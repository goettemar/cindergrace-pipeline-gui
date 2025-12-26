"""Kohya LoRA Trainer Models - Data classes and configuration types.

This module contains the data structures used by the Kohya trainer service.
Supports FLUX, SDXL, and SD3 LoRA training.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List


class KohyaTrainingStatus(Enum):
    """Training process status."""
    IDLE = "idle"
    PREPARING = "preparing"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


class KohyaModelType(Enum):
    """Supported model types for LoRA training."""
    FLUX = "flux"
    SDXL = "sdxl"
    SD3 = "sd3"


class KohyaVRAMPreset(Enum):
    """VRAM optimization presets for Kohya training."""
    VRAM_8GB = "8gb"    # SDXL/SD3 only
    VRAM_16GB = "16gb"
    VRAM_24GB = "24gb"


@dataclass
class KohyaTrainingConfig:
    """Training configuration for Kohya LoRA training."""
    # Required
    character_name: str
    images_dir: str
    trigger_word: str
    output_dir: str

    # Model type (FLUX, SDXL, SD3)
    model_type: KohyaModelType = KohyaModelType.FLUX

    # Model paths (auto-detected from ComfyUI)
    model_path: str = ""
    vae_path: str = ""          # Used by SDXL, SD3; FLUX uses 'ae'
    clip_l_path: str = ""       # FLUX, SD3 (separate)
    t5xxl_path: str = ""        # FLUX, SD3 only
    clip_g_path: str = ""       # SD3 only (SDXL has embedded)

    # Training parameters
    max_train_steps: int = 1500
    learning_rate: float = 1.0  # Prodigy auto-adjusts
    optimizer: str = "prodigy"
    mixed_precision: str = "bf16"

    # Network parameters
    network_dim: int = 16
    network_alpha: int = 8

    # VRAM optimization
    resolution: int = 512
    batch_size: int = 1
    gradient_accumulation: int = 4
    gradient_checkpointing: bool = True

    # Dataset
    num_repeats: int = 10
    caption_extension: str = ".txt"

    # Advanced
    save_every_n_steps: int = 500
    seed: int = 42

    # Sample generation during training
    sample_every_n_steps: int = 0  # 0 = disabled
    sample_prompt: str = ""  # Prompt for sample generation (uses trigger_word if empty)
    sample_sampler: str = "euler"  # euler, ddim, pndm, etc.


@dataclass
class KohyaTrainingProgress:
    """Current training progress."""
    status: KohyaTrainingStatus = KohyaTrainingStatus.IDLE
    current_step: int = 0
    total_steps: int = 0
    current_epoch: int = 0
    total_epochs: int = 0
    current_loss: float = 0.0
    average_loss: float = 0.0
    elapsed_time: float = 0.0
    eta_seconds: float = 0.0
    error_message: str = ""
    output_dir: str = ""  # Output directory for LoRAs and samples
    log_lines: List[str] = field(default_factory=list)


# Training scripts per model type
KOHYA_TRAINING_SCRIPTS: Dict[KohyaModelType, str] = {
    KohyaModelType.FLUX: "flux_train_network.py",
    KohyaModelType.SDXL: "sdxl_train_network.py",
    KohyaModelType.SD3: "sd3_train_network.py",
}

# Network modules per model type
KOHYA_NETWORK_MODULES: Dict[KohyaModelType, str] = {
    KohyaModelType.FLUX: "networks.lora_flux",
    KohyaModelType.SDXL: "networks.lora",
    KohyaModelType.SD3: "networks.lora_sd3",
}

# Valid VRAM presets per model type
KOHYA_VALID_PRESETS: Dict[KohyaModelType, List[KohyaVRAMPreset]] = {
    KohyaModelType.FLUX: [KohyaVRAMPreset.VRAM_16GB, KohyaVRAMPreset.VRAM_24GB],
    KohyaModelType.SDXL: [KohyaVRAMPreset.VRAM_8GB, KohyaVRAMPreset.VRAM_16GB, KohyaVRAMPreset.VRAM_24GB],
    KohyaModelType.SD3: [KohyaVRAMPreset.VRAM_8GB, KohyaVRAMPreset.VRAM_16GB, KohyaVRAMPreset.VRAM_24GB],
}

# VRAM Preset configurations per model type
# Format: KOHYA_VRAM_PRESETS[model_type][vram_preset]
KOHYA_VRAM_PRESETS: Dict[KohyaModelType, Dict[KohyaVRAMPreset, Dict[str, Any]]] = {
    # ==================== FLUX Presets ====================
    KohyaModelType.FLUX: {
        KohyaVRAMPreset.VRAM_16GB: {
            "resolution": 512,
            "batch_size": 1,
            "gradient_accumulation": 4,
            "gradient_checkpointing": True,
            "mixed_precision": "bf16",
            "optimizer": "prodigy",
            "network_dim": 16,
            "network_alpha": 8,
            "learning_rate": 1.0,
            "max_train_steps": 1500,
            "blocks_to_swap": 20,
            "t5xxl_max_token_length": 512,
            "description": "FLUX 16GB (RTX 5060 Ti, 4080) - 512px, Prodigy",
        },
        KohyaVRAMPreset.VRAM_24GB: {
            "resolution": 768,
            "batch_size": 1,
            "gradient_accumulation": 2,
            "gradient_checkpointing": True,
            "mixed_precision": "bf16",
            "optimizer": "adamw8bit",
            "network_dim": 32,
            "network_alpha": 16,
            "learning_rate": 1e-4,
            "max_train_steps": 2000,
            "blocks_to_swap": 0,
            "t5xxl_max_token_length": 512,
            "description": "FLUX 24GB+ (RTX 4090, 3090) - 768px, AdamW8bit",
        },
    },
    # ==================== SDXL Presets ====================
    KohyaModelType.SDXL: {
        KohyaVRAMPreset.VRAM_8GB: {
            "resolution": 512,
            "batch_size": 1,
            "gradient_accumulation": 4,
            "gradient_checkpointing": True,
            "mixed_precision": "bf16",
            "optimizer": "prodigy",
            "network_dim": 8,
            "network_alpha": 4,
            "learning_rate": 0.5,
            "max_train_steps": 1000,
            "description": "SDXL 8GB (RTX 3060, 4060 Ti) - 512px, Prodigy",
        },
        KohyaVRAMPreset.VRAM_16GB: {
            "resolution": 768,
            "batch_size": 1,
            "gradient_accumulation": 2,
            "gradient_checkpointing": True,
            "mixed_precision": "bf16",
            "optimizer": "adamw8bit",
            "network_dim": 16,
            "network_alpha": 8,
            "learning_rate": 1e-4,
            "max_train_steps": 1500,
            "description": "SDXL 16GB (RTX 4080, 5060 Ti) - 768px, AdamW8bit",
        },
        KohyaVRAMPreset.VRAM_24GB: {
            "resolution": 1024,
            "batch_size": 1,
            "gradient_accumulation": 1,
            "gradient_checkpointing": True,
            "mixed_precision": "bf16",
            "optimizer": "adamw8bit",
            "network_dim": 32,
            "network_alpha": 16,
            "learning_rate": 1e-4,
            "max_train_steps": 2000,
            "description": "SDXL 24GB+ (RTX 4090, 3090) - 1024px, AdamW8bit",
        },
    },
    # ==================== SD3 Presets ====================
    KohyaModelType.SD3: {
        KohyaVRAMPreset.VRAM_8GB: {
            "resolution": 512,
            "batch_size": 1,
            "gradient_accumulation": 4,
            "gradient_checkpointing": True,
            "mixed_precision": "bf16",
            "optimizer": "prodigy",
            "network_dim": 12,
            "network_alpha": 6,
            "learning_rate": 0.5,
            "max_train_steps": 1000,
            "blocks_to_swap": 18,
            "t5xxl_max_token_length": 256,
            "description": "SD3 8GB (RTX 3060, 4060 Ti) - 512px, Prodigy",
        },
        KohyaVRAMPreset.VRAM_16GB: {
            "resolution": 768,
            "batch_size": 1,
            "gradient_accumulation": 2,
            "gradient_checkpointing": True,
            "mixed_precision": "bf16",
            "optimizer": "adamw8bit",
            "network_dim": 24,
            "network_alpha": 12,
            "learning_rate": 1e-4,
            "max_train_steps": 1500,
            "blocks_to_swap": 10,
            "t5xxl_max_token_length": 256,
            "description": "SD3 16GB (RTX 4080, 5060 Ti) - 768px, AdamW8bit",
        },
        KohyaVRAMPreset.VRAM_24GB: {
            "resolution": 1024,
            "batch_size": 1,
            "gradient_accumulation": 1,
            "gradient_checkpointing": True,
            "mixed_precision": "bf16",
            "optimizer": "adamw8bit",
            "network_dim": 32,
            "network_alpha": 16,
            "learning_rate": 1e-4,
            "max_train_steps": 2000,
            "blocks_to_swap": 0,
            "t5xxl_max_token_length": 512,
            "description": "SD3 24GB+ (RTX 4090, 3090) - 1024px, AdamW8bit",
        },
    },
}


def get_vram_preset(
    model_type: KohyaModelType,
    vram_preset: KohyaVRAMPreset
) -> Dict[str, Any]:
    """Get VRAM preset configuration for a specific model type.

    Args:
        model_type: The model type (FLUX, SDXL, SD3)
        vram_preset: The VRAM preset (8GB, 16GB, 24GB)

    Returns:
        Dictionary with preset configuration

    Raises:
        ValueError: If the preset is not valid for the model type
    """
    if model_type not in KOHYA_VRAM_PRESETS:
        raise ValueError(f"Unknown model type: {model_type}")

    model_presets = KOHYA_VRAM_PRESETS[model_type]

    if vram_preset not in model_presets:
        valid = [p.value for p in KOHYA_VALID_PRESETS.get(model_type, [])]
        raise ValueError(
            f"VRAM preset {vram_preset.value} not available for {model_type.value}. "
            f"Valid presets: {valid}"
        )

    return model_presets[vram_preset]
