"""Shallow tests for legacy video_service module exports."""
import importlib


def test_video_service_reexports_components():
    module = importlib.import_module("services.video_service")

    assert hasattr(module, "VideoPlanBuilder")
    assert hasattr(module, "VideoGenerationService")
    assert hasattr(module, "LastFrameExtractor")
    assert set(module.__all__) == {
        "VideoPlanBuilder",
        "VideoGenerationService",
        "LastFrameExtractor",
    }
