"""Shared storyboard loading helpers."""

from typing import Optional, Tuple, Dict, Any

from domain import models as domain_models
from domain.storyboard_service import StoryboardService


def load_storyboard_from_config(config, apply_resolution: bool = False) -> Tuple[Optional[domain_models.Storyboard], str, Dict[str, Any]]:
    """Load current storyboard from config with consistent status output.

    Args:
        config: ConfigManager instance
        apply_resolution: Apply resolution override from config

    Returns:
        (storyboard_model or None, status_markdown, raw_dict)
    """
    storyboard_file = config.get_current_storyboard()
    if not storyboard_file:
        return None, "**Storyboard:** Not loaded yet", {}

    try:
        storyboard_model = StoryboardService.load_from_config(config, filename=storyboard_file)
        if apply_resolution:
            StoryboardService.apply_resolution_from_config(storyboard_model, config)
        status = f"**Storyboard:** ✅ {storyboard_model.project} – {len(storyboard_model.shots)} Shots loaded"
        return storyboard_model, status, storyboard_model.raw
    except Exception as exc:  # pragma: no cover - defensive UI helper
        return None, f"**Storyboard:** ❌ Error: {exc}", {}


__all__ = ["load_storyboard_from_config"]
