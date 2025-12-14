"""Model Classifier - Classify models into used/unused/missing categories"""
from typing import Dict, List, Set
from enum import Enum

from services.model_manager.workflow_scanner import WorkflowScanner
from services.model_manager.model_scanner import ModelScanner
from infrastructure.logger import get_logger

logger = get_logger(__name__)


class ModelStatus(str, Enum):
    """Model status categories"""
    USED = "used"  # Referenced in workflows AND exists on disk
    UNUSED = "unused"  # Exists on disk but NOT referenced in workflows
    MISSING = "missing"  # Referenced in workflows but NOT on disk


class ModelClassifier:
    """Classifies models into used/unused/missing categories"""

    def __init__(
        self,
        workflow_scanner: WorkflowScanner,
        model_scanner: ModelScanner
    ):
        """
        Initialize model classifier

        Args:
            workflow_scanner: WorkflowScanner instance
            model_scanner: ModelScanner instance
        """
        self.workflow_scanner = workflow_scanner
        self.model_scanner = model_scanner
        self.logger = logger

    def classify_all_models(self) -> Dict[str, List[Dict]]:
        """
        Classify all models across all types

        Returns:
            Dict with classified models by status
            Format: {
                "used": [
                    {
                        "type": "checkpoints",
                        "filename": "model.safetensors",
                        "size": "4.5 GB",
                        "workflows": ["workflow1.json", "workflow2.json"],
                        "path": "/full/path"
                    },
                    ...
                ],
                "unused": [...],
                "missing": [...]
            }
        """
        self.logger.info("Starting model classification...")

        # Get referenced models from workflows
        referenced_models = self.workflow_scanner.get_all_referenced_models()
        self.logger.info(f"Found {sum(len(v) for v in referenced_models.values())} model references in workflows")

        # Get existing models from filesystem
        existing_models = self.model_scanner.scan_all_models()
        self.logger.info(f"Found {sum(len(v) for v in existing_models.values())} model files on disk")

        # Classify
        classified = {
            ModelStatus.USED: [],
            ModelStatus.UNUSED: [],
            ModelStatus.MISSING: [],
        }

        # Process each model type
        all_model_types = set(referenced_models.keys()) | set(existing_models.keys())

        for model_type in all_model_types:
            referenced_set = referenced_models.get(model_type, set())
            existing_list = existing_models.get(model_type, [])

            # Create set of existing filenames for quick lookup
            existing_dict = {m["filename"]: m for m in existing_list}
            existing_set = set(existing_dict.keys())

            # USED: Referenced AND exists
            used_filenames = referenced_set & existing_set
            for filename in used_filenames:
                model_info = existing_dict[filename]
                workflows = self.workflow_scanner.get_workflows_using_model(filename)
                classified[ModelStatus.USED].append({
                    "status": ModelStatus.USED,
                    "type": model_type,
                    "filename": filename,
                    "size_bytes": model_info["size_bytes"],
                    "size": model_info["size_formatted"],
                    "path": model_info["path"],
                    "workflows": workflows,
                    "workflow_count": len(workflows),
                })

            # UNUSED: Exists but NOT referenced
            unused_filenames = existing_set - referenced_set
            for filename in unused_filenames:
                model_info = existing_dict[filename]
                classified[ModelStatus.UNUSED].append({
                    "status": ModelStatus.UNUSED,
                    "type": model_type,
                    "filename": filename,
                    "size_bytes": model_info["size_bytes"],
                    "size": model_info["size_formatted"],
                    "path": model_info["path"],
                    "workflows": [],
                    "workflow_count": 0,
                })

            # MISSING: Referenced but NOT exists
            missing_filenames = referenced_set - existing_set
            for filename in missing_filenames:
                workflows = self.workflow_scanner.get_workflows_using_model(filename)
                classified[ModelStatus.MISSING].append({
                    "status": ModelStatus.MISSING,
                    "type": model_type,
                    "filename": filename,
                    "size_bytes": 0,
                    "size": "N/A",
                    "path": None,
                    "workflows": workflows,
                    "workflow_count": len(workflows),
                })

        # Log summary
        self.logger.info(f"Classification complete:")
        self.logger.info(f"  - Used: {len(classified[ModelStatus.USED])} models")
        self.logger.info(f"  - Unused: {len(classified[ModelStatus.UNUSED])} models")
        self.logger.info(f"  - Missing: {len(classified[ModelStatus.MISSING])} models")

        return classified

    def get_statistics(self) -> Dict[str, any]:
        """
        Get classification statistics

        Returns:
            Statistics dictionary
        """
        classified = self.classify_all_models()

        # Calculate total sizes
        used_size = sum(m["size_bytes"] for m in classified[ModelStatus.USED])
        unused_size = sum(m["size_bytes"] for m in classified[ModelStatus.UNUSED])

        # Count by type
        types_used = {}
        types_unused = {}
        types_missing = {}

        for model in classified[ModelStatus.USED]:
            model_type = model["type"]
            types_used[model_type] = types_used.get(model_type, 0) + 1

        for model in classified[ModelStatus.UNUSED]:
            model_type = model["type"]
            types_unused[model_type] = types_unused.get(model_type, 0) + 1

        for model in classified[ModelStatus.MISSING]:
            model_type = model["type"]
            types_missing[model_type] = types_missing.get(model_type, 0) + 1

        return {
            "total_used": len(classified[ModelStatus.USED]),
            "total_unused": len(classified[ModelStatus.UNUSED]),
            "total_missing": len(classified[ModelStatus.MISSING]),
            "used_size_bytes": used_size,
            "used_size": ModelScanner._format_size(used_size),
            "unused_size_bytes": unused_size,
            "unused_size": ModelScanner._format_size(unused_size),
            "potential_savings": ModelScanner._format_size(unused_size),
            "by_type": {
                "used": types_used,
                "unused": types_unused,
                "missing": types_missing,
            }
        }

    def get_models_by_status(self, status: ModelStatus) -> List[Dict]:
        """
        Get all models with a specific status

        Args:
            status: ModelStatus to filter by

        Returns:
            List of models with that status
        """
        classified = self.classify_all_models()
        return classified.get(status, [])

    def get_models_by_type_and_status(
        self,
        model_type: str,
        status: ModelStatus
    ) -> List[Dict]:
        """
        Get models filtered by type and status

        Args:
            model_type: Model type (checkpoints, loras, etc.)
            status: ModelStatus to filter by

        Returns:
            Filtered list of models
        """
        all_models = self.get_models_by_status(status)
        return [m for m in all_models if m["type"] == model_type]
