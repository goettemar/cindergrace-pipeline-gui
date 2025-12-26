"""Keyframe Checkpoint Handler - Progress tracking and persistence.

Manages generation checkpoints for pause/resume functionality.
"""

import os
import json
from datetime import datetime
from typing import Dict, Any

from infrastructure.logger import get_logger

logger = get_logger(__name__)


def create_checkpoint(
    storyboard_file: str,
    workflow_file: str,
    variants_per_shot: int,
    base_seed: int
) -> Dict[str, Any]:
    """Create a new generation checkpoint.

    Args:
        storyboard_file: Path to storyboard file
        workflow_file: Workflow template filename
        variants_per_shot: Number of variants per shot
        base_seed: Base random seed

    Returns:
        New checkpoint dictionary
    """
    return {
        "storyboard_file": storyboard_file,
        "workflow_file": workflow_file,
        "variants_per_shot": int(variants_per_shot),
        "base_seed": int(base_seed),
        "started_at": datetime.now().isoformat(),
        "completed_shots": [],
        "current_shot": None,
        "total_images_generated": 0,
        "status": "running",
    }


def format_progress(checkpoint: Dict[str, Any], total_shots: int) -> str:
    """Format progress details as markdown.

    Args:
        checkpoint: Current checkpoint state
        total_shots: Total number of shots

    Returns:
        Markdown formatted progress string
    """
    completed = len(checkpoint.get("completed_shots", []))
    total_images = checkpoint.get("total_images_generated", 0)
    current_shot = checkpoint.get("current_shot", "None")
    status = checkpoint.get("status", "unknown")

    progress_md = f"""### Progress

- **Status:** {status}
- **Completed Shots:** {completed}/{total_shots}
- **Total Images Generated:** {total_images}
- **Current Shot:** {current_shot}
- **Started:** {checkpoint.get('started_at', 'N/A')}
"""

    if status == "completed":
        progress_md += f"- **Completed:** {checkpoint.get('completed_at', 'N/A')}\n"

    return progress_md


class CheckpointHandler:
    """Handles checkpoint persistence."""

    def __init__(self, project_store):
        """Initialize checkpoint handler.

        Args:
            project_store: ProjectStore for directory access
        """
        self.project_store = project_store

    def save(
        self,
        checkpoint: Dict[str, Any],
        storyboard_file: str,
        project: Dict[str, Any]
    ):
        """Save checkpoint to file.

        Args:
            checkpoint: Checkpoint data
            storyboard_file: Storyboard filename
            project: Project metadata
        """
        try:
            checkpoint_dir = self.project_store.ensure_dir(project, "checkpoints")
            # Use only the filename, not the full path
            storyboard_filename = os.path.basename(storyboard_file)
            checkpoint_file = os.path.join(checkpoint_dir, f"checkpoint_{storyboard_filename}")

            with open(checkpoint_file, "w") as f:
                json.dump(checkpoint, f, indent=2)

            logger.debug(f"Checkpoint saved: {checkpoint_file}")

        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}", exc_info=True)

    def load(
        self,
        storyboard_file: str,
        project: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Load checkpoint from file.

        Args:
            storyboard_file: Storyboard filename
            project: Project metadata

        Returns:
            Checkpoint data or empty dict if not found
        """
        try:
            checkpoint_dir = self.project_store.ensure_dir(project, "checkpoints")
            storyboard_filename = os.path.basename(storyboard_file)
            checkpoint_file = os.path.join(checkpoint_dir, f"checkpoint_{storyboard_filename}")

            if os.path.exists(checkpoint_file):
                with open(checkpoint_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load checkpoint: {e}")

        return {}
