"""Addon registry and loader"""
import sys
import os

# Ensure parent directory is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from addons.base_addon import BaseAddon
from addons.storyboard_editor import StoryboardEditorAddon
from addons.project_panel import ProjectAddon
from addons.keyframe_generator import KeyframeGeneratorAddon
from addons.keyframe_selector import KeyframeSelectorAddon
from addons.video_generator import VideoGeneratorAddon
from addons.test_comfy_flux import TestComfyFluxAddon
from addons.model_manager import ModelManagerAddon
from addons.settings_panel import SettingsAddon
from infrastructure.logger import get_logger

logger = get_logger(__name__)


# Registry of all available addons
AVAILABLE_ADDONS = [
    ProjectAddon,            # Tab 1
    StoryboardEditorAddon,   # Tab 2 - Storyboard editor
    KeyframeGeneratorAddon,  # Tab 3 - Phase 1
    KeyframeSelectorAddon,   # Tab 4 - Phase 2
    VideoGeneratorAddon,     # Tab 5 - Phase 3
    TestComfyFluxAddon,      # Tools Tab
    ModelManagerAddon,       # Tools Tab
    SettingsAddon,           # Tab 7
    # Future addons will be added here:
    # LipsyncProcessorAddon,
    # TimelineAssemblerAddon,
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
