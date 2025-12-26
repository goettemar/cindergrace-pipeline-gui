"""Factory functions for reusable Gradio UI components.

This module provides factory functions that create consistent UI elements
across all addons, reducing code duplication and ensuring visual consistency.

Usage:
    from addons.ui_factories import create_universal_presets, create_preset_dropdown

    # In your render method:
    presets = create_universal_presets(self.preset_service)
    # Access: presets["style"], presets["lighting"], etc.
"""

import gradio as gr
from typing import Dict, List, Tuple, Optional

from infrastructure.preset_service import PresetService


# Preset configuration: category -> (label, info)
PRESET_CONFIG: Dict[str, Tuple[str, str]] = {
    # Universal Presets (for all shots)
    "style": ("Style", "Visual style"),
    "lighting": ("Lighting", "Light direction"),
    "mood": ("Mood", "Atmosphere"),
    "time_of_day": ("Time of Day", "Lighting conditions"),
    # Keyframe Presets (Flux)
    "composition": ("Composition", "Image layout"),
    "color_grade": ("Color Grade", "Color grading"),
    # Video Presets (Wan)
    "camera": ("Camera Movement", "Camera direction"),
    "motion": ("Motion Type", "Motion control"),
}


def create_preset_dropdown(
    preset_service: PresetService,
    category: str,
    value: str = "none",
    **kwargs,
) -> gr.Dropdown:
    """Create a single preset dropdown.

    Args:
        preset_service: PresetService instance for fetching choices
        category: Preset category (e.g., "style", "lighting")
        value: Initial value (default: "none")
        **kwargs: Additional arguments passed to gr.Dropdown

    Returns:
        Configured gr.Dropdown component
    """
    label, info = PRESET_CONFIG.get(category, (category.capitalize(), ""))
    return gr.Dropdown(
        label=label,
        choices=preset_service.get_dropdown_choices(category, include_none=True),
        value=value,
        info=info,
        **kwargs,
    )


def create_preset_row(
    preset_service: PresetService,
    categories: List[str],
) -> Dict[str, gr.Dropdown]:
    """Create a row of preset dropdowns.

    Must be called inside a gr.Row() context.

    Args:
        preset_service: PresetService instance
        categories: List of preset categories to create

    Returns:
        Dictionary mapping category names to dropdown components

    Example:
        with gr.Row():
            presets = create_preset_row(service, ["style", "lighting"])
        # Access: presets["style"], presets["lighting"]
    """
    dropdowns = {}
    for category in categories:
        dropdowns[category] = create_preset_dropdown(preset_service, category)
    return dropdowns


def create_universal_presets(preset_service: PresetService) -> Dict[str, gr.Dropdown]:
    """Create all universal presets (style, lighting, mood, time_of_day).

    Creates the complete preset section with header and two rows.

    Args:
        preset_service: PresetService instance

    Returns:
        Dictionary with keys: style, lighting, mood, time_of_day
    """
    gr.Markdown("#### Style Presets")
    with gr.Row():
        style = create_preset_dropdown(preset_service, "style")
        lighting = create_preset_dropdown(preset_service, "lighting")
    with gr.Row():
        mood = create_preset_dropdown(preset_service, "mood")
        time_of_day = create_preset_dropdown(preset_service, "time_of_day")

    return {
        "style": style,
        "lighting": lighting,
        "mood": mood,
        "time_of_day": time_of_day,
    }


def create_keyframe_presets(preset_service: PresetService) -> Dict[str, gr.Dropdown]:
    """Create keyframe-specific presets (composition, color_grade).

    Args:
        preset_service: PresetService instance

    Returns:
        Dictionary with keys: composition, color_grade
    """
    gr.Markdown("#### Composition & Color")
    with gr.Row():
        composition = create_preset_dropdown(preset_service, "composition")
        color_grade = create_preset_dropdown(preset_service, "color_grade")

    return {
        "composition": composition,
        "color_grade": color_grade,
    }


def create_video_presets(preset_service: PresetService) -> Dict[str, gr.Dropdown]:
    """Create video-specific presets (camera, motion).

    Args:
        preset_service: PresetService instance

    Returns:
        Dictionary with keys: camera, motion
    """
    with gr.Row():
        camera = create_preset_dropdown(preset_service, "camera")
        motion = create_preset_dropdown(preset_service, "motion")

    return {
        "camera": camera,
        "motion": motion,
    }


def create_render_settings(
    prefix: str = "flux",
    seed_value: int = -1,
    cfg_value: float = 7.0,
    steps_value: int = 20,
) -> Dict[str, gr.Number]:
    """Create render settings row (seed, cfg, steps).

    Args:
        prefix: Prefix for field names (e.g., "flux", "wan")
        seed_value: Initial seed value (-1 = random)
        cfg_value: Initial CFG scale value
        steps_value: Initial steps value

    Returns:
        Dictionary with keys: seed, cfg, steps
    """
    with gr.Row():
        seed = gr.Number(
            label="Seed",
            value=seed_value,
            precision=0,
            info="-1 = random"
        )
        cfg = gr.Number(
            label="CFG Scale",
            value=cfg_value,
            minimum=1.0,
            maximum=30.0,
            step=0.5,
            precision=1,
            info="Guidance Scale"
        )
        steps = gr.Number(
            label="Steps",
            value=steps_value,
            minimum=1,
            maximum=150,
            precision=0,
            info="Sampling Steps"
        )

    return {
        "seed": seed,
        "cfg": cfg,
        "steps": steps,
    }


__all__ = [
    "PRESET_CONFIG",
    "create_preset_dropdown",
    "create_preset_row",
    "create_universal_presets",
    "create_keyframe_presets",
    "create_video_presets",
    "create_render_settings",
]
