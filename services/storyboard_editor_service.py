from typing import Dict, Any

from domain.models import Storyboard, Shot
from infrastructure.logger import get_logger

logger = get_logger(__name__)


class StoryboardEditorService:
    """Service for storyboard CRUD operations."""

    def __init__(self):
        self.logger = logger

    def create_new_storyboard(self, project_name: str) -> Storyboard:
        storyboard = Storyboard(
            project=project_name or "Untitled Project",
            shots=[],
            raw={
                "project": project_name or "Untitled Project",
                "shots": [],
            },
        )
        self.logger.info("Created new storyboard: %s", storyboard.project)
        return storyboard

    def add_shot(
        self,
        storyboard: Storyboard,
        shot_id: str,
        filename_base: str,
        description: str,
        prompt: str,
        duration: float,
        width: int | None = None,
        height: int | None = None,
        characters: list | None = None,
        character_lora: str | None = None,
        negative_prompt: str = "",
        full_prompt: str | None = None,
        presets: dict | None = None,
        flux: dict | None = None,
        wan: dict | None = None,
    ) -> Storyboard:
        """Add a new shot to the storyboard.

        Args:
            shot_id: Unique identifier for the shot
            filename_base: Base name for generated files
            description: Human-readable description
            prompt: Base prompt text
            duration: Duration in seconds
            width/height: Resolution (defaults to 1024x576)
            characters: List of character IDs (legacy, multi-select)
            character_lora: Single character LoRA ID (e.g., "cg_elena")
            negative_prompt: What to avoid in generation
            full_prompt: Computed prompt including preset texts
            presets: Dict of preset keys (style, lighting, mood, etc.)
            flux: Flux render settings (seed, cfg, steps)
            wan: Wan render settings (seed, cfg, steps, motion_strength)
        """
        shot_payload = {
            "shot_id": shot_id,
            "filename_base": filename_base,
            "description": description,
            "prompt": prompt,
            "duration": float(duration),
            "width": width or 1024,
            "height": height or 576,
        }

        # Character LoRAs (v2.1 format - legacy multi-select)
        if characters:
            shot_payload["characters"] = characters
        # Single character LoRA (new simplified format)
        if character_lora:
            shot_payload["character_lora"] = character_lora
        if negative_prompt:
            shot_payload["negative_prompt"] = negative_prompt
        if full_prompt:
            shot_payload["full_prompt"] = full_prompt
        if presets:
            shot_payload["presets"] = presets
        if flux:
            shot_payload["flux"] = flux
        if wan:
            shot_payload["wan"] = wan

        shot = Shot.from_dict(shot_payload)
        storyboard.shots.append(shot)
        storyboard.raw.setdefault("shots", []).append(shot_payload)
        self.logger.info("Added shot %s to storyboard %s", shot_id, storyboard.project)
        return storyboard

    def update_shot(self, storyboard: Storyboard, shot_index: int, **fields) -> Storyboard:
        """Update a shot at the given index.

        Supported fields:
            shot_id, filename_base, description, prompt, negative_prompt,
            full_prompt, duration, width, height, characters (list),
            presets (dict), flux (dict), wan (dict)
        """
        if shot_index < 0 or shot_index >= len(storyboard.shots):
            raise IndexError(f"Invalid shot index: {shot_index}")

        shot = storyboard.shots[shot_index]
        for key, value in fields.items():
            # Skip None values (but allow empty strings and empty lists)
            if value is None:
                continue
            # Skip empty strings except for fields that can be empty
            if isinstance(value, str) and value == "" and key not in ["negative_prompt"]:
                continue

            # Handle different field types
            if key == "duration":
                setattr(shot, key, float(value))
                shot.raw[key] = float(value)
            elif key in ["width", "height"]:
                if hasattr(shot, key):
                    setattr(shot, key, int(value))
                shot.raw[key] = int(value)
            elif key == "characters":
                # List of character IDs (v2.1 format)
                shot.characters = value if value else []
                shot.raw[key] = value if value else []
            elif key in ["negative_prompt", "full_prompt", "description"]:
                shot.raw[key] = value or ""
            elif key in ["presets", "flux", "wan"]:
                # Dict fields for preset system
                if value:
                    shot.raw[key] = value
                elif key in shot.raw:
                    del shot.raw[key]
            elif hasattr(shot, key):
                setattr(shot, key, value)
                shot.raw[key] = value
            else:
                # Store in raw for fields not in Shot model
                shot.raw[key] = value

        # Ensure storyboard.raw["shots"] is in sync with storyboard.shots
        storyboard.raw.setdefault("shots", [])

        # Ensure the raw shots list is long enough
        while len(storyboard.raw["shots"]) <= shot_index:
            storyboard.raw["shots"].append({})

        # Replace the entire shot dict in raw to ensure full sync
        storyboard.raw["shots"][shot_index] = shot.raw.copy()

        self.logger.info("Updated shot %s at index %s", shot.shot_id, shot_index)
        return storyboard

    def delete_shot(self, storyboard: Storyboard, shot_index: int) -> Storyboard:
        if shot_index < 0 or shot_index >= len(storyboard.shots):
            raise IndexError(f"Invalid shot index: {shot_index}")

        removed = storyboard.shots.pop(shot_index)
        if storyboard.raw.get("shots") and shot_index < len(storyboard.raw["shots"]):
            storyboard.raw["shots"].pop(shot_index)
        self.logger.info("Deleted shot %s from storyboard %s", removed.shot_id, storyboard.project)
        return storyboard

    def get_next_shot_id(self, storyboard: Storyboard) -> str:
        max_id = 0
        for shot in storyboard.shots:
            try:
                max_id = max(max_id, int(shot.shot_id))
            except ValueError:
                continue
        return f"{max_id + 1:03d}"

    def storyboard_to_dict(self, storyboard: Storyboard) -> Dict[str, Any]:
        if storyboard.raw:
            return storyboard.raw
        return {
            "project": storyboard.project,
            "version": storyboard.version,
            "description": storyboard.description,
            "shots": [shot.raw for shot in storyboard.shots],
        }
