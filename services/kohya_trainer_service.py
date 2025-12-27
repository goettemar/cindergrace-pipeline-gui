"""Kohya LoRA Trainer Service - Direct sd-scripts orchestrator for LoRA training.

This service provides a clean interface to train character LoRAs using
Kohya sd-scripts (sd3 branch) directly via subprocess (bypassing ComfyUI).
This is more stable for RTX 50xx GPUs that require PyTorch 2.8+/CUDA 12.8.

Supported Model Types:
- FLUX: Diffusion Transformer models (FLUX.1-dev, FLUX.1-schnell)
- SDXL: Stable Diffusion XL models
- SD3: Stable Diffusion 3 models (SD3-medium, SD3.5)

Features:
- TOML config generation with VRAM-aware presets
- Subprocess management for training
- Real-time log streaming
- Training cancellation and status tracking

LICENSING NOTE:
This is an orchestration tool only. No models or weights are bundled.
Users are responsible for:
- Obtaining and licensing base models
- Complying with respective model licenses
- Legal use of trained LoRAs
"""

from pathlib import Path
from typing import Optional, Callable, Dict, Any, List, Tuple

from infrastructure.config_manager import ConfigManager
from infrastructure.logger import get_logger

# Import from package
from services.kohya import (
    KohyaTrainingStatus,
    KohyaModelType,
    KohyaVRAMPreset,
    KohyaTrainingConfig,
    KohyaTrainingProgress,
    KOHYA_VRAM_PRESETS,
    KOHYA_VALID_PRESETS,
    KOHYA_TRAINING_SCRIPTS,
    get_vram_preset,
    KohyaConfigBuilder,
    KohyaModelScanner,
    KohyaTrainingRunner,
)

logger = get_logger(__name__)


class KohyaTrainerService:
    """Orchestrates Kohya sd-scripts for LoRA training.

    Supports FLUX, SDXL, and SD3 model types.

    This service manages the complete LoRA training workflow using
    Kohya sd-scripts directly (not via ComfyUI), which is more stable
    for newer GPUs like RTX 50xx series.

    Example:
        trainer = KohyaTrainerService(config)

        # Generate config for SDXL
        config_path = trainer.generate_training_config(
            character_name="elena",
            images_dir="/path/to/images",
            trigger_word="elena",
            model_type=KohyaModelType.SDXL,
            vram_preset=KohyaVRAMPreset.VRAM_16GB
        )

        # Start training with log callback
        def on_log(line):
            print(line)

        trainer.start_training(config_path, model_type=KohyaModelType.SDXL, log_callback=on_log)

        # Monitor progress
        while trainer.is_training():
            progress = trainer.get_progress()
            print(f"Step {progress.current_step}/{progress.total_steps}")
            time.sleep(1)
    """

    def __init__(self, config: Optional[ConfigManager] = None):
        """Initialize the trainer service.

        Args:
            config: ConfigManager instance for accessing settings
        """
        self.config = config or ConfigManager()

        # Locate Kohya sd-scripts
        self._kohya_path = self._find_kohya_scripts()

        # Initialize components
        comfy_root = self.config.get_comfy_root()
        self._model_scanner = KohyaModelScanner(comfy_root) if comfy_root else None
        self._config_builder = KohyaConfigBuilder(
            config_dir=str(Path(self.config.config_dir).resolve()),
            comfy_root=comfy_root or ""
        )
        self._runner = KohyaTrainingRunner(self._kohya_path)
        self._current_model_type = KohyaModelType.FLUX

    def _find_kohya_scripts(self) -> str:
        """Find the Kohya sd-scripts directory.

        Returns:
            Path to sd-scripts directory
        """
        # Get the cindergrace_gui root directory
        cindergrace_root = Path(__file__).parent.parent.resolve()

        possible_paths = [
            # First check local tools directory (preferred)
            cindergrace_root / "tools" / "sd-scripts",
            # Then check other common locations
            Path.home() / "projekte" / "fluxgym" / "sd-scripts",
            Path.home() / "sd-scripts",
            Path.home() / "kohya_ss" / "sd-scripts",
            Path("/opt/sd-scripts"),
        ]

        for path in possible_paths:
            script_path = path / "flux_train_network.py"
            if script_path.exists():
                logger.info(f"Found Kohya sd-scripts at: {path}")
                return str(path)

        logger.warning("Kohya sd-scripts not found in common locations")
        return ""

    def get_kohya_path(self) -> str:
        """Get the Kohya sd-scripts path."""
        return self._kohya_path

    def is_kohya_available(self) -> bool:
        """Check if Kohya sd-scripts is available."""
        return bool(self._kohya_path)

    # ==================== Installation ====================

    def get_install_path(self) -> Path:
        """Get the target installation path for sd-scripts."""
        cindergrace_root = Path(__file__).parent.parent.resolve()
        return cindergrace_root / "tools" / "sd-scripts"

    def _detect_cuda_version(self) -> str:
        """Detect installed CUDA version for PyTorch installation.

        Returns:
            CUDA version string like 'cu128', 'cu124', 'cu121' or 'cpu'
        """
        import subprocess
        import shutil

        # Try nvidia-smi first
        try:
            result = subprocess.run(
                ["nvidia-smi"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "CUDA Version" in line:
                        parts = line.split("CUDA Version:")
                        if len(parts) > 1:
                            version = parts[1].strip().rstrip("|").strip()
                            # Parse major.minor
                            version_parts = version.split(".")
                            if len(version_parts) >= 2:
                                major = int(version_parts[0])
                                minor = int(version_parts[1])
                                # Map to PyTorch CUDA versions
                                if major >= 12 and minor >= 8:
                                    return "cu128"
                                elif major >= 12 and minor >= 4:
                                    return "cu124"
                                elif major >= 12 and minor >= 1:
                                    return "cu121"
                                elif major >= 11 and minor >= 8:
                                    return "cu118"
                                else:
                                    return "cu121"  # Default fallback
        except Exception:
            pass

        # Try nvcc
        nvcc = shutil.which("nvcc")
        if nvcc:
            try:
                result = subprocess.run(
                    ["nvcc", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    for line in result.stdout.split("\n"):
                        if "release" in line.lower():
                            parts = line.split("release")
                            if len(parts) > 1:
                                version = parts[1].split(",")[0].strip()
                                version_parts = version.split(".")
                                if len(version_parts) >= 2:
                                    major = int(version_parts[0])
                                    minor = int(version_parts[1])
                                    if major >= 12 and minor >= 8:
                                        return "cu128"
                                    elif major >= 12 and minor >= 4:
                                        return "cu124"
                                    elif major >= 12:
                                        return "cu121"
                                    else:
                                        return "cu118"
            except Exception:
                pass

        logger.warning("Could not detect CUDA version, defaulting to cu121")
        return "cu121"

    def install_kohya_scripts(
        self,
        log_callback: Optional[Callable[[str], None]] = None
    ) -> Tuple[bool, str]:
        """Install Kohya sd-scripts automatically.

        This will:
        1. Clone the sd-scripts repository (sd3 branch)
        2. Create a Python virtual environment
        3. Install PyTorch with detected CUDA version
        4. Install requirements.txt

        Args:
            log_callback: Optional callback for log messages

        Returns:
            Tuple of (success, message)
        """
        import subprocess
        import shutil

        def log(msg: str):
            logger.info(msg)
            if log_callback:
                log_callback(msg)

        # Check prerequisites
        git = shutil.which("git")
        if not git:
            return False, "Git ist nicht installiert. Bitte zuerst Git installieren."

        python = shutil.which("python3") or shutil.which("python")
        if not python:
            return False, "Python3 ist nicht installiert."

        install_path = self.get_install_path()
        tools_dir = install_path.parent

        # Check if already installed
        if (install_path / "flux_train_network.py").exists():
            log("sd-scripts ist bereits installiert.")
            self._kohya_path = str(install_path)
            return True, "sd-scripts ist bereits installiert."

        try:
            # Create tools directory if needed
            tools_dir.mkdir(parents=True, exist_ok=True)
            log(f"📁 Installationsverzeichnis: {install_path}")

            # Step 1: Clone repository
            log("📥 Klone Kohya sd-scripts Repository (sd3 branch)...")
            log("   Dies kann einige Minuten dauern (~100MB)...")

            result = subprocess.run(
                ["git", "clone", "-b", "sd3", "--depth", "1",
                 "https://github.com/kohya-ss/sd-scripts.git", str(install_path)],
                capture_output=True,
                text=True,
                timeout=600,  # 10 min timeout
                cwd=str(tools_dir)
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                log(f"❌ Git clone fehlgeschlagen: {error_msg}")
                return False, f"Git clone fehlgeschlagen: {error_msg}"

            log("✅ Repository erfolgreich geklont")

            # Step 2: Create virtual environment
            log("🐍 Erstelle Python Virtual Environment...")

            venv_path = install_path / ".venv"
            result = subprocess.run(
                [python, "-m", "venv", str(venv_path)],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(install_path)
            )

            if result.returncode != 0:
                log(f"❌ venv Erstellung fehlgeschlagen: {result.stderr}")
                return False, f"venv Erstellung fehlgeschlagen: {result.stderr}"

            log("✅ Virtual Environment erstellt")

            # Determine pip path
            pip_path = venv_path / "bin" / "pip"
            if not pip_path.exists():
                pip_path = venv_path / "Scripts" / "pip.exe"  # Windows

            # Step 3: Detect CUDA and install PyTorch
            cuda_version = self._detect_cuda_version()
            log(f"🔍 Erkannte CUDA-Version: {cuda_version}")

            if cuda_version == "cpu":
                pytorch_url = "https://download.pytorch.org/whl/cpu"
            else:
                pytorch_url = f"https://download.pytorch.org/whl/{cuda_version}"

            log(f"📦 Installiere PyTorch mit {cuda_version}...")
            log("   Dies kann 5-10 Minuten dauern (~2GB Download)...")

            result = subprocess.run(
                [str(pip_path), "install", "torch", "torchvision", "torchaudio",
                 "--index-url", pytorch_url],
                capture_output=True,
                text=True,
                timeout=1800,  # 30 min timeout
                cwd=str(install_path)
            )

            if result.returncode != 0:
                log(f"⚠️ PyTorch Installation Warnung: {result.stderr[:500]}")
                # Continue anyway, might still work

            log("✅ PyTorch installiert")

            # Step 4: Install requirements
            log("📦 Installiere sd-scripts Abhängigkeiten...")
            log("   Dies kann 5-10 Minuten dauern...")

            requirements_file = install_path / "requirements.txt"
            if requirements_file.exists():
                result = subprocess.run(
                    [str(pip_path), "install", "-r", "requirements.txt"],
                    capture_output=True,
                    text=True,
                    timeout=1800,  # 30 min timeout
                    cwd=str(install_path)
                )

                if result.returncode != 0:
                    log(f"⚠️ Requirements Installation Warnung: {result.stderr[:500]}")
                    # Continue anyway

            log("✅ Abhängigkeiten installiert")

            # Verify installation
            if (install_path / "flux_train_network.py").exists():
                self._kohya_path = str(install_path)
                log("🎉 Installation erfolgreich abgeschlossen!")
                log("   Du kannst jetzt LoRA Training verwenden.")
                return True, "Installation erfolgreich!"
            else:
                return False, "Installation fehlgeschlagen - Training-Script nicht gefunden"

        except subprocess.TimeoutExpired:
            log("❌ Timeout - Installation hat zu lange gedauert")
            return False, "Installation Timeout"
        except Exception as e:
            log(f"❌ Fehler: {str(e)}")
            return False, f"Installation fehlgeschlagen: {str(e)}"

    # ==================== Model Type Management ====================

    def get_supported_model_types(self) -> List[KohyaModelType]:
        """Get list of supported model types."""
        return list(KohyaModelType)

    def get_valid_vram_presets(
        self,
        model_type: KohyaModelType = KohyaModelType.FLUX
    ) -> List[KohyaVRAMPreset]:
        """Get valid VRAM presets for a model type.

        Args:
            model_type: The model type

        Returns:
            List of valid VRAM presets
        """
        return KOHYA_VALID_PRESETS.get(model_type, [KohyaVRAMPreset.VRAM_16GB])

    # ==================== Model Scanning ====================

    def scan_available_models(
        self,
        model_type: KohyaModelType = KohyaModelType.FLUX
    ) -> List[Tuple[str, str]]:
        """Scan for available models of a specific type.

        Args:
            model_type: The model type to scan for

        Returns:
            List of tuples (display_name, full_path)
        """
        if not self._model_scanner:
            return []
        return self._model_scanner.scan_models(model_type)

    def scan_available_flux_models(self) -> List[Tuple[str, str]]:
        """Scan for available FLUX models in the models folder."""
        return self._model_scanner.scan_flux_models() if self._model_scanner else []

    def scan_available_sdxl_models(self) -> List[Tuple[str, str]]:
        """Scan for available SDXL models in the models folder."""
        return self._model_scanner.scan_sdxl_models() if self._model_scanner else []

    def scan_available_sd3_models(self) -> List[Tuple[str, str]]:
        """Scan for available SD3 models in the models folder."""
        return self._model_scanner.scan_sd3_models() if self._model_scanner else []

    def scan_available_t5xxl_models(self) -> List[Tuple[str, str]]:
        """Scan for available T5XXL text encoder models."""
        return self._model_scanner.scan_t5xxl_models() if self._model_scanner else []

    def scan_available_clip_g_models(self) -> List[Tuple[str, str]]:
        """Scan for available CLIP-G text encoder models (SD3 only)."""
        return self._model_scanner.scan_clip_g_models() if self._model_scanner else []

    # ==================== Configuration ====================

    def get_vram_preset_config(
        self,
        preset: KohyaVRAMPreset,
        model_type: KohyaModelType = KohyaModelType.FLUX
    ) -> Dict[str, Any]:
        """Get training parameters for a VRAM preset.

        Args:
            preset: The VRAM preset
            model_type: The model type

        Returns:
            Dictionary with preset configuration
        """
        return get_vram_preset(model_type, preset)

    def generate_training_config(
        self,
        character_name: str,
        images_dir: str,
        trigger_word: str,
        model_type: KohyaModelType = KohyaModelType.FLUX,
        output_dir: Optional[str] = None,
        vram_preset: KohyaVRAMPreset = KohyaVRAMPreset.VRAM_16GB,
        base_model_path: Optional[str] = None,
        t5xxl_model_path: Optional[str] = None,
        clip_g_model_path: Optional[str] = None,
        vae_path: Optional[str] = None,
        **overrides
    ) -> str:
        """Generate TOML configuration for training.

        Args:
            character_name: Name for the character (used in output filename)
            images_dir: Directory containing training images
            trigger_word: Trigger word for the LoRA (without cg_ prefix)
            model_type: Model type (FLUX, SDXL, SD3)
            output_dir: Output directory (default: ComfyUI loras folder)
            vram_preset: VRAM optimization preset
            base_model_path: Custom path to base model (optional)
            t5xxl_model_path: Custom path to T5XXL encoder (FLUX/SD3 only)
            clip_g_model_path: Custom path to CLIP-G encoder (SD3 only)
            vae_path: Custom VAE path (optional)
            **overrides: Override any default parameters

        Returns:
            Path to generated TOML config file
        """
        # Get default model paths for this model type
        model_paths = (
            self._model_scanner.get_default_model_paths(model_type)
            if self._model_scanner else {}
        )

        # Override with custom paths if provided
        if base_model_path:
            model_paths["model"] = base_model_path
            logger.info(f"Using custom {model_type.value.upper()} model: {base_model_path}")
        if t5xxl_model_path:
            model_paths["t5xxl"] = t5xxl_model_path
            logger.info(f"Using custom T5XXL encoder: {t5xxl_model_path}")
        if clip_g_model_path:
            model_paths["clip_g"] = clip_g_model_path
            logger.info(f"Using custom CLIP-G encoder: {clip_g_model_path}")
        if vae_path:
            model_paths["vae"] = vae_path
            logger.info(f"Using custom VAE: {vae_path}")

        # Store current model type for training
        self._current_model_type = model_type

        return self._config_builder.generate_training_config(
            character_name=character_name,
            images_dir=images_dir,
            trigger_word=trigger_word,
            output_dir=output_dir,
            model_paths=model_paths,
            model_type=model_type,
            vram_preset=vram_preset,
            **overrides
        )

    # ==================== Training Control ====================

    def start_training(
        self,
        config_path: str,
        model_type: Optional[KohyaModelType] = None,
        log_callback: Optional[Callable[[str], None]] = None
    ) -> bool:
        """Start the training process.

        Args:
            config_path: Path to TOML config file
            model_type: Model type (uses last generated config type if not specified)
            log_callback: Optional callback for log lines

        Returns:
            True if training started successfully
        """
        # Use provided model type or fall back to current
        effective_model_type = model_type or self._current_model_type

        # Update runner's model type
        self._runner.model_type = effective_model_type

        return self._runner.start(config_path, log_callback)

    def cancel_training(self) -> bool:
        """Cancel the running training process."""
        return self._runner.cancel()

    def is_training(self) -> bool:
        """Check if training is currently running."""
        return self._runner.is_running()

    def get_progress(self) -> KohyaTrainingProgress:
        """Get current training progress."""
        return self._runner.progress

    def get_logs(self, last_n: int = 100) -> List[str]:
        """Get recent log lines."""
        return self._runner.get_logs(last_n)

    def find_trained_lora(self, character_name: str) -> Optional[str]:
        """Find the trained LoRA file.

        Args:
            character_name: Character name used during training

        Returns:
            Path to LoRA file or None
        """
        return self._model_scanner.find_trained_lora(character_name) if self._model_scanner else None


# Re-export for backwards compatibility
__all__ = [
    "KohyaTrainerService",
    "KohyaTrainingConfig",
    "KohyaTrainingProgress",
    "KohyaTrainingStatus",
    "KohyaModelType",
    "KohyaVRAMPreset",
    "KOHYA_VRAM_PRESETS",
    "KOHYA_VALID_PRESETS",
]
