"""Cleanup Service - Archive old files before new generation runs.

Provides centralized cleanup functionality for all generation services.
Files are moved to _archive/{timestamp}/ instead of deleted.
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from infrastructure.logger import get_logger
from infrastructure.project_store import ProjectStore

logger = get_logger(__name__)


class CleanupService:
    """Centralized cleanup service for archiving old generation outputs."""

    ARCHIVE_DIR = "_archive"

    # File extensions to archive per folder type
    KEYFRAME_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
    VIDEO_EXTENSIONS = (".mp4", ".webm", ".mov", ".gif")
    LORA_EXTENSIONS = (".safetensors", ".pt", ".ckpt")

    def __init__(self, project_store: ProjectStore):
        """Initialize cleanup service.

        Args:
            project_store: ProjectStore for directory access
        """
        self.project_store = project_store

    def _create_archive_dir(self, base_path: str) -> str:
        """Create timestamped archive directory.

        Args:
            base_path: Base path where archive should be created

        Returns:
            Path to created archive directory
        """
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        archive_path = os.path.join(base_path, self.ARCHIVE_DIR, timestamp)
        os.makedirs(archive_path, exist_ok=True)
        return archive_path

    def _archive_files(
        self,
        source_dir: str,
        extensions: Tuple[str, ...],
        subfolder: Optional[str] = None
    ) -> Tuple[int, str]:
        """Move files with specified extensions to archive.

        Args:
            source_dir: Directory to clean up
            extensions: File extensions to archive (e.g., (".png", ".jpg"))
            subfolder: Optional subfolder name in archive

        Returns:
            Tuple of (files_moved, archive_path)
        """
        if not os.path.exists(source_dir):
            return 0, ""

        # Find files to archive
        files_to_move = []
        for f in os.listdir(source_dir):
            if f.lower().endswith(extensions):
                files_to_move.append(os.path.join(source_dir, f))

        if not files_to_move:
            return 0, ""

        # Create archive directory
        archive_base = self._create_archive_dir(source_dir)
        if subfolder:
            archive_path = os.path.join(archive_base, subfolder)
            os.makedirs(archive_path, exist_ok=True)
        else:
            archive_path = archive_base

        # Move files
        moved_count = 0
        for src in files_to_move:
            try:
                dest = os.path.join(archive_path, os.path.basename(src))
                shutil.move(src, dest)
                moved_count += 1
            except OSError as e:
                logger.warning(f"Failed to archive {src}: {e}")

        if moved_count > 0:
            logger.info(f"Archived {moved_count} file(s) to {archive_path}")

        return moved_count, archive_path

    def cleanup_project_keyframes(self, project: dict) -> int:
        """Archive old keyframes from project keyframes directory.

        Args:
            project: Project metadata dict

        Returns:
            Number of files archived
        """
        try:
            keyframes_dir = self.project_store.project_path(project, "keyframes")
            if not keyframes_dir or not os.path.exists(keyframes_dir):
                return 0

            count, path = self._archive_files(keyframes_dir, self.KEYFRAME_EXTENSIONS)
            if count > 0:
                logger.info(f"Keyframes cleanup: {count} file(s) archived")
            return count

        except Exception as e:
            logger.error(f"Keyframes cleanup failed: {e}")
            return 0

    def cleanup_project_videos(self, project: dict) -> int:
        """Archive old videos from project video directory.

        Args:
            project: Project metadata dict

        Returns:
            Number of files archived
        """
        try:
            video_dir = self.project_store.project_path(project, "video")
            if not video_dir or not os.path.exists(video_dir):
                return 0

            count, path = self._archive_files(video_dir, self.VIDEO_EXTENSIONS)
            if count > 0:
                logger.info(f"Video cleanup: {count} file(s) archived")
            return count

        except Exception as e:
            logger.error(f"Video cleanup failed: {e}")
            return 0

    def cleanup_comfy_output(self) -> int:
        """Archive leftover files from ComfyUI output directory.

        Returns:
            Number of files archived
        """
        try:
            comfy_output = self.project_store.comfy_output_dir()
            if not os.path.exists(comfy_output):
                return 0

            # Archive both images and videos
            all_extensions = self.KEYFRAME_EXTENSIONS + self.VIDEO_EXTENSIONS
            count, path = self._archive_files(comfy_output, all_extensions)

            # Also check video subdirectory
            video_subdir = os.path.join(comfy_output, "video")
            if os.path.exists(video_subdir):
                video_count, _ = self._archive_files(video_subdir, self.VIDEO_EXTENSIONS)
                count += video_count

            if count > 0:
                logger.info(f"ComfyUI output cleanup: {count} file(s) archived")
            return count

        except Exception as e:
            logger.error(f"ComfyUI output cleanup failed: {e}")
            return 0

    def cleanup_before_keyframe_generation(self, project: dict) -> int:
        """Full cleanup before starting keyframe generation.

        Cleans both project keyframes dir and ComfyUI output.

        Args:
            project: Project metadata dict

        Returns:
            Total number of files archived
        """
        total = 0
        total += self.cleanup_project_keyframes(project)
        total += self.cleanup_comfy_output()

        if total > 0:
            logger.info(f"Pre-generation cleanup: {total} file(s) archived total")
        return total

    def cleanup_before_video_generation(self, project: dict) -> int:
        """Full cleanup before starting video generation.

        Cleans both project video dir and ComfyUI output.

        Args:
            project: Project metadata dict

        Returns:
            Total number of files archived
        """
        total = 0
        total += self.cleanup_project_videos(project)
        total += self.cleanup_comfy_output()

        if total > 0:
            logger.info(f"Pre-generation cleanup: {total} file(s) archived total")
        return total

    def cleanup_character_lora(self, lora_dir: str, character_name: str) -> int:
        """Archive old LoRA files for a character before retraining.

        Args:
            lora_dir: Directory containing LoRA files
            character_name: Character name (prefix to match)

        Returns:
            Number of files archived
        """
        try:
            if not os.path.exists(lora_dir):
                return 0

            # Find matching LoRA files
            prefix = f"cg_{character_name}"
            files_to_move = []
            for f in os.listdir(lora_dir):
                if f.startswith(prefix) and f.lower().endswith(self.LORA_EXTENSIONS):
                    files_to_move.append(os.path.join(lora_dir, f))

            if not files_to_move:
                return 0

            # Create archive in lora directory
            archive_path = self._create_archive_dir(lora_dir)

            moved_count = 0
            for src in files_to_move:
                try:
                    dest = os.path.join(archive_path, os.path.basename(src))
                    shutil.move(src, dest)
                    moved_count += 1
                except OSError as e:
                    logger.warning(f"Failed to archive LoRA {src}: {e}")

            if moved_count > 0:
                logger.info(f"LoRA cleanup for '{character_name}': {moved_count} file(s) archived")

            return moved_count

        except Exception as e:
            logger.error(f"LoRA cleanup failed for {character_name}: {e}")
            return 0


__all__ = ["CleanupService"]
