"""Service layer for keyframe generation (Phase 1)."""
import os
from datetime import datetime
from typing import Dict, Any, List, Tuple

from infrastructure.project_store import ProjectStore
from infrastructure.workflow_registry import WorkflowRegistry
from infrastructure.config_manager import ConfigManager
from infrastructure.comfy_api import ComfyUIAPI
from domain.models import Storyboard


class KeyframeService:
    """Encapsulate logic for running Flux keyframe generation."""

    def __init__(
        self,
        project_store: ProjectStore,
        config: ConfigManager,
        workflow_registry: WorkflowRegistry
    ):
        self.project_store = project_store
        self.config = config
        self.workflow_registry = workflow_registry

    def prepare_checkpoint(
        self,
        storyboard: Storyboard,
        workflow_file: str,
        variants_per_shot: int,
        base_seed: int
    ) -> Dict[str, Any]:
        return {
            "storyboard_file": storyboard.raw.get("storyboard_file"),
            "workflow_file": workflow_file,
            "variants_per_shot": int(variants_per_shot),
            "base_seed": int(base_seed),
            "started_at": datetime.now().isoformat(),
            "completed_shots": [],
            "current_shot": None,
            "total_images_generated": 0,
            "status": "running",
        }


__all__ = ["KeyframeService"]
