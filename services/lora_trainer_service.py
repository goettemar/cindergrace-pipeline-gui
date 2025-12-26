"""Service for Flux LoRA Training via ComfyUI."""
import copy
import glob
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from infrastructure.comfy_api.client import ComfyUIAPI
from infrastructure.config_manager import ConfigManager
from infrastructure.logger import get_logger

logger = get_logger(__name__)


class TrainingPreset(Enum):
    """Training presets for different use cases."""
    QUICK = "quick"        # Fast test run
    STANDARD = "standard"  # Default training
    QUALITY = "quality"    # Extended training


class VRAMPreset(Enum):
    """VRAM presets for different GPU configurations."""
    VRAM_12GB = "12gb"     # 12GB VRAM - only 512
    VRAM_16GB = "16gb"     # 16GB VRAM - 512 + 768
    VRAM_24GB = "24gb"     # 24GB+ VRAM - 512 + 768 + 1024


# Resolution configurations per VRAM preset
VRAM_RESOLUTION_CONFIG = {
    VRAMPreset.VRAM_12GB: {
        "resolutions": [512],
        "description": "12GB VRAM (RTX 3060, 4070) - Nur 512px",
    },
    VRAMPreset.VRAM_16GB: {
        "resolutions": [512, 768],
        "description": "16GB VRAM (RTX 4080, 4070 Ti) - 512 + 768px",
    },
    VRAMPreset.VRAM_24GB: {
        "resolutions": [512, 768, 1024],
        "description": "24GB+ VRAM (RTX 3090, 4090) - Alle Auflösungen",
    },
}


@dataclass
class TrainingConfig:
    """Configuration for LoRA training."""
    # Required
    dataset_path: str
    trigger_word: str
    output_name: str

    # Training parameters
    total_steps: int = 3000
    network_dim: int = 16
    network_alpha: float = 1.0  # Changed to float for nightly API
    learning_rate: float = 0.0004

    # Dataset options
    num_repeats: int = 1
    enable_bucket: bool = True

    # VRAM / Resolution
    vram_preset: VRAMPreset = VRAMPreset.VRAM_16GB

    # Validation
    sample_prompts: Optional[str] = None
    validation_steps: int = 20

    # Advanced
    optimizer: str = "CAME"
    lr_scheduler: str = "constant"
    gradient_dtype: str = "bf16"
    save_dtype: str = "bf16"
    fp8_base: bool = True


# Preset configurations
TRAINING_PRESETS: Dict[TrainingPreset, TrainingConfig] = {
    TrainingPreset.QUICK: TrainingConfig(
        dataset_path="",
        trigger_word="",
        output_name="",
        total_steps=500,
        network_dim=8,
        learning_rate=0.0005,
    ),
    TrainingPreset.STANDARD: TrainingConfig(
        dataset_path="",
        trigger_word="",
        output_name="",
        total_steps=3000,
        network_dim=16,
        learning_rate=0.0004,
    ),
    TrainingPreset.QUALITY: TrainingConfig(
        dataset_path="",
        trigger_word="",
        output_name="",
        total_steps=6000,
        network_dim=32,
        learning_rate=0.0003,
    ),
}


@dataclass
class TrainingProgress:
    """Progress information during training."""
    current_step: int = 0
    total_steps: int = 0
    current_epoch: int = 0
    loss: float = 0.0
    status: str = "idle"


@dataclass
class TrainingResult:
    """Result of a training run."""
    success: bool
    lora_path: Optional[str] = None
    output_dir: str = ""
    total_steps: int = 0
    duration_seconds: float = 0
    loss_plot_path: Optional[str] = None
    validation_images: List[str] = field(default_factory=list)
    error: Optional[str] = None


class LoraTrainerService:
    """Service for training Flux LoRAs via ComfyUI."""

    WORKFLOW_FILE = "config/workflow_templates/flux_lora_train.json"
    OUTPUT_BASE_DIR = "output/lora_training"

    # Node IDs in the workflow
    NODES = {
        # Main training config
        "init_training": "107",

        # Dataset nodes (chained: 137 → 109 → 111 → 112)
        "dataset_config": "137",
        "dataset_512": "109",
        "dataset_768": "111",
        "dataset_1024": "112",

        # Training loops (4 loops × 750 steps = 3000 total)
        "train_loop_1": "4",
        "train_loop_2": "44",
        "train_loop_3": "59",
        "train_loop_4": "64",

        # Save checkpoints
        "save_1": "14",
        "save_2": "47",
        "save_3": "62",
        "save_4": "134",
        "save_final": "133",

        # Validation
        "validation_settings": "37",
        "sample_prompts": "135",

        # Optimizer
        "optimizer": "95",

        # Model selection
        "model_select": "136",

        # Outputs
        "loss_plot": "90",
        "trainer_sheet": "130",
    }

    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config or ConfigManager()
        self.api = ComfyUIAPI(self.config.get_comfy_url())
        self._workflow: Optional[Dict[str, Any]] = None

    def get_preset_config(self, preset: TrainingPreset) -> TrainingConfig:
        """Get a preset training configuration."""
        return copy.deepcopy(TRAINING_PRESETS[preset])

    def _load_workflow(self) -> Dict[str, Any]:
        """Load the LoRA training workflow."""
        if self._workflow is None:
            workflow_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                self.WORKFLOW_FILE
            )
            self._workflow = self.api.load_workflow(workflow_path)
        return copy.deepcopy(self._workflow)

    def _get_output_dir(self, output_name: str) -> str:
        """Get the output directory for training."""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in output_name)
        output_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            self.OUTPUT_BASE_DIR,
            f"{safe_name}_{timestamp}"
        )
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def validate_dataset(self, dataset_path: str) -> tuple[bool, str, int]:
        """
        Validate a dataset directory.

        Supports two formats:
        1. Flat: images directly in dataset_path/
        2. Kohya DreamBooth: images in dataset_path/<repeats>_<trigger>/

        Returns:
            Tuple of (is_valid, message, image_count)
        """
        if not os.path.exists(dataset_path):
            return False, f"Pfad existiert nicht: {dataset_path}", 0

        if not os.path.isdir(dataset_path):
            return False, f"Pfad ist kein Verzeichnis: {dataset_path}", 0

        # Count images
        image_extensions = {".png", ".jpg", ".jpeg", ".webp"}
        images = []
        captions = []

        # First check for images directly in the folder
        for f in os.listdir(dataset_path):
            name, ext = os.path.splitext(f)
            if ext.lower() in image_extensions:
                images.append(f)
            elif ext.lower() == ".txt":
                captions.append(name)

        # If no images found, check Kohya DreamBooth subfolders (e.g., 10_triggerwort/)
        if not images:
            for subdir in os.listdir(dataset_path):
                subdir_path = os.path.join(dataset_path, subdir)
                if os.path.isdir(subdir_path) and "_" in subdir:
                    # Could be a Kohya format folder like "10_triggerwort"
                    for f in os.listdir(subdir_path):
                        name, ext = os.path.splitext(f)
                        if ext.lower() in image_extensions:
                            images.append(f)
                        elif ext.lower() == ".txt":
                            captions.append(name)

        if not images:
            return False, "Keine Bilder gefunden (.png, .jpg, .jpeg, .webp)", 0

        # Check for captions
        images_without_captions = []
        for img in images:
            name = os.path.splitext(img)[0]
            if name not in captions:
                images_without_captions.append(img)

        if images_without_captions:
            msg = f"{len(images)} Bilder gefunden, {len(images_without_captions)} ohne Caption"
            return True, msg, len(images)

        return True, f"{len(images)} Bilder mit Captions gefunden", len(images)

    def _configure_workflow(
        self,
        workflow: Dict[str, Any],
        config: TrainingConfig,
        output_dir: str
    ) -> Dict[str, Any]:
        """Configure the workflow with training parameters."""

        # Main training config (Node 107)
        init = workflow[self.NODES["init_training"]]["inputs"]
        init["output_name"] = config.output_name
        init["output_dir"] = output_dir
        init["network_dim"] = config.network_dim
        init["network_alpha"] = config.network_alpha
        init["learning_rate"] = config.learning_rate
        init["max_train_steps"] = config.total_steps
        init["fp8_base"] = config.fp8_base
        init["gradient_dtype"] = config.gradient_dtype
        init["save_dtype"] = config.save_dtype
        # Memory optimization based on VRAM preset (nightly API)
        # blocks_to_swap: 0 = disabled, 18 = full split mode (saves VRAM)
        if config.vram_preset == VRAMPreset.VRAM_24GB:
            init["highvram"] = True
            init["blocks_to_swap"] = 0
            # gradient_checkpointing is optional, don't set it for 24GB
        elif config.vram_preset == VRAMPreset.VRAM_16GB:
            init["highvram"] = False
            init["blocks_to_swap"] = 18  # Full split mode for 16GB
        else:  # 12GB
            init["highvram"] = False
            init["blocks_to_swap"] = 18  # Full split mode

        # Dataset configuration based on VRAM preset
        resolutions = VRAM_RESOLUTION_CONFIG[config.vram_preset]["resolutions"]

        # Convert to relative path for ComfyUI training node
        relative_dataset_path = self.get_relative_dataset_path(config.dataset_path)
        logger.info(f"Dataset path: {config.dataset_path} -> relative: {relative_dataset_path}")

        # Configure all resolution nodes with dataset info
        for node_key in ["dataset_512", "dataset_768", "dataset_1024"]:
            dataset = workflow[self.NODES[node_key]]["inputs"]
            dataset["dataset_path"] = relative_dataset_path
            dataset["class_tokens"] = config.trigger_word
            dataset["num_repeats"] = config.num_repeats
            dataset["enable_bucket"] = config.enable_bucket

        # Point to the correct dataset node based on VRAM preset
        # Chain: 137 → 109 (512) → 111 (768) → 112 (1024)
        if 1024 in resolutions:
            # Use all resolutions (default)
            init["dataset"] = ["112", 0]
        elif 768 in resolutions:
            # Use 512 + 768 only
            init["dataset"] = ["111", 0]
        else:
            # Use 512 only
            init["dataset"] = ["109", 0]

        logger.info(f"VRAM preset: {config.vram_preset.value}, resolutions: {resolutions}")

        # Training loops - distribute steps across 4 loops
        steps_per_loop = config.total_steps // 4
        remainder = config.total_steps % 4

        for i, loop_key in enumerate(["train_loop_1", "train_loop_2", "train_loop_3", "train_loop_4"]):
            loop_steps = steps_per_loop + (1 if i < remainder else 0)
            workflow[self.NODES[loop_key]]["inputs"]["steps"] = loop_steps

        # Optimizer
        optimizer = workflow[self.NODES["optimizer"]]["inputs"]
        optimizer["optimizer_type"] = config.optimizer
        optimizer["lr_scheduler"] = config.lr_scheduler

        # Validation settings
        validation = workflow[self.NODES["validation_settings"]]["inputs"]
        validation["steps"] = config.validation_steps

        # Sample prompts for validation
        if config.sample_prompts:
            workflow[self.NODES["sample_prompts"]]["inputs"]["string"] = config.sample_prompts
        else:
            # Generate default prompts using trigger word (character-focused)
            tw = config.trigger_word
            default_prompts = (
                f"portrait photo of {tw}, front view, neutral background, soft lighting|"
                f"full body shot of {tw}, standing pose, studio lighting|"
                f"close up face of {tw}, detailed features, professional photo|"
                f"{tw} in a dynamic action pose, cinematic lighting"
            )
            workflow[self.NODES["sample_prompts"]]["inputs"]["string"] = default_prompts

        return workflow

    def start_training(
        self,
        config: TrainingConfig,
        callback: Optional[Callable[[float, str], None]] = None,
    ) -> TrainingResult:
        """
        Start a LoRA training run.

        Args:
            config: Training configuration
            callback: Progress callback(progress_pct, status_text)

        Returns:
            TrainingResult with output paths or error
        """
        start_time = time.time()

        # Validate inputs
        if not config.dataset_path:
            return TrainingResult(
                success=False,
                error="Dataset-Pfad fehlt"
            )

        if not config.trigger_word:
            return TrainingResult(
                success=False,
                error="Trigger-Wort fehlt"
            )

        if not config.output_name:
            return TrainingResult(
                success=False,
                error="Ausgabe-Name fehlt"
            )

        # Validate dataset
        is_valid, msg, image_count = self.validate_dataset(config.dataset_path)
        if not is_valid:
            return TrainingResult(
                success=False,
                error=f"Dataset ungültig: {msg}"
            )

        logger.info(f"Dataset validated: {msg}")

        try:
            if callback:
                callback(0.05, "Lade Workflow...")

            # Get output directory
            output_dir = self._get_output_dir(config.output_name)

            # Load and configure workflow
            workflow = self._load_workflow()
            workflow = self._configure_workflow(workflow, config, output_dir)

            if callback:
                callback(0.1, f"Starte Training ({config.total_steps} Steps, {image_count} Bilder)...")

            # Queue the workflow
            prompt_id = self.api.queue_prompt(workflow)
            logger.info(f"Queued LoRA training: {prompt_id}")

            # Monitor progress
            def progress_wrapper(pct, status):
                if callback:
                    # Scale progress: 10% loading, 85% training, 5% saving
                    scaled = 0.1 + (pct * 0.85)
                    callback(scaled, status)

            result = self.api.monitor_progress(
                prompt_id,
                callback=progress_wrapper,
                timeout=7200  # 2 hours max
            )

            if result["status"] != "success":
                return TrainingResult(
                    success=False,
                    output_dir=output_dir,
                    error=result.get("error", "Training fehlgeschlagen")
                )

            if callback:
                callback(0.98, "Sammle Ergebnisse...")

            # Find outputs
            duration = time.time() - start_time

            # Look for LoRA file in ComfyUI output
            lora_path = self._find_lora_output(config.output_name, output_dir)
            loss_plot = self._find_loss_plot(output_dir)
            validation_images = self._find_validation_images(output_dir)

            if callback:
                callback(1.0, "Training abgeschlossen!")

            return TrainingResult(
                success=True,
                lora_path=lora_path,
                output_dir=output_dir,
                total_steps=config.total_steps,
                duration_seconds=duration,
                loss_plot_path=loss_plot,
                validation_images=validation_images
            )

        except Exception as e:
            logger.error(f"LoRA training failed: {e}", exc_info=True)
            return TrainingResult(
                success=False,
                error=str(e)
            )

    def _find_lora_output(self, output_name: str, output_dir: str) -> Optional[str]:
        """Find the generated LoRA file."""
        # Check ComfyUI output directory
        comfy_root = self.config.get_comfy_root()

        # Common locations for LoRA outputs
        search_paths = [
            os.path.join(output_dir, f"{output_name}*.safetensors"),
            os.path.join(comfy_root, "output", f"{output_name}*.safetensors"),
            os.path.join(comfy_root, "models", "loras", f"{output_name}*.safetensors"),
        ]

        for pattern in search_paths:
            matches = glob.glob(pattern)
            if matches:
                # Return most recent
                return max(matches, key=os.path.getmtime)

        return None

    def _find_loss_plot(self, output_dir: str) -> Optional[str]:
        """Find the loss plot image."""
        comfy_root = self.config.get_comfy_root()

        patterns = [
            os.path.join(comfy_root, "output", "flux_lora_loss_plot*.png"),
            os.path.join(output_dir, "*loss*.png"),
        ]

        for pattern in patterns:
            matches = glob.glob(pattern)
            if matches:
                return max(matches, key=os.path.getmtime)

        return None

    def _find_validation_images(self, output_dir: str) -> List[str]:
        """Find validation preview images."""
        comfy_root = self.config.get_comfy_root()

        patterns = [
            os.path.join(comfy_root, "output", "flux_lora_trainer_sheet*.png"),
        ]

        images = []
        for pattern in patterns:
            images.extend(glob.glob(pattern))

        # Sort by modification time
        return sorted(images, key=os.path.getmtime, reverse=True)[:5]

    def list_available_datasets(self) -> List[Dict[str, Any]]:
        """List available training datasets from character trainer output."""
        datasets = []

        # Check character training output directory under ComfyUI
        comfy_root = self.config.get_comfy_root()
        char_training_dir = os.path.join(comfy_root, "output/character_training")

        if os.path.exists(char_training_dir):
            for entry in os.listdir(char_training_dir):
                # Skip temp folder (contains backups)
                if entry == "temp":
                    continue

                entry_path = os.path.join(char_training_dir, entry)
                if os.path.isdir(entry_path):
                    is_valid, msg, count = self.validate_dataset(entry_path)
                    # Store relative path for training (relative to ComfyUI root)
                    relative_path = f"output/character_training/{entry}"
                    datasets.append({
                        "name": entry,
                        "path": entry_path,  # Full path for validation
                        "relative_path": relative_path,  # Relative path for training
                        "valid": is_valid,
                        "image_count": count,
                        "message": msg
                    })

        return sorted(datasets, key=lambda d: d["name"], reverse=True)

    def get_relative_dataset_path(self, absolute_path: str) -> str:
        """Convert absolute dataset path to relative path for training."""
        comfy_root = self.config.get_comfy_root()
        if absolute_path.startswith(comfy_root):
            return absolute_path[len(comfy_root):].lstrip("/")
        # If not under ComfyUI, return as-is (might not work)
        return absolute_path


__all__ = [
    "LoraTrainerService",
    "TrainingConfig",
    "TrainingPreset",
    "TrainingResult",
    "TrainingProgress",
    "VRAMPreset",
    "TRAINING_PRESETS",
    "VRAM_RESOLUTION_CONFIG",
]
