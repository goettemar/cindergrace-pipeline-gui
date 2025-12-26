"""Pydantic validation models for CINDERGRACE input validation"""
from pydantic import BaseModel, Field, field_validator, ConfigDict, model_validator
from typing import Any, Dict, List, Optional, Tuple
import json
import os
import re


class KeyframeGeneratorInput(BaseModel):
    """Validation model for Keyframe Generator inputs"""

    model_config = ConfigDict(str_strip_whitespace=True)

    variants_per_shot: int = Field(
        ge=1,
        le=10,
        description="Number of keyframe variants to generate per shot"
    )
    base_seed: int = Field(
        ge=0,
        le=2147483647,  # Max int32
        description="Base seed for random generation"
    )

    @field_validator('variants_per_shot')
    @classmethod
    def validate_variants(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Mindestens 1 Variante pro Shot erforderlich")
        if v > 10:
            raise ValueError("Maximal 10 Varianten pro Shot erlaubt (Performance-Limit)")
        return v

    @field_validator('base_seed')
    @classmethod
    def validate_seed(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Seed muss eine positive Zahl sein")
        if v > 2147483647:
            raise ValueError("Seed zu groß (max. 2147483647)")
        return v


class VideoGeneratorInput(BaseModel):
    """Validation model for Video Generator inputs"""

    model_config = ConfigDict(str_strip_whitespace=True)

    fps: int = Field(
        ge=12,
        le=30,
        description="Frames per second for video generation"
    )
    max_segment_seconds: float = Field(
        gt=0,
        le=10.0,
        description="Maximum duration of each video segment in seconds"
    )

    @field_validator('fps')
    @classmethod
    def validate_fps(cls, v: int) -> int:
        if v < 12:
            raise ValueError("FPS zu niedrig (min. 12 fps)")
        if v > 30:
            raise ValueError("FPS zu hoch (max. 30 fps für Wan 2.2)")
        return v

    @field_validator('max_segment_seconds')
    @classmethod
    def validate_segment_duration(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Segment-Dauer muss größer als 0 sein")
        if v > 10.0:
            raise ValueError("Segment-Dauer zu lang (max. 10 Sekunden)")
        return v


class ProjectCreateInput(BaseModel):
    """Validation model for Project creation"""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(
        min_length=1,
        max_length=100,
        description="Project name"
    )

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Projektname darf nicht leer sein")
        if len(v) > 100:
            raise ValueError("Projektname zu lang (max. 100 Zeichen)")

        # Check for invalid filesystem characters
        invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
        if re.search(invalid_chars, v):
            raise ValueError("Projektname enthält ungültige Zeichen (vermeiden: < > : \" / \\ | ? *)")

        # Check for reserved names (Windows)
        reserved = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4',
                   'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2',
                   'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}
        if v.upper() in reserved:
            raise ValueError(f"'{v}' ist ein reservierter Name und nicht erlaubt")

        return v


class SettingsInput(BaseModel):
    """Validation model for Settings configuration"""

    model_config = ConfigDict(str_strip_whitespace=True)

    comfy_url: str = Field(
        min_length=1,
        description="ComfyUI server URL"
    )
    comfy_root: str = Field(
        min_length=1,
        description="ComfyUI installation root path"
    )

    @field_validator('comfy_url')
    @classmethod
    def validate_comfy_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("ComfyUI URL darf nicht leer sein")

        # Basic URL validation
        if not v.startswith(('http://', 'https://')):
            raise ValueError("URL muss mit http:// oder https:// beginnen")

        # Check for valid format
        url_pattern = r'^https?://[\w\-\.]+(:\d+)?(/.*)?$'
        if not re.match(url_pattern, v):
            raise ValueError("Ungültiges URL-Format (z.B. http://127.0.0.1:8188)")

        return v

    @field_validator('comfy_root')
    @classmethod
    def validate_comfy_root(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("ComfyUI Root-Pfad darf nicht leer sein")

        # Check if path looks reasonable
        if len(v) < 3:
            raise ValueError("Pfad zu kurz (z.B. /home/user/ComfyUI)")

        # On Linux, check if absolute path
        if not v.startswith('/') and not re.match(r'^[A-Za-z]:\\', v):
            raise ValueError("Bitte absoluten Pfad angeben (z.B. /home/user/ComfyUI)")

        # Warn if path doesn't exist (but don't fail - user might want to set it up later)
        # We'll just validate the format here

        return v


class StoryboardFileInput(BaseModel):
    """Validation model for Storyboard file selection"""

    model_config = ConfigDict(str_strip_whitespace=True)

    storyboard_file: str = Field(
        min_length=1,
        description="Storyboard JSON file path"
    )

    @field_validator('storyboard_file')
    @classmethod
    def validate_storyboard_file(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Keine Storyboard-Datei ausgewählt")

        if v.startswith("No storyboards"):
            raise ValueError("Keine Storyboard-Dateien verfügbar")

        if not v.endswith('.json'):
            raise ValueError("Storyboard-Datei muss eine .json Datei sein")

        return v


class WorkflowFileInput(BaseModel):
    """Validation model for Workflow file selection"""

    model_config = ConfigDict(str_strip_whitespace=True)

    workflow_file: str = Field(
        min_length=1,
        description="Workflow JSON file path"
    )

    @field_validator('workflow_file')
    @classmethod
    def validate_workflow_file(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Kein Workflow ausgewählt")

        if v.startswith("No workflows"):
            raise ValueError("Keine Workflow-Dateien verfügbar")

        if not v.endswith('.json'):
            raise ValueError("Workflow-Datei muss eine .json Datei sein")

        return v


class SelectionFileInput(BaseModel):
    """Validation model for Selection file input"""

    model_config = ConfigDict(str_strip_whitespace=True)

    selection_file: str = Field(
        min_length=1,
        description="Selection JSON file path"
    )

    @field_validator('selection_file')
    @classmethod
    def validate_selection_file(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Keine Auswahl-Datei angegeben")

        if not v.endswith('.json'):
            raise ValueError("Auswahl-Datei muss eine .json Datei sein")

        return v


# ========================================
# Storyboard Draft Validation
# ========================================

class ShotDraft(BaseModel):
    """Validation model for a single shot in a storyboard draft."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")

    shot_id: str = Field(min_length=1, description="Shot identifier")
    filename_base: str = Field(min_length=1, description="Base filename")
    prompt: str = Field(min_length=1, description="Image generation prompt")
    description: Optional[str] = Field(default=None, description="Shot description")
    negative_prompt: Optional[str] = Field(default=None)
    width: int = Field(default=1024, ge=256, le=2048)
    height: int = Field(default=576, ge=256, le=2048)
    duration: float = Field(default=3.0, gt=0, le=30)
    presets: Optional[Dict[str, str]] = Field(default=None)

    @field_validator('filename_base')
    @classmethod
    def validate_filename_base(cls, v: str) -> str:
        v = v.strip()
        # Remove invalid filesystem characters
        invalid_chars = r'[<>:"/\\|?*\s]'
        if re.search(invalid_chars, v):
            # Auto-fix: replace with hyphens
            v = re.sub(invalid_chars, '-', v)
        # Ensure lowercase
        return v.lower()

    @field_validator('shot_id')
    @classmethod
    def validate_shot_id(cls, v: str) -> str:
        v = v.strip()
        # Ensure it's a valid ID format (numbers or alphanumeric)
        if not re.match(r'^[\w\-]+$', v):
            raise ValueError(f"Invalid shot_id format: {v}")
        return v


class StoryboardDraft(BaseModel):
    """Validation model for LLM-generated storyboard drafts."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")

    project: str = Field(min_length=1, description="Project name")
    shots: List[ShotDraft] = Field(min_length=1, description="List of shots")
    description: Optional[str] = Field(default=None)
    version: str = Field(default="2.2")
    video_settings: Optional[Dict[str, Any]] = Field(default=None)

    @field_validator('project')
    @classmethod
    def validate_project(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Project name cannot be empty")
        return v

    @field_validator('shots')
    @classmethod
    def validate_shots(cls, v: List[ShotDraft]) -> List[ShotDraft]:
        if not v:
            raise ValueError("Storyboard must have at least one shot")
        return v

    @model_validator(mode='after')
    def validate_unique_shot_ids(self) -> 'StoryboardDraft':
        """Ensure all shot IDs are unique."""
        shot_ids = [shot.shot_id for shot in self.shots]
        if len(shot_ids) != len(set(shot_ids)):
            raise ValueError("Duplicate shot_id found - all shot IDs must be unique")
        return self


class StoryboardDraftValidator:
    """Utility class for validating storyboard drafts from LLM output."""

    @staticmethod
    def validate_json_string(json_str: str) -> Tuple[bool, Optional[StoryboardDraft], List[str]]:
        """Validate a JSON string as a storyboard draft.

        Args:
            json_str: JSON string to validate

        Returns:
            Tuple of (is_valid, parsed_draft, list_of_errors)
        """
        errors = []

        # Step 1: Parse JSON
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return False, None, [f"Invalid JSON: {e}"]

        # Step 2: Check it's a dict
        if not isinstance(data, dict):
            return False, None, ["Root element must be an object, not array"]

        # Step 3: Validate with Pydantic
        try:
            draft = StoryboardDraft.model_validate(data)
            return True, draft, []
        except Exception as e:
            # Extract validation errors
            error_str = str(e)
            # Parse pydantic validation errors
            if hasattr(e, 'errors'):
                for err in e.errors():
                    loc = " -> ".join(str(l) for l in err.get('loc', []))
                    msg = err.get('msg', 'Unknown error')
                    errors.append(f"{loc}: {msg}")
            else:
                errors.append(error_str)

            return False, None, errors

    @staticmethod
    def validate_dict(data: Dict[str, Any]) -> Tuple[bool, Optional[StoryboardDraft], List[str]]:
        """Validate a dictionary as a storyboard draft.

        Args:
            data: Dictionary to validate

        Returns:
            Tuple of (is_valid, parsed_draft, list_of_errors)
        """
        try:
            draft = StoryboardDraft.model_validate(data)
            return True, draft, []
        except Exception as e:
            errors = []
            if hasattr(e, 'errors'):
                for err in e.errors():
                    loc = " -> ".join(str(l) for l in err.get('loc', []))
                    msg = err.get('msg', 'Unknown error')
                    errors.append(f"{loc}: {msg}")
            else:
                errors.append(str(e))
            return False, None, errors

    @staticmethod
    def get_warnings(draft: StoryboardDraft) -> List[str]:
        """Get non-critical warnings for a valid draft.

        Args:
            draft: Validated storyboard draft

        Returns:
            List of warning messages
        """
        warnings = []

        for i, shot in enumerate(draft.shots):
            # Check prompt length
            if len(shot.prompt) < 20:
                warnings.append(f"Shot {shot.shot_id}: Prompt is very short ({len(shot.prompt)} chars)")

            # Check for missing description
            if not shot.description:
                warnings.append(f"Shot {shot.shot_id}: Missing description")

            # Check unusual resolutions
            aspect_ratio = shot.width / shot.height
            if aspect_ratio < 0.5 or aspect_ratio > 2.5:
                warnings.append(f"Shot {shot.shot_id}: Unusual aspect ratio ({aspect_ratio:.2f})")

            # Check very long durations
            if shot.duration > 10:
                warnings.append(f"Shot {shot.shot_id}: Long duration ({shot.duration}s) may require many segments")

        # Check total duration
        total_duration = sum(s.duration for s in draft.shots)
        if total_duration > 120:
            warnings.append(f"Total duration is {total_duration:.1f}s - this will generate many video segments")

        return warnings


__all__ = [
    "KeyframeGeneratorInput",
    "VideoGeneratorInput",
    "ProjectCreateInput",
    "SettingsInput",
    "StoryboardFileInput",
    "WorkflowFileInput",
    "SelectionFileInput",
    # Storyboard Draft
    "ShotDraft",
    "StoryboardDraft",
    "StoryboardDraftValidator",
]
