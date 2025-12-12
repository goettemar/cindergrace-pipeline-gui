"""Pydantic validation models for CINDERGRACE input validation"""
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional
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


__all__ = [
    "KeyframeGeneratorInput",
    "VideoGeneratorInput",
    "ProjectCreateInput",
    "SettingsInput",
    "StoryboardFileInput",
    "WorkflowFileInput",
    "SelectionFileInput",
]
