"""Kohya LoRA Trainer Package - Modular training orchestration.

This package provides a clean interface to train character LoRAs using
Kohya sd-scripts (sd3 branch) directly via subprocess.

Modules:
- models: Data classes and enums
- config_builder: TOML configuration generation
- model_scanner: Model discovery in ComfyUI
- training_runner: Subprocess management
"""

from .models import (
    KohyaTrainingStatus,
    KohyaModelType,
    KohyaVRAMPreset,
    KohyaTrainingConfig,
    KohyaTrainingProgress,
    KOHYA_VRAM_PRESETS,
    KOHYA_TRAINING_SCRIPTS,
    KOHYA_NETWORK_MODULES,
    KOHYA_VALID_PRESETS,
    get_vram_preset,
)
from .config_builder import KohyaConfigBuilder
from .model_scanner import KohyaModelScanner
from .training_runner import KohyaTrainingRunner

__all__ = [
    # Enums
    "KohyaTrainingStatus",
    "KohyaModelType",
    "KohyaVRAMPreset",
    # Data classes
    "KohyaTrainingConfig",
    "KohyaTrainingProgress",
    # Constants
    "KOHYA_VRAM_PRESETS",
    "KOHYA_TRAINING_SCRIPTS",
    "KOHYA_NETWORK_MODULES",
    "KOHYA_VALID_PRESETS",
    # Functions
    "get_vram_preset",
    # Classes
    "KohyaConfigBuilder",
    "KohyaModelScanner",
    "KohyaTrainingRunner",
]
