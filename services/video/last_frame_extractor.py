"""Utility to extract the last frame from a generated video."""
import os
import shutil
import subprocess
import tempfile
from typing import Optional

from infrastructure.logger import get_logger

logger = get_logger(__name__)


class LastFrameExtractor:
    """Extract the last frame from a video file using ffmpeg."""

    def __init__(self):
        self._ffmpeg_path = self._find_ffmpeg()

    def _find_ffmpeg(self) -> str:
        """Find ffmpeg executable."""
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            return ffmpeg
        # Common locations
        for path in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"]:
            if os.path.isfile(path):
                return path
        return "ffmpeg"  # Hope it's in PATH

    def is_available(self) -> bool:
        """Return True when extraction backend is available."""
        try:
            result = subprocess.run(
                [self._ffmpeg_path, "-version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def extract(self, video_path: str, output_path: Optional[str] = None) -> Optional[str]:
        """Extract the last frame from a video.

        Args:
            video_path: Path to the video file
            output_path: Optional output path for the frame image.
                        If None, creates a temp file.

        Returns:
            Path to extracted frame image, or None if failed
        """
        if not os.path.isfile(video_path):
            logger.error(f"Video file not found: {video_path}")
            return None

        # Create output path if not specified
        if output_path is None:
            temp_dir = tempfile.gettempdir()
            basename = os.path.splitext(os.path.basename(video_path))[0]
            output_path = os.path.join(temp_dir, f"{basename}_lastframe.png")

        try:
            # First, get video duration
            probe_cmd = [
                self._ffmpeg_path.replace("ffmpeg", "ffprobe"),
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                video_path
            ]

            probe_result = subprocess.run(
                probe_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            if probe_result.returncode != 0:
                logger.error(f"ffprobe failed: {probe_result.stderr}")
                return None

            duration = float(probe_result.stdout.strip())
            # Go slightly before end to ensure we get a frame
            seek_time = max(0, duration - 0.1)

            # Extract frame at end of video
            extract_cmd = [
                self._ffmpeg_path,
                "-y",  # Overwrite
                "-ss", str(seek_time),
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "2",  # High quality
                output_path
            ]

            result = subprocess.run(
                extract_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                logger.error(f"Frame extraction failed: {result.stderr}")
                return None

            if os.path.isfile(output_path) and os.path.getsize(output_path) > 0:
                logger.info(f"Extracted last frame: {output_path}")
                return output_path
            else:
                logger.error("Extraction produced no output")
                return None

        except subprocess.TimeoutExpired:
            logger.error("Frame extraction timed out")
            return None
        except Exception as e:
            logger.error(f"Frame extraction failed: {e}")
            return None

    def extract_first_frame(self, video_path: str, output_path: Optional[str] = None) -> Optional[str]:
        """Extract the first frame from a video.

        Args:
            video_path: Path to the video file
            output_path: Optional output path for the frame image.

        Returns:
            Path to extracted frame image, or None if failed
        """
        if not os.path.isfile(video_path):
            logger.error(f"Video file not found: {video_path}")
            return None

        if output_path is None:
            temp_dir = tempfile.gettempdir()
            basename = os.path.splitext(os.path.basename(video_path))[0]
            output_path = os.path.join(temp_dir, f"{basename}_firstframe.png")

        try:
            extract_cmd = [
                self._ffmpeg_path,
                "-y",
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "2",
                output_path
            ]

            result = subprocess.run(
                extract_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                logger.error(f"Frame extraction failed: {result.stderr}")
                return None

            if os.path.isfile(output_path) and os.path.getsize(output_path) > 0:
                logger.info(f"Extracted first frame: {output_path}")
                return output_path

            return None

        except Exception as e:
            logger.error(f"Frame extraction failed: {e}")
            return None


__all__ = ["LastFrameExtractor"]
