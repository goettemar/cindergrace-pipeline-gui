"""Keyframe Workflow Utilities - LoRA and workflow selection.

Handles workflow modification and LoRA parameter injection.
"""

import os
import copy
from typing import Dict, Any, Optional

from infrastructure.logger import get_logger

logger = get_logger(__name__)


def inject_model_override(workflow: Dict[str, Any], model_path: str) -> Dict[str, Any]:
    """Inject a model override into the workflow's model loader nodes.

    Supports:
    - UNETLoader (for Flux, etc.)
    - UnetLoaderGGUF (for GGUF models)
    - CheckpointLoaderSimple (for LTX-Video, SD, etc.)

    Only updates nodes with [MODEL] marker in title to avoid overwriting
    unrelated loaders (like T5 text encoders).

    Args:
        workflow: Workflow dictionary
        model_path: Model path relative to ComfyUI/models/

    Returns:
        Modified workflow with model override applied
    """
    workflow = copy.deepcopy(workflow)

    # Extract just the filename from the path
    model_filename = os.path.basename(model_path)

    nodes_updated = 0
    for node_id, node_data in workflow.items():
        if not isinstance(node_data, dict):
            continue

        class_type = node_data.get("class_type", "")
        inputs = node_data.get("inputs", {})
        title = node_data.get("_meta", {}).get("title", "")

        # Only update nodes with [MODEL] marker in title
        if not title.startswith("[MODEL"):
            continue

        # Update UNETLoader nodes
        if class_type == "UNETLoader" and "unet_name" in inputs:
            old_model = inputs["unet_name"]
            inputs["unet_name"] = model_filename
            nodes_updated += 1
            logger.debug(f"UNETLoader node {node_id}: {old_model} → {model_filename}")

        # Update UnetLoaderGGUF nodes
        elif class_type == "UnetLoaderGGUF" and "unet_name" in inputs:
            old_model = inputs["unet_name"]
            inputs["unet_name"] = model_filename
            nodes_updated += 1
            logger.debug(f"UnetLoaderGGUF node {node_id}: {old_model} → {model_filename}")

        # Update CheckpointLoaderSimple nodes (LTX-Video, SD, etc.)
        elif class_type == "CheckpointLoaderSimple" and "ckpt_name" in inputs:
            old_model = inputs["ckpt_name"]
            inputs["ckpt_name"] = model_filename
            nodes_updated += 1
            logger.debug(f"CheckpointLoaderSimple node {node_id}: {old_model} → {model_filename}")

    if nodes_updated > 0:
        logger.info(f"Updated {nodes_updated} model loader node(s) with: {model_filename}")
    else:
        logger.warning("No [MODEL] marked loader nodes found in workflow - model override not applied")

    return workflow


def get_workflow_for_shot(
    shot: Dict[str, Any],
    base_workflow_file: str,
    workflow_dir: str
) -> str:
    """Determine which workflow to use for a shot based on character_lora.

    Args:
        shot: Shot dictionary
        base_workflow_file: Base workflow filename (e.g., "gc_flux1_krea_dev.json")
        workflow_dir: Directory containing workflow templates

    Returns:
        Workflow filename - either base workflow or LoRA variant
    """
    character_lora = shot.get("character_lora")

    # Also check legacy characters array
    if not character_lora or character_lora == "none":
        characters = shot.get("characters", [])
        if characters:
            character_lora = characters[0] if isinstance(characters[0], str) else characters[0].get("id", "")

    if character_lora and character_lora != "none":
        # Need LoRA workflow - try to find the _lora variant
        base_name = base_workflow_file.replace(".json", "")
        lora_workflow = f"{base_name}_lora.json"

        # Check if LoRA workflow exists
        lora_path = os.path.join(workflow_dir, lora_workflow)
        if os.path.exists(lora_path):
            logger.info(f"Using LoRA workflow: {lora_workflow}")
            return lora_workflow
        else:
            logger.warning(f"LoRA workflow not found: {lora_path}, using base workflow")

    return base_workflow_file


class LoraParamsResolver:
    """Resolves LoRA parameters for shots."""

    def __init__(self, character_lora_service):
        """Initialize LoRA params resolver.

        Args:
            character_lora_service: CharacterLoraService instance
        """
        self.character_lora_service = character_lora_service

    def get_lora_params_for_shot(self, shot: Dict[str, Any]) -> Dict[str, Any]:
        """Get LoRA parameters for a shot based on character_lora field.

        Args:
            shot: Shot dictionary with optional 'character_lora' or 'characters'

        Returns:
            Dictionary with lora_name param (empty dict if no character LoRA)
        """
        # Check new single-select character_lora field first
        character_lora = shot.get("character_lora")
        if character_lora and character_lora != "none":
            lora = self.character_lora_service.get_lora(character_lora)
            if lora:
                logger.info(f"Using character LoRA '{lora.lora_file}' for shot")
                return {
                    "lora_name": lora.lora_file,
                    "lora_strength": lora.strength
                }
            else:
                logger.warning(f"Character LoRA not found: {character_lora}")
                return {}

        # Fallback: Check legacy 'characters' array
        characters = shot.get("characters", [])
        if characters:
            character_id = characters[0] if isinstance(characters[0], str) else characters[0].get("id", "")
            if character_id:
                lora = self.character_lora_service.get_lora(character_id)
                if lora:
                    logger.info(f"Using legacy character LoRA '{lora.lora_file}' for shot")
                    return {
                        "lora_name": lora.lora_file,
                        "lora_strength": lora.strength
                    }

        # No character LoRA - return empty
        return {}
