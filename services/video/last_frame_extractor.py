"""Utility to extract the last frame from a generated video."""
from typing import Optional


class LastFrameExtractor:
    """Minimal last-frame extractor (ffmpeg-backed in production)."""

    def is_available(self) -> bool:
        """Return True when extraction backend is available."""
        return False

    def extract(self, video_path: str) -> Optional[str]:
        """Return path to extracted last frame (None if unavailable)."""
        return None


__all__ = ["LastFrameExtractor"]
