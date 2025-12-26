"""Keyframe File Handler - Image copy and cleanup operations.

Handles moving generated images from ComfyUI output to project directory.
"""

import os
import glob
import shutil
from datetime import datetime
from typing import List, Dict, Any

from infrastructure.logger import get_logger

logger = get_logger(__name__)


class KeyframeFileHandler:
    """Handles file operations for keyframe generation."""

    def __init__(self, project_store):
        """Initialize file handler.

        Args:
            project_store: ProjectStore for directory access
        """
        self.project_store = project_store

    def copy_generated_images(
        self,
        variant_name: str,
        output_dir: str,
        api_result: Dict[str, Any],
        max_retries: int = 30,
        retry_delay: float = 1.0
    ) -> List[str]:
        """Move generated images from ComfyUI output to project directory.

        Includes retry mechanism to handle race condition where ComfyUI reports
        success via WebSocket before the file is fully written to disk.

        Args:
            variant_name: Base name for the variant files
            output_dir: Destination directory
            api_result: Result from ComfyUI API
            max_retries: Number of retries to find files
            retry_delay: Delay between retries in seconds

        Returns:
            List of moved image paths
        """
        import time
        moved_images = []

        try:
            comfy_output = self.project_store.comfy_output_dir()

            # Try multiple patterns to find the images
            patterns = [
                os.path.join(comfy_output, f"{variant_name}_*.png"),
                os.path.join(comfy_output, f"{variant_name}*.png"),
            ]

            logger.debug(f"Searching for images matching '{variant_name}' in {comfy_output}")

            # Retry loop to wait for file to appear on disk
            for attempt in range(max_retries):
                seen_sources = set()
                seen_destinations = set()

                for pattern in patterns:
                    matches = glob.glob(pattern)

                    for src in matches:
                        if src in seen_sources:
                            continue
                        seen_sources.add(src)

                        dest = os.path.join(output_dir, os.path.basename(src))

                        if dest in seen_destinations:
                            logger.warning(f"Skipping duplicate destination: {dest}")
                            continue
                        seen_destinations.add(dest)

                        # MOVE instead of copy to avoid duplicates
                        shutil.move(src, dest)
                        moved_images.append(dest)
                        logger.info(f"Moved image: {os.path.basename(src)} → {output_dir}")

                if moved_images:
                    break  # Found and moved files, exit retry loop

                if attempt < max_retries - 1:
                    logger.debug(f"No files found yet, retry {attempt + 1}/{max_retries} in {retry_delay}s")
                    time.sleep(retry_delay)

            if not moved_images:
                logger.warning(f"No images found for pattern '{variant_name}' after {max_retries} retries")
                logger.warning(f"Tried patterns: {patterns}")
                # List what's actually in the directory for debugging
                try:
                    all_files = [f for f in os.listdir(comfy_output) if f.endswith('.png')]
                    logger.debug(f"PNG files in {comfy_output}: {all_files[:10]}")
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Failed to move images for {variant_name}: {e}", exc_info=True)

        return moved_images

    def cleanup_old_files(self, filename_base: str) -> int:
        """Move leftover files from ComfyUI output directory to temp folder.

        This prevents picking up old files from failed/previous runs.
        Files are moved to output/temp/{timestamp}/ instead of deleted.

        Args:
            filename_base: Base filename for the shot (e.g., 'opening-scene')

        Returns:
            Number of files moved
        """
        try:
            comfy_output = self.project_store.comfy_output_dir()
            pattern = os.path.join(comfy_output, f"{filename_base}_v*_*.png")
            old_files = glob.glob(pattern)

            if old_files:
                # Create temp directory with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                temp_dir = os.path.join(comfy_output, "temp", timestamp)
                os.makedirs(temp_dir, exist_ok=True)

                logger.info(f"Moving {len(old_files)} old file(s) for '{filename_base}' to {temp_dir}")
                for old_file in old_files:
                    try:
                        dest = os.path.join(temp_dir, os.path.basename(old_file))
                        shutil.move(old_file, dest)
                        logger.debug(f"Moved old file: {old_file} → {temp_dir}")
                    except OSError as e:
                        logger.warning(f"Failed to move {old_file}: {e}")

            return len(old_files)

        except Exception as e:
            logger.error(f"Cleanup failed for {filename_base}: {e}")
            return 0
