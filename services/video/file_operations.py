"""Video File Operations - Copy and cleanup for video generation.

Handles moving generated videos and last frame images from ComfyUI
output to project directories.
"""

import os
import re
import glob
import shutil
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

from infrastructure.logger import get_logger

logger = get_logger(__name__)


class VideoFileHandler:
    """Handles file operations for video generation."""

    def __init__(self, project_store, config=None):
        """Initialize file handler.

        Args:
            project_store: ProjectStore for directory access
            config: Optional ConfigManager for timeout settings
        """
        self.project_store = project_store
        self.config = config or (project_store.config if hasattr(project_store, 'config') else None)

    def copy_video_outputs(
        self,
        entry: Dict[str, Any],
        project: Dict[str, Any]
    ) -> List[str]:
        """Copy generated video files from ComfyUI/output to project/video folder.

        Includes retry mechanism to handle race condition where ComfyUI reports
        success via WebSocket before the file is fully written to disk.

        Args:
            entry: Plan segment
            project: Project metadata

        Returns:
            List of copied video file paths
        """
        # Get timeout values from config (or use defaults)
        initial_wait = 60  # default: 60s before first check
        retry_delay = 30.0  # default: 30s between checks
        max_retries = 20  # default: 20 retries

        if self.config:
            initial_wait = self.config.get_video_initial_wait()
            retry_delay = float(self.config.get_video_retry_delay())
            max_retries = self.config.get_video_max_retries()

        try:
            comfy_output = self.project_store.comfy_output_dir()
        except FileNotFoundError as exc:
            logger.warning(f"ComfyUI output directory not found: {exc}")
            return []

        dest_dir = self.project_store.ensure_dir(project, "video")

        extensions = ("mp4", "webm", "mov", "gif")
        clip_name = entry.get("clip_name") or entry.get("filename_base") or entry.get("shot_id", "clip")
        base_name = entry.get("filename_base", clip_name)
        project_path = project.get("path", "")

        # Initial wait before first check (video encoding takes time)
        logger.info(f"Waiting {initial_wait}s for video encoding to complete...")
        time.sleep(initial_wait)

        # Retry loop to wait for video file to appear on disk
        logger.info(f"Searching for video files with clip_name='{clip_name}' in {comfy_output}")

        for attempt in range(max_retries):
            copied: List[str] = []
            seen = set()

            for ext in extensions:
                patterns = [
                    os.path.join(comfy_output, f"{clip_name}*.{ext}"),
                    os.path.join(comfy_output, "video", f"{clip_name}*.{ext}"),
                    # Fallback to ComfyUI default naming
                    os.path.join(comfy_output, "video", f"ComfyUI_*.{ext}"),
                ]

                for pattern in patterns:
                    matches = glob.glob(pattern)
                    if matches:
                        logger.info(f"Pattern '{pattern}' found {len(matches)} files: {matches}")
                    for src in matches:
                        if src in seen:
                            logger.debug(f"Skipping duplicate: {src}")
                            continue
                        # Skip files already in project directory
                        if project_path and os.path.commonpath([src, project_path]) == project_path:
                            logger.debug(f"Skipping file in project path: {src}")
                            continue

                        seen.add(src)
                        dest_filename = self._build_video_filename(base_name, entry, ext, dest_dir)
                        dest = os.path.join(dest_dir, dest_filename)
                        logger.info(f"Moving video from {src} to {dest}")
                        try:
                            # MOVE instead of copy to avoid picking up same file for next shot
                            shutil.move(src, dest)
                            copied.append(dest)
                            logger.info(f"✓ Successfully moved video: {src} → {dest}")
                        except Exception as move_error:
                            logger.error(f"Failed to move {src} to {dest}: {move_error}")

            if copied:
                return copied

            if attempt < max_retries - 1:
                # Log status on each retry (every 30s)
                try:
                    all_files = os.listdir(comfy_output)
                    video_files = [f for f in all_files if f.endswith(('.mp4', '.webm', '.mov', '.gif'))]
                    elapsed = initial_wait + (attempt + 1) * retry_delay
                    logger.info(f"Check {attempt + 1}/{max_retries} ({elapsed:.0f}s elapsed): Looking for '{clip_name}*', videos in output: {video_files}")
                except Exception:
                    pass
                time.sleep(retry_delay)

        total_wait = initial_wait + max_retries * retry_delay
        logger.warning(f"No video files found for '{clip_name}' after {total_wait:.0f}s total wait")
        return []

    def _build_video_filename(
        self,
        base_name: str,
        entry: Dict[str, Any],
        ext: str,
        dest_dir: str
    ) -> str:
        """Generate readable filename for exported clips."""
        safe_base = re.sub(r"[^a-zA-Z0-9_-]+", "_", base_name) or entry.get("clip_name", "clip")
        variant = entry.get("selected_variant")

        # Start with variant suffix if available, otherwise plain name
        if variant:
            candidate = f"{safe_base}_v{variant}.{ext}"
        else:
            candidate = f"{safe_base}.{ext}"

        # Add counter to ensure uniqueness if file already exists
        counter = 2
        base_candidate = candidate.replace(f".{ext}", "")
        while os.path.exists(os.path.join(dest_dir, candidate)):
            candidate = f"{base_candidate}_{counter}.{ext}"
            counter += 1

        return candidate

    def copy_last_frame_output(
        self,
        entry: Dict[str, Any],
        project: Dict[str, Any],
    ) -> Optional[str]:
        """Copy the last frame image from ComfyUI output to project folder.

        The SaveImage node saves with pattern: {clip_name}_lastframe_00001.png
        This method finds and copies it for use in chaining.

        Args:
            entry: Plan segment entry
            project: Project metadata

        Returns:
            Path to copied last frame, or None if not found
        """
        try:
            comfy_output = self.project_store.comfy_output_dir()
        except FileNotFoundError as exc:
            logger.warning(f"ComfyUI output directory not found: {exc}")
            return None

        # Create lastframes directory in project
        dest_dir = self.project_store.ensure_dir(project, "lastframes")

        clip_name = entry.get("clip_name") or entry.get("filename_base") or entry.get("shot_id", "clip")
        # Sanitize clip_name
        safe_clip_name = re.sub(r"[^\w\-]+", "_", clip_name)

        # Wait a bit for file to be written (much shorter than video wait)
        time.sleep(2)

        # Search patterns for last frame images
        image_extensions = ("png", "jpg", "jpeg")
        patterns = []
        for ext in image_extensions:
            # Pattern: {safe_clip_name}_lastframe_00001.png
            patterns.append(os.path.join(comfy_output, f"{safe_clip_name}_lastframe*.{ext}"))
            # Also check without underscore in case of different naming
            patterns.append(os.path.join(comfy_output, f"{safe_clip_name}lastframe*.{ext}"))

        # Try to find the last frame image
        for attempt in range(5):  # Max 5 attempts, 2 sec each
            for pattern in patterns:
                matches = glob.glob(pattern)
                if matches:
                    # Take the most recent file
                    src = max(matches, key=os.path.getmtime)
                    logger.info(f"Found last frame: {src}")

                    # Build destination filename
                    segment_index = entry.get("segment_index", 1)
                    dest_filename = f"{safe_clip_name}_seg{segment_index}_lastframe.png"
                    dest = os.path.join(dest_dir, dest_filename)

                    try:
                        # MOVE to prevent picking up same file again
                        shutil.move(src, dest)
                        logger.info(f"Last frame moved: {src} → {dest}")
                        return dest
                    except Exception as move_error:
                        logger.error(f"Failed to move last frame: {move_error}")
                        # Try copy as fallback
                        try:
                            shutil.copy2(src, dest)
                            os.remove(src)
                            return dest
                        except Exception:
                            pass

            if attempt < 4:
                time.sleep(2)

        logger.warning(f"Last frame not found for {clip_name} after searching patterns: {patterns}")
        return None

    def cleanup_old_video_files(self) -> int:
        """Move leftover video and lastframe files from ComfyUI output to temp folder.

        Returns:
            Number of files moved
        """
        try:
            comfy_output = self.project_store.comfy_output_dir()
        except FileNotFoundError as exc:
            logger.warning(f"ComfyUI output directory not found: {exc}")
            return 0

        video_extensions = ("mp4", "webm", "mov", "gif")
        image_extensions = ("png", "jpg", "jpeg")
        moved_count = 0
        files_to_move = []

        # Get project video directory for cleanup
        try:
            project = self.project_store.get_active_project(refresh=True)
            project_video_dir = self.project_store.project_path(project, "video") if project else None
        except Exception:
            project_video_dir = None

        # Collect video files from multiple locations
        video_subdir = os.path.join(comfy_output, "video")

        search_dirs = [
            (comfy_output, video_extensions),
            (video_subdir, video_extensions),
        ]

        # Add project directory if available
        if isinstance(project_video_dir, (str, os.PathLike)) and os.path.exists(project_video_dir):
            search_dirs.append((project_video_dir, video_extensions))

        for search_dir, extensions in search_dirs:
            for ext in extensions:
                found_files = glob.glob(os.path.join(search_dir, f"*.{ext}"))
                # Skip _state.json and other non-media files
                found_files = [f for f in found_files if not f.endswith('.json')]
                if found_files:
                    logger.info(f"Cleanup: Found {len(found_files)} .{ext} files in {search_dir}")
                    files_to_move.extend(found_files)

        # Also cleanup lastframe images
        for ext in image_extensions:
            lastframe_pattern = os.path.join(comfy_output, f"*_lastframe*.{ext}")
            lastframe_files = glob.glob(lastframe_pattern)
            if lastframe_files:
                logger.info(f"Cleanup: Found {len(lastframe_files)} lastframe .{ext} files")
                files_to_move.extend(lastframe_files)

        if not files_to_move:
            return 0

        # Create temp directory with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_dir = os.path.join(comfy_output, "temp", timestamp)
        os.makedirs(temp_dir, exist_ok=True)

        logger.info(f"Moving {len(files_to_move)} old video file(s) to {temp_dir}")

        for old_file in files_to_move:
            try:
                dest = os.path.join(temp_dir, os.path.basename(old_file))
                shutil.move(old_file, dest)
                moved_count += 1
                logger.debug(f"Moved old video file: {old_file} → {temp_dir}")
            except OSError as e:
                logger.warning(f"Failed to move {old_file}: {e}")

        return moved_count
