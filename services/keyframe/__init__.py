"""Keyframe Generation Package - Modular keyframe generation.

This package provides keyframe generation using ComfyUI workflows.

Modules:
- file_handler: Image copy and cleanup operations
- checkpoint_handler: Progress tracking and persistence
- workflow_utils: LoRA and workflow selection
"""

from .file_handler import KeyframeFileHandler
from .checkpoint_handler import (
    CheckpointHandler,
    create_checkpoint,
    format_progress,
)
from .workflow_utils import (
    inject_model_override,
    get_workflow_for_shot,
    LoraParamsResolver,
)

__all__ = [
    # Classes
    "KeyframeFileHandler",
    "CheckpointHandler",
    "LoraParamsResolver",
    # Functions
    "create_checkpoint",
    "format_progress",
    "inject_model_override",
    "get_workflow_for_shot",
]
