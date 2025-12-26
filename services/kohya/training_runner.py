"""Kohya Training Runner - Subprocess management for training.

This module handles the actual training process execution,
log parsing, and progress tracking.
Supports FLUX, SDXL, and SD3 model types.
"""

import os
import re
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional, Callable, List

from infrastructure.logger import get_logger
from .models import KohyaTrainingStatus, KohyaTrainingProgress, KohyaModelType, KOHYA_TRAINING_SCRIPTS

logger = get_logger(__name__)


class KohyaTrainingRunner:
    """Manages training subprocess execution and monitoring.

    Supports multiple model types: FLUX, SDXL, SD3.
    """

    # Log parsing patterns
    PATTERNS = {
        "step": re.compile(r"(\d+)/(\d+).*?(?:it/s|s/it)", re.IGNORECASE),
        "epoch": re.compile(r"[Ee]poch\s+(\d+)/(\d+)"),
        "loss": re.compile(r"(?:loss|avr_loss)[=:\s]+([0-9.]+(?:e[+-]?\d+)?)", re.IGNORECASE),
        # More specific error patterns to avoid false positives like "ar error", "accelerator"
        "error": re.compile(r"((?<!\w)Error(?!\s+\(without)|Exception|CUDA\s+error|OOM|out of memory|RuntimeError|ValueError|AssertionError)", re.IGNORECASE),
        "complete": re.compile(r"(Training completed|model saved|Saving model)", re.IGNORECASE),
        "nan": re.compile(r"loss[=:\s]+nan", re.IGNORECASE),
    }

    def __init__(self, kohya_path: str, model_type: KohyaModelType = KohyaModelType.FLUX):
        """Initialize the training runner.

        Args:
            kohya_path: Path to the Kohya sd-scripts directory
            model_type: Model type (FLUX, SDXL, SD3)
        """
        self._kohya_path = kohya_path
        self._model_type = model_type
        self._process: Optional[subprocess.Popen] = None
        self._progress = KohyaTrainingProgress()
        self._stop_event = threading.Event()
        self._log_thread: Optional[threading.Thread] = None
        self._start_time: float = 0
        self._log_callback: Optional[Callable[[str], None]] = None

    @property
    def model_type(self) -> KohyaModelType:
        """Get current model type."""
        return self._model_type

    @model_type.setter
    def model_type(self, value: KohyaModelType):
        """Set model type (only when not running)."""
        if self.is_running():
            raise RuntimeError("Cannot change model type while training is running")
        self._model_type = value

    def get_training_script(self) -> str:
        """Get the training script name for current model type."""
        return KOHYA_TRAINING_SCRIPTS.get(self._model_type, "flux_train_network.py")

    @property
    def progress(self) -> KohyaTrainingProgress:
        """Get current training progress."""
        return self._progress

    def is_running(self) -> bool:
        """Check if training is currently running."""
        return (
            self._process is not None and
            self._process.poll() is None and
            self._progress.status == KohyaTrainingStatus.RUNNING
        )

    def get_logs(self, last_n: int = 100) -> List[str]:
        """Get recent log lines."""
        return self._progress.log_lines[-last_n:]

    def start(
        self,
        config_path: str,
        log_callback: Optional[Callable[[str], None]] = None
    ) -> bool:
        """Start the training process.

        Args:
            config_path: Path to TOML config file
            log_callback: Optional callback for log lines

        Returns:
            True if training started successfully
        """
        if self._process and self._process.poll() is None:
            logger.warning("Training already in progress")
            return False

        if not self._kohya_path:
            logger.error("Kohya sd-scripts not found")
            self._progress.status = KohyaTrainingStatus.ERROR
            self._progress.error_message = "Kohya sd-scripts nicht gefunden. Erwartet in: tools/sd-scripts/"
            return False

        # Reset state
        self._progress = KohyaTrainingProgress()
        self._progress.status = KohyaTrainingStatus.PREPARING
        self._stop_event.clear()
        self._start_time = time.time()
        self._log_callback = log_callback

        # Extract output_dir and output_name from config for sample image tracking
        self._output_name = ""
        try:
            import toml
            with open(config_path, "r") as f:
                config_data = toml.load(f)
            training_args = config_data.get("training_arguments", {})
            self._progress.output_dir = training_args.get("output_dir", "")
            self._output_name = training_args.get("output_name", "")
        except Exception as e:
            logger.warning(f"Could not read output_dir from config: {e}")

        # Build command with model-type-specific script
        script_name = self.get_training_script()
        script_path = Path(self._kohya_path) / script_name
        cmd = [
            "python", str(script_path),
            "--config_file", config_path
        ]

        logger.info(f"Starting Kohya {self._model_type.value.upper()} training: {' '.join(cmd)}")

        try:
            # Set up environment - use sd-scripts venv
            env = os.environ.copy()
            env["PYTHONPATH"] = self._kohya_path

            # Find Python interpreter
            python_path = self._find_python_interpreter()
            if python_path:
                cmd[0] = python_path

            # Start process
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=self._kohya_path,
                env=env,
                text=True,
                bufsize=1
            )

            self._progress.status = KohyaTrainingStatus.RUNNING

            # Start log reader thread
            self._log_thread = threading.Thread(
                target=self._read_logs,
                daemon=True
            )
            self._log_thread.start()

            logger.info(f"Kohya training started with PID: {self._process.pid}")
            return True

        except Exception as e:
            logger.error(f"Failed to start Kohya training: {e}", exc_info=True)
            self._progress.status = KohyaTrainingStatus.ERROR
            self._progress.error_message = str(e)
            return False

    def _find_python_interpreter(self) -> Optional[str]:
        """Find the appropriate Python interpreter for training."""
        # Use sd-scripts local venv (preferred) or FluxGym venv as fallback
        local_venv = Path(self._kohya_path) / ".venv" / "bin" / "python"
        fluxgym_venv = Path.home() / "projekte" / "fluxgym" / "env" / "bin" / "python"

        if local_venv.exists():
            logger.info(f"Using local sd-scripts Python: {local_venv}")
            return str(local_venv)
        elif fluxgym_venv.exists():
            logger.info(f"Using FluxGym Python: {fluxgym_venv}")
            return str(fluxgym_venv)
        return None

    def _read_logs(self):
        """Read and parse logs from training process."""
        if not self._process or not self._process.stdout:
            return

        try:
            for line in iter(self._process.stdout.readline, ""):
                if self._stop_event.is_set():
                    break

                line = line.rstrip()
                if not line:
                    continue

                # Store log line
                self._progress.log_lines.append(line)
                if len(self._progress.log_lines) > 1000:
                    self._progress.log_lines.pop(0)

                # Parse log line
                self._parse_log_line(line)

                # Call callback
                if self._log_callback:
                    try:
                        self._log_callback(line)
                    except Exception as e:
                        logger.warning(f"Log callback error: {e}")

        except Exception as e:
            logger.error(f"Log reading error: {e}", exc_info=True)

        # Update final status
        if self._process:
            self._process.wait()
            exit_code = self._process.returncode

            if self._stop_event.is_set():
                self._progress.status = KohyaTrainingStatus.CANCELLED
            elif exit_code == 0:
                self._progress.status = KohyaTrainingStatus.COMPLETED
                logger.info("Kohya training completed successfully")
                # Create .models sidecar file with model type
                self._create_models_sidecar()
            else:
                self._progress.status = KohyaTrainingStatus.ERROR
                self._progress.error_message = f"Process exited with code {exit_code}"
                logger.error(f"Kohya training failed with exit code: {exit_code}")

    def _parse_log_line(self, line: str):
        """Parse a log line and update progress."""
        # Update elapsed time
        self._progress.elapsed_time = time.time() - self._start_time

        # Parse step progress (e.g., "123/1500 [00:45<1:23:45, 4.28s/it]")
        step_match = self.PATTERNS["step"].search(line)
        if step_match:
            self._progress.current_step = int(step_match.group(1))
            self._progress.total_steps = int(step_match.group(2))

            # Calculate ETA
            if self._progress.current_step > 0:
                steps_remaining = self._progress.total_steps - self._progress.current_step
                time_per_step = self._progress.elapsed_time / self._progress.current_step
                self._progress.eta_seconds = steps_remaining * time_per_step

        # Parse epoch
        epoch_match = self.PATTERNS["epoch"].search(line)
        if epoch_match:
            self._progress.current_epoch = int(epoch_match.group(1))
            self._progress.total_epochs = int(epoch_match.group(2))

        # Parse loss
        loss_match = self.PATTERNS["loss"].search(line)
        if loss_match:
            try:
                loss_str = loss_match.group(1)
                if loss_str.lower() != "nan":
                    loss_value = float(loss_str)
                    self._progress.current_loss = loss_value
                    # Update average (exponential moving average)
                    if self._progress.average_loss == 0:
                        self._progress.average_loss = loss_value
                    else:
                        self._progress.average_loss = (
                            self._progress.average_loss * 0.95 + loss_value * 0.05
                        )
            except ValueError:
                pass

        # Check for NaN loss
        if self.PATTERNS["nan"].search(line):
            logger.warning("NaN loss detected - training may be unstable")

        # Check for errors
        if self.PATTERNS["error"].search(line):
            logger.warning(f"Training warning/error: {line}")

    def cancel(self) -> bool:
        """Cancel the running training process."""
        if not self._process or self._process.poll() is not None:
            logger.warning("No training process to cancel")
            return False

        logger.info("Cancelling Kohya training...")
        self._stop_event.set()

        try:
            # Send SIGTERM for graceful shutdown
            self._process.send_signal(signal.SIGTERM)

            # Wait for graceful shutdown
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning("Force killing training process")
                self._process.kill()
                self._process.wait()

            self._progress.status = KohyaTrainingStatus.CANCELLED
            logger.info("Kohya training cancelled")
            return True

        except Exception as e:
            logger.error(f"Error cancelling training: {e}", exc_info=True)
            return False

    def _create_models_sidecar(self):
        """Create .models sidecar file with model type information.

        This file is used by CharacterLoraService to determine LoRA compatibility
        with different base model types (FLUX, SDXL, SD3).

        Format:
            # Model type
            type=flux

            # Compatible base models (optional)
            flux1-dev-fp8.safetensors
        """
        if not self._progress.output_dir or not self._output_name:
            logger.warning("Cannot create .models file: missing output_dir or output_name")
            return

        # Find the final LoRA file
        output_dir = Path(self._progress.output_dir)
        lora_file = output_dir / f"{self._output_name}.safetensors"

        if not lora_file.exists():
            # Try to find any matching safetensors file
            candidates = list(output_dir.glob(f"{self._output_name}*.safetensors"))
            if candidates:
                # Take the most recent one
                lora_file = max(candidates, key=lambda p: p.stat().st_mtime)
            else:
                logger.warning(f"LoRA file not found: {lora_file}")
                return

        # Create .models sidecar file
        models_file = lora_file.with_suffix('.models')
        model_type = self._model_type.value  # "flux", "sdxl", "sd3"

        try:
            content = f"""# Auto-generated by CinderGrace Character Trainer
# Model type this LoRA was trained for
type={model_type}

# Compatible base models can be listed below (one per line)
# Example: flux1-dev-fp8.safetensors
"""
            with open(models_file, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"Created .models sidecar file: {models_file} (type={model_type})")

        except Exception as e:
            logger.error(f"Failed to create .models file: {e}")
