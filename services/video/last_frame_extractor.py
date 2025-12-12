"""LastFrame extraction service for video segment chaining."""
import os
import shutil
import subprocess
from typing import Optional, Dict, Any

from infrastructure.logger import get_logger

logger = get_logger(__name__)


class LastFrameExtractor:
    """Extract last frames from video clips using ffmpeg."""

    def __init__(self, cache_dir: str):
        """
        Initialize the LastFrame extractor.

        Args:
            cache_dir: Directory to store extracted frames
        """
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    @staticmethod
    def is_available() -> bool:
        """Check if ffmpeg is available on the system."""
        return shutil.which("ffmpeg") is not None

    def extract(
        self,
        video_path: str,
        entry: Dict[str, Any],
        offset_seconds: float = 0.05
    ) -> Optional[str]:
        """
        Extract the last frame from a video file.

        Args:
            video_path: Path to source video file
            entry: Plan entry containing shot metadata
            offset_seconds: Offset from end in seconds (default: 0.05s)

        Returns:
            Path to extracted frame PNG, or None if extraction failed
        """
        if not self.is_available():
            logger.warning("ffmpeg not found - cannot extract last frame")
            return None

        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            return None

        plan_id = entry.get("plan_id") or entry.get("shot_id") or "clip"
        target_path = os.path.join(self.cache_dir, f"{plan_id}_lastframe.png")

        cmd = [
            "ffmpeg",
            "-y",  # Overwrite existing
            "-v", "error",  # Only show errors
            "-sseof", f"-{offset_seconds}",  # Seek from end
            "-i", video_path,
            "-frames:v", "1",  # Extract 1 frame
            target_path,
        ]

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            logger.info(f"Extracted last frame: {target_path}")
        except subprocess.CalledProcessError as exc:
            logger.error(
                f"ffmpeg failed to extract last frame: {exc.stderr}",
                exc_info=True
            )
            return None
        except Exception as exc:
            logger.error(
                f"Unexpected error during frame extraction: {exc}",
                exc_info=True
            )
            return None

        if os.path.exists(target_path):
            return target_path

        logger.warning(f"Frame extraction succeeded but file not found: {target_path}")
        return None


__all__ = ["LastFrameExtractor"]
