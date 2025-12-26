"""Workflow Scanner - Extract model references from ComfyUI workflows"""
import os
import json
from typing import Dict, List, Set
from pathlib import Path

from infrastructure.logger import get_logger

logger = get_logger(__name__)


class WorkflowScanner:
    """Scans ComfyUI workflow files and extracts model references"""

    # Node types that reference models
    MODEL_NODE_TYPES = {
        "CheckpointLoaderSimple": "checkpoints",
        "CheckpointLoader": "checkpoints",
        "CheckpointLoaderNF4": "checkpoints",
        "LoraLoader": "loras",
        "LoraLoaderModelOnly": "loras",
        "VAELoader": "vae",
        "ControlNetLoader": "controlnet",
        "UpscaleModelLoader": "upscale_models",
        "CLIPLoader": "clip",
        "DualCLIPLoader": "clip",
        "UNETLoader": "diffusion_models",  # Most UNETs are in diffusion_models/
        "UnetLoaderGGUF": "diffusion_models",  # GGUF quantized models
        "StyleModelLoader": "style_models",
    }

    def __init__(self, workflows_dir: str):
        """
        Initialize workflow scanner

        Args:
            workflows_dir: Path to ComfyUI workflows directory
        """
        self.workflows_dir = Path(workflows_dir)
        self.logger = logger
        self._scan_cache = None  # Cache for scan_all_workflows results

    def scan_all_workflows(self, use_cache: bool = True) -> Dict[str, List[Dict[str, str]]]:
        """
        Scan all workflows in directory

        Args:
            use_cache: If True, use cached results if available

        Returns:
            Dict mapping workflow filename to list of model references
            Format: {
                "workflow1.json": [
                    {"type": "checkpoints", "filename": "model.safetensors", "node_id": "4"},
                    ...
                ]
            }
        """
        # Return cached results if available
        if use_cache and self._scan_cache is not None:
            return self._scan_cache

        results = {}

        if not self.workflows_dir.exists():
            self.logger.warning(f"Workflows directory does not exist: {self.workflows_dir}")
            return results

        # Find all JSON files
        workflow_files = list(self.workflows_dir.glob("*.json"))
        workflow_files.extend(self.workflows_dir.glob("**/*.json"))

        self.logger.info(f"Scanning {len(workflow_files)} workflow files...")

        for workflow_file in workflow_files:
            try:
                models = self.scan_workflow(str(workflow_file))
                if models:
                    results[workflow_file.name] = models
                    self.logger.debug(f"Found {len(models)} model references in {workflow_file.name}")
            except Exception as e:
                self.logger.error(f"Failed to scan {workflow_file.name}: {e}")
                continue

        self.logger.info(f"Scanned {len(results)} workflows with model references")

        # Cache the results
        self._scan_cache = results
        return results

    def scan_workflow(self, workflow_path: str) -> List[Dict[str, str]]:
        """
        Scan a single workflow file for model references

        Args:
            workflow_path: Path to workflow JSON file

        Returns:
            List of model references found
        """
        models = []

        try:
            with open(workflow_path, 'r', encoding='utf-8') as f:
                workflow = json.load(f)

            if not isinstance(workflow, dict):
                self.logger.warning(f"Workflow {workflow_path} is not in expected format")
                return models

            # Determine workflow format and extract nodes
            nodes_to_scan = []

            if "nodes" in workflow and isinstance(workflow["nodes"], list):
                # UI format: {"nodes": [...], ...}
                nodes_to_scan = [(node.get("id"), node) for node in workflow["nodes"] if isinstance(node, dict)]
            else:
                # API format: {"1": {...}, "2": {...}, ...}
                nodes_to_scan = [(node_id, node_data) for node_id, node_data in workflow.items()
                                if isinstance(node_data, dict)]

            # Scan all nodes
            for node_id, node_data in nodes_to_scan:
                if not isinstance(node_data, dict):
                    continue

                # UI format uses "type", API format uses "class_type"
                class_type = node_data.get("class_type") or node_data.get("type", "")
                if class_type not in self.MODEL_NODE_TYPES:
                    continue

                # Extract model filename from inputs or widgets
                inputs = node_data.get("inputs", {})

                # UI format has inputs as list (connections) and widgets_values for actual values
                # API format has inputs as dict
                if isinstance(inputs, list) or not inputs:
                    # UI format - extract from widgets_values
                    inputs = self._extract_inputs_from_widgets(node_data, class_type)

                model_type = self.MODEL_NODE_TYPES[class_type]

                # Different node types use different input field names
                model_filename = self._extract_model_filename(inputs, class_type)

                if model_filename:
                    models.append({
                        "type": model_type,
                        "filename": model_filename,
                        "node_id": str(node_id),
                        "node_type": class_type,
                    })

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in {workflow_path}: {e}")
        except Exception as e:
            self.logger.error(f"Error scanning {workflow_path}: {e}", exc_info=True)

        return models

    def _extract_inputs_from_widgets(self, node_data: Dict, class_type: str) -> Dict:
        """
        Extract inputs from UI format widgets_values

        Args:
            node_data: Node data dictionary
            class_type: Node class type

        Returns:
            Inputs dictionary
        """
        inputs = {}
        widgets_values = node_data.get("widgets_values", [])

        if not widgets_values:
            return inputs

        # Map class types to expected widget positions
        # Most loaders have the model name as first widget value
        if widgets_values and len(widgets_values) > 0:
            model_value = widgets_values[0]
            if isinstance(model_value, str) and model_value:
                # Determine field name based on class type
                if "Checkpoint" in class_type:
                    inputs["ckpt_name"] = model_value
                elif "Lora" in class_type or "LoRA" in class_type:
                    inputs["lora_name"] = model_value
                elif "VAE" in class_type:
                    inputs["vae_name"] = model_value
                elif "ControlNet" in class_type:
                    inputs["control_net_name"] = model_value
                elif "CLIP" in class_type:
                    inputs["clip_name"] = model_value
                elif "UNET" in class_type:
                    inputs["unet_name"] = model_value
                elif "Style" in class_type:
                    inputs["style_model_name"] = model_value
                elif "Upscale" in class_type:
                    inputs["model_name"] = model_value

        return inputs

    def _extract_model_filename(self, inputs: Dict, class_type: str) -> str:
        """
        Extract model filename from node inputs

        Args:
            inputs: Node inputs dictionary
            class_type: Node class type

        Returns:
            Model filename or empty string
        """
        # Common field names for model references
        field_names = [
            "ckpt_name",      # Checkpoints
            "checkpoint",
            "lora_name",      # LoRAs
            "vae_name",       # VAEs
            "control_net_name",  # ControlNet
            "model_name",     # Generic
            "clip_name",      # CLIP
            "clip_name1",     # DualCLIPLoader first clip
            "clip_name2",     # DualCLIPLoader second clip
            "unet_name",      # UNET
            "style_model_name",  # Style models
        ]

        for field_name in field_names:
            if field_name in inputs:
                value = inputs[field_name]
                if isinstance(value, str) and value:
                    return value

        # If no standard field found, log for debugging
        if inputs:
            self.logger.debug(f"Could not find model filename in {class_type} inputs: {list(inputs.keys())}")

        return ""

    def get_all_referenced_models(self) -> Dict[str, Set[str]]:
        """
        Get all unique model filenames referenced across all workflows

        Returns:
            Dict mapping model type to set of filenames
            Format: {
                "checkpoints": {"model1.safetensors", "model2.ckpt"},
                "loras": {"lora1.safetensors"},
                ...
            }
        """
        all_workflows = self.scan_all_workflows()

        # Aggregate by type
        models_by_type: Dict[str, Set[str]] = {}

        for workflow_name, models in all_workflows.items():
            for model_ref in models:
                model_type = model_ref["type"]
                filename = model_ref["filename"]

                if model_type not in models_by_type:
                    models_by_type[model_type] = set()

                models_by_type[model_type].add(filename)

        return models_by_type

    def get_workflows_using_model(self, model_filename: str) -> List[str]:
        """
        Find all workflows that reference a specific model

        Args:
            model_filename: Model filename to search for

        Returns:
            List of workflow filenames that use this model
        """
        all_workflows = self.scan_all_workflows()
        workflows_using_model = []

        for workflow_name, models in all_workflows.items():
            for model_ref in models:
                if model_ref["filename"] == model_filename:
                    workflows_using_model.append(workflow_name)
                    break  # Only add workflow once

        return workflows_using_model
