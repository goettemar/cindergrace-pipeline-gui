"""
Video generation service (legacy compatibility).

This module re-exports from the new services/video/ package structure.
Use services.video imports directly for new code.
"""
from services.video.video_plan_builder import VideoPlanBuilder
from services.video.video_generation_service import VideoGenerationService
from services.video.last_frame_extractor import LastFrameExtractor

__all__ = ["VideoPlanBuilder", "VideoGenerationService", "LastFrameExtractor"]
