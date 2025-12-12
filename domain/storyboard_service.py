"""Service helpers for loading storyboards and selections."""
import json
import os
from typing import Dict, Any, Optional, Tuple

from domain.models import Storyboard, SelectionSet
from domain.exceptions import ValidationError


class StoryboardService:
    """Centralized service for storyboard loading and manipulation.

    Eliminates code duplication across addons by providing:
    - File loading with validation
    - Config-based loading
    - Global resolution overrides
    """

    @staticmethod
    def load_from_file(file_path: str) -> Storyboard:
        """Load and validate storyboard from JSON file.

        Args:
            file_path: Absolute path to storyboard JSON file

        Returns:
            Validated Storyboard domain model

        Raises:
            FileNotFoundError: If storyboard file doesn't exist
            ValidationError: If JSON is invalid or schema mismatch
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Storyboard nicht gefunden: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                payload: Dict[str, Any] = json.load(f)
            return Storyboard.from_dict(payload)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Ungültiges JSON in {file_path}: {e}")
        except Exception as e:
            raise ValidationError(f"Fehler beim Laden von {file_path}: {e}")

    @staticmethod
    def load_from_config(config_manager, filename: Optional[str] = None) -> Storyboard:
        """Load storyboard using ConfigManager (from project tab selection).

        Args:
            config_manager: ConfigManager instance
            filename: Optional filename override (uses project selection if None)

        Returns:
            Validated Storyboard domain model

        Raises:
            ValidationError: If no storyboard selected or file invalid
        """
        config_manager.refresh()
        storyboard_file = filename or config_manager.get_current_storyboard()

        if not storyboard_file:
            raise ValidationError(
                "Kein Storyboard gesetzt. Bitte im Tab '📁 Projekt' auswählen."
            )

        # Handle relative paths (fallback to config directory)
        if not os.path.exists(storyboard_file):
            candidate = os.path.join(config_manager.config_dir, storyboard_file)
            if os.path.exists(candidate):
                storyboard_file = candidate

        return StoryboardService.load_from_file(storyboard_file)

    @staticmethod
    def apply_global_resolution(
        storyboard: Storyboard,
        width: int,
        height: int
    ) -> Storyboard:
        """Override shot resolution with global preset.

        Args:
            storyboard: Storyboard to modify
            width: Target width in pixels
            height: Target height in pixels

        Returns:
            Modified storyboard (in-place modification)

        Note:
            This modifies the storyboard in-place and returns it for chaining.
        """
        for shot in storyboard.shots:
            shot.width = width
            shot.height = height
            shot.raw["width"] = width
            shot.raw["height"] = height

        return storyboard

    @staticmethod
    def apply_resolution_from_config(
        storyboard: Storyboard,
        config_manager
    ) -> Storyboard:
        """Apply resolution from ConfigManager preset.

        Args:
            storyboard: Storyboard to modify
            config_manager: ConfigManager with resolution preset

        Returns:
            Modified storyboard (in-place modification)
        """
        width, height = config_manager.get_resolution_tuple()
        return StoryboardService.apply_global_resolution(storyboard, width, height)


def load_storyboard(path: str) -> Storyboard:
    """Legacy function - use StoryboardService.load_from_file() instead.

    Kept for backwards compatibility.
    """
    return StoryboardService.load_from_file(path)


def load_selection(path: str) -> SelectionSet:
    """Load selection set from JSON file.

    Args:
        path: Absolute path to selection JSON file

    Returns:
        Validated SelectionSet domain model

    Raises:
        FileNotFoundError: If selection file doesn't exist
        ValidationError: If JSON is invalid
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Selection nicht gefunden: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            payload: Dict[str, Any] = json.load(f)
        return SelectionSet.from_dict(payload)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Ungültiges JSON in {path}: {e}")
    except Exception as e:
        raise ValidationError(f"Fehler beim Laden von {path}: {e}")


__all__ = [
    "StoryboardService",
    "load_storyboard",  # Legacy
    "load_selection"
]
