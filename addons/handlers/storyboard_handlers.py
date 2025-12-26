"""Storyboard Editor Event Handlers - extracted for maintainability.

This module contains the callback functions for storyboard editor operations.
Extracted from StoryboardEditorAddon to reduce file size and improve testability.
"""
import os
import json
from typing import Tuple, List, Optional, Any, Dict
import gradio as gr

from domain.models import Storyboard
from domain.storyboard_service import StoryboardService
from infrastructure.logger import get_logger

logger = get_logger(__name__)


class ShotInputs:
    """Container for shot input parameters."""

    def __init__(
        self,
        shot_id: str,
        filename_base: str,
        description: str,
        prompt: str,
        negative_prompt: str,
        preset_style: str,
        preset_lighting: str,
        preset_mood: str,
        preset_time_of_day: str,
        preset_composition: str,
        preset_color_grade: str,
        flux_seed: float,
        flux_cfg: float,
        flux_steps: float,
        preset_camera: str,
        preset_motion: str,
        wan_motion_strength: float,
        duration: float,
        characters: List[str],
        wan_seed: float,
        wan_cfg: float,
        wan_steps: float,
        character_lora: str
    ):
        self.shot_id = shot_id
        self.filename_base = filename_base
        self.description = description
        self.prompt = prompt
        self.negative_prompt = negative_prompt or ""
        self.preset_style = preset_style
        self.preset_lighting = preset_lighting
        self.preset_mood = preset_mood
        self.preset_time_of_day = preset_time_of_day
        self.preset_composition = preset_composition
        self.preset_color_grade = preset_color_grade
        self.flux_seed = int(flux_seed) if flux_seed else -1
        self.flux_cfg = float(flux_cfg) if flux_cfg else 7.0
        self.flux_steps = int(flux_steps) if flux_steps else 20
        self.preset_camera = preset_camera
        self.preset_motion = preset_motion
        self.wan_motion_strength = float(wan_motion_strength) if wan_motion_strength else 0.5
        self.duration = float(duration) if duration else 3.0
        self.characters = characters if characters else []
        self.wan_seed = int(wan_seed) if wan_seed else -1
        self.wan_cfg = float(wan_cfg) if wan_cfg else 7.0
        self.wan_steps = int(wan_steps) if wan_steps else 20
        self.character_lora = character_lora if character_lora and character_lora != "none" else None

    def collect_presets(self) -> Dict[str, str]:
        """Collect non-empty presets into a dictionary."""
        presets = {}
        preset_fields = [
            ("style", self.preset_style),
            ("lighting", self.preset_lighting),
            ("mood", self.preset_mood),
            ("time_of_day", self.preset_time_of_day),
            ("composition", self.preset_composition),
            ("color_grade", self.preset_color_grade),
            ("camera", self.preset_camera),
            ("motion", self.preset_motion),
        ]
        for key, value in preset_fields:
            if value and value != "none":
                presets[key] = value
        return presets if presets else None

    def get_flux_settings(self) -> Dict[str, Any]:
        """Get Flux render settings."""
        return {
            "seed": self.flux_seed,
            "cfg": self.flux_cfg,
            "steps": self.flux_steps
        }

    def get_wan_settings(self) -> Dict[str, Any]:
        """Get Wan render settings."""
        return {
            "seed": self.wan_seed,
            "cfg": self.wan_cfg,
            "steps": self.wan_steps,
            "motion_strength": self.wan_motion_strength
        }

    def validate(self) -> Optional[str]:
        """Validate required fields. Returns error message or None if valid."""
        if not self.prompt:
            return "❌ Error: Prompt is required"
        if not self.filename_base:
            return "❌ Error: Filename Base is required"
        if not self.description:
            return "❌ Error: Description is required"
        return None


class StoryboardHandlers:
    """Handlers for storyboard CRUD operations."""

    def __init__(self, addon):
        """Initialize with reference to parent addon for service access."""
        self.addon = addon

    @property
    def current_storyboard(self) -> Optional[Storyboard]:
        return self.addon.current_storyboard

    @current_storyboard.setter
    def current_storyboard(self, value: Storyboard):
        self.addon.current_storyboard = value

    def _error_response(self, message: str) -> Tuple:
        """Create error response tuple."""
        return (
            message,
            gr.update(value=self.addon._storyboard_to_dataframe()),
            self.addon._get_timeline_info(),
            self.addon._storyboard_to_json_str()
        )

    def _success_response(self, message: str) -> Tuple:
        """Create success response tuple."""
        return (
            message,
            gr.update(value=self.addon._storyboard_to_dataframe()),
            self.addon._get_timeline_info(),
            self.addon._storyboard_to_json_str()
        )

    def add_shot(self, inputs: ShotInputs) -> Tuple:
        """Add a new shot to the storyboard."""
        if not self.current_storyboard:
            return "❌ Error: No storyboard loaded", gr.update(value=[]), "**Timeline:** 0 shots, 0.0s total", "{}"

        error = inputs.validate()
        if error:
            return self._error_response(error)

        shot_id = inputs.shot_id
        if not shot_id:
            shot_id = self.addon.editor_service.get_next_shot_id(self.current_storyboard)

        # Build full prompt
        full_prompt = self.addon.preset_service.build_prompt(
            base_prompt=inputs.prompt,
            style=inputs.preset_style if inputs.preset_style != "none" else None,
            lighting=inputs.preset_lighting if inputs.preset_lighting != "none" else None,
            mood=inputs.preset_mood if inputs.preset_mood != "none" else None,
            time_of_day=inputs.preset_time_of_day if inputs.preset_time_of_day != "none" else None,
            camera=inputs.preset_camera if inputs.preset_camera != "none" else None,
            motion=inputs.preset_motion if inputs.preset_motion != "none" else None,
        )

        self.current_storyboard = self.addon.editor_service.add_shot(
            self.current_storyboard,
            shot_id=shot_id,
            filename_base=inputs.filename_base or f"shot_{shot_id}",
            description=inputs.description,
            prompt=inputs.prompt,
            full_prompt=full_prompt,
            duration=inputs.duration,
            characters=inputs.characters,
            character_lora=inputs.character_lora,
            negative_prompt=inputs.negative_prompt,
            presets=inputs.collect_presets(),
            flux=inputs.get_flux_settings(),
            wan=inputs.get_wan_settings(),
            width=1024,
            height=576,
        )

        return self._success_response(f"✅ Added shot {shot_id}")

    def update_shot(self, index: int, inputs: ShotInputs) -> Tuple:
        """Update an existing shot."""
        if not self.current_storyboard:
            return "❌ Error: No storyboard loaded", [], "**Timeline:** 0 shots, 0.0s total", "{}"

        index = int(index)
        if index < 0 or index >= len(self.current_storyboard.shots):
            return self._error_response(f"❌ Error: Invalid index {index}")

        error = inputs.validate()
        if error:
            return self._error_response(error)

        # Build full prompt
        full_prompt = self.addon.preset_service.build_prompt(
            base_prompt=inputs.prompt,
            style=inputs.preset_style if inputs.preset_style != "none" else None,
            lighting=inputs.preset_lighting if inputs.preset_lighting != "none" else None,
            mood=inputs.preset_mood if inputs.preset_mood != "none" else None,
            time_of_day=inputs.preset_time_of_day if inputs.preset_time_of_day != "none" else None,
            camera=inputs.preset_camera if inputs.preset_camera != "none" else None,
            motion=inputs.preset_motion if inputs.preset_motion != "none" else None,
        )

        self.current_storyboard = self.addon.editor_service.update_shot(
            self.current_storyboard,
            index,
            shot_id=inputs.shot_id,
            filename_base=inputs.filename_base,
            description=inputs.description,
            prompt=inputs.prompt,
            full_prompt=full_prompt,
            duration=inputs.duration,
            characters=inputs.characters,
            character_lora=inputs.character_lora,
            negative_prompt=inputs.negative_prompt,
            presets=inputs.collect_presets(),
            flux=inputs.get_flux_settings(),
            wan=inputs.get_wan_settings(),
        )

        # Auto-save
        save_status = self._auto_save(inputs.shot_id)

        return self._success_response(f"✅ Updated shot at index {index}{save_status}")

    def _auto_save(self, shot_id: str) -> str:
        """Auto-save storyboard after update. Returns status suffix."""
        try:
            current_sb_path = self.addon.config.get_current_storyboard()
            if current_sb_path and os.path.exists(current_sb_path):
                StoryboardService.save_storyboard(self.current_storyboard, current_sb_path)
                logger.info(f"Auto-saved storyboard after updating shot {shot_id}")
                return " (auto-saved)"
            else:
                logger.warning("No storyboard path set, cannot auto-save")
                return " (kein Storyboard-Pfad)"
        except Exception as e:
            logger.warning(f"Could not auto-save storyboard: {e}")
            return " (save failed)"

    def delete_shot(self, index: int) -> Tuple:
        """Delete a shot from the storyboard."""
        if not self.current_storyboard:
            return "❌ Error: No storyboard loaded", gr.update(value=[]), "**Timeline:** 0 shots, 0.0s total", "{}"

        index = int(index)
        try:
            self.current_storyboard = self.addon.editor_service.delete_shot(
                self.current_storyboard, index
            )
        except IndexError:
            return self._error_response(f"❌ Error: Invalid index {index}")

        return self._success_response(f"✅ Deleted shot at index {index}")
