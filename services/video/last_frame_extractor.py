"""LastFrame extraction service for video segment chaining."""
import os
import shutil
import subprocess
import time
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

        # Ensure cache directory exists
        os.makedirs(self.cache_dir, exist_ok=True)

        # Primary method: Get frame count and extract last frame by number
        # This is the most reliable method for extracting the final frame
        logger.info(f"Extracting last frame from: {video_path} → {target_path}")

        if not os.path.exists(video_path):
            logger.error(f"Video file does not exist: {video_path}")
            return None

        try:
            # Get total frame count
            probe_cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-count_frames",
                "-show_entries", "stream=nb_read_frames",
                "-of", "default=nokey=1:noprint_wrappers=1",
                video_path
            ]
            logger.debug(f"Getting frame count: {' '.join(probe_cmd)}")
            frame_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=60)
            if frame_result.returncode != 0:
                logger.error(f"ffprobe failed: {frame_result.stderr}")
                raise ValueError(f"ffprobe returncode: {frame_result.returncode}")

            total_frames = int(frame_result.stdout.strip())
            last_frame_num = max(0, total_frames - 1)
            logger.info(f"Total frames: {total_frames}, extracting frame: {last_frame_num}")

            # Extract specific frame by number using select filter
            cmd = [
                "ffmpeg", "-y",
                "-v", "warning",
                "-i", video_path,
                "-vf", f"select=eq(n\\,{last_frame_num})",
                "-frames:v", "1",
                "-update", "1",
                target_path
            ]
            logger.info(f"Running ffmpeg: {' '.join(cmd)}")
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60)
            if result.stderr:
                logger.debug(f"ffmpeg stderr: {result.stderr}")

            # Small delay to ensure file is fully written
            time.sleep(0.2)

            if os.path.exists(target_path):
                file_size = os.path.getsize(target_path)
                logger.info(f"✓ Extracted last frame: {target_path} ({file_size} bytes)")
                return target_path
            else:
                logger.warning(f"ffmpeg completed but file not created: {target_path}")
                # List directory contents for debugging
                parent_dir = os.path.dirname(target_path)
                if os.path.exists(parent_dir):
                    files = os.listdir(parent_dir)
                    logger.warning(f"Contents of {parent_dir}: {files}")

        except subprocess.TimeoutExpired:
            logger.error("ffmpeg/ffprobe timed out during frame extraction")
        except ValueError as ve:
            logger.error(f"Could not parse video duration: {ve}")
        except subprocess.CalledProcessError as exc:
            logger.error(f"ffmpeg failed: {exc.stderr}")
        except Exception as exc:
            logger.error(f"Primary extraction failed: {exc}", exc_info=True)

        # Fallback: Try -sseof method (works on some formats)
        logger.warning("Primary method failed, trying -sseof fallback...")
        try:
            fallback_cmd = [
                "ffmpeg", "-y", "-v", "warning",
                "-sseof", f"-{offset_seconds}",
                "-i", video_path,
                "-frames:v", "1",
                "-update", "1",
                target_path
            ]
            subprocess.run(fallback_cmd, check=True, capture_output=True, text=True, timeout=30)
            time.sleep(0.2)

            if os.path.exists(target_path):
                file_size = os.path.getsize(target_path)
                logger.info(f"Extracted last frame (fallback): {target_path} ({file_size} bytes)")
                return target_path
        except Exception as fallback_exc:
            logger.debug(f"Fallback extraction also failed: {fallback_exc}")

        logger.error(f"Frame extraction failed - file not created: {target_path}")
        return None


__all__ = ["LastFrameExtractor"]
