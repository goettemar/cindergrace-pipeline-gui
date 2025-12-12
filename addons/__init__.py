"""Addon registry and loader"""
import sys
import os

# Ensure parent directory is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from addons.base_addon import BaseAddon
from addons.project_panel import ProjectAddon
from addons.keyframe_generator import KeyframeGeneratorAddon
from addons.keyframe_selector import KeyframeSelectorAddon
from addons.video_generator import VideoGeneratorAddon
from addons.test_comfy_flux import TestComfyFluxAddon
from addons.settings_panel import SettingsAddon
from infrastructure.logger import get_logger

logger = get_logger(__name__)


# Registry of all available addons
AVAILABLE_ADDONS = [
    ProjectAddon,
    KeyframeGeneratorAddon,  # ✅ Phase 1 - Keyframe generation
    KeyframeSelectorAddon,   # ✅ Phase 2 - Keyframe selection
    VideoGeneratorAddon,     # ✅ Phase 3 - Wan video generation (3s segments)
    TestComfyFluxAddon,
    SettingsAddon,
    # Future addons will be added here:
    # VideoGeneratorAddon,    # Phase 3 - Video generation
    # LipsyncProcessorAddon,  # Phase 4 - Lipsync processing
    # TimelineAssemblerAddon, # Phase 5 - Timeline assembly
]


def load_addons():
    """
    Load all enabled addons

    Returns:
        List of instantiated addon objects
    """
    addons = []
    for addon_class in AVAILABLE_ADDONS:
        try:
            addon = addon_class()
            addon.on_load()
            addons.append(addon)
            logger.info(f"✓ Loaded addon: {addon.name}")
        except Exception as e:
            logger.error(f"Failed to load {addon_class.__name__}: {e}", exc_info=True)

    return addons


__all__ = ["BaseAddon", "load_addons", "AVAILABLE_ADDONS"]
