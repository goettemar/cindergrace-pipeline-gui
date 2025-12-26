"""Addon registry and loader"""
import sys
import os

# Ensure parent directory is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from addons.base_addon import BaseAddon
from addons.storyboard_editor import StoryboardEditorAddon
from addons.storyboard_manager import StoryboardManagerAddon
from addons.storyboard_llm_generator import StoryboardLLMGeneratorAddon
from addons.project_panel import ProjectAddon
from addons.keyframe_generator import KeyframeGeneratorAddon
from addons.keyframe_selector import KeyframeSelectorAddon
from addons.video_generator import VideoGeneratorAddon
from addons.image_importer import ImageImporterAddon
from addons.test_comfy_flux import TestComfyFluxAddon
from addons.model_manager import ModelManagerAddon
from addons.settings_panel import SettingsAddon
from addons.setup_wizard import SetupWizardAddon
from addons.firstlast_video import FirstLastVideoAddon
from addons.lipsync_addon import LipsyncAddon
from addons.dataset_generator import DatasetGeneratorAddon
from addons.character_trainer import CharacterTrainerAddon
from addons.help_addon import HelpAddon
from addons.tts_addon import TTSAddon
from infrastructure.logger import get_logger

logger = get_logger(__name__)


# Registry of all available addons
# Order determines tab order in the UI
AVAILABLE_ADDONS = [
    # === Project & Setup ===
    ProjectAddon,            # Create/select project
    StoryboardManagerAddon,  # Manage storyboards
    StoryboardEditorAddon,   # Define shots
    StoryboardLLMGeneratorAddon,  # AI storyboard generation

    # === Keyframe Production ===
    ImageImporterAddon,      # Import custom images (alternative)
    KeyframeGeneratorAddon,  # AI-generated keyframes
    KeyframeSelectorAddon,   # Select best variant

    # === Video Production ===
    VideoGeneratorAddon,     # Animate keyframes to video
    FirstLastVideoAddon,     # First/Last frame video
    LipsyncAddon,            # Audio-to-video lipsync

    # === Training & Tools ===
    DatasetGeneratorAddon,   # Create character datasets
    CharacterTrainerAddon,   # LoRA training
    TTSAddon,                # Text-to-speech for explainer videos
    TestComfyFluxAddon,      # Test ComfyUI
    ModelManagerAddon,       # Manage models
    SetupWizardAddon,        # Initial setup

    # === Settings & Help ===
    SettingsAddon,           # Configuration
    HelpAddon,               # Help & workflow overview (rightmost)
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
