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
        camera_movement: str = "static",
        width: int | None = None,
        height: int | None = None,
        character: str = "",
        negative_prompt: str = "",
        wan_motion: dict | None = None,
        seed: int = -1,
        cfg_scale: float = 7.0,
        steps: int = 20,
    ) -> Storyboard:
        shot_payload = {
            "shot_id": shot_id,
            "filename_base": filename_base,
            "description": description,
            "prompt": prompt,
            "duration": float(duration),
            "camera_movement": camera_movement,
            "width": width or 1024,
            "height": height or 576,
        }

        # Add optional fields if provided
        if character:
            shot_payload["character"] = character
        if negative_prompt:
            shot_payload["negative_prompt"] = negative_prompt
        if wan_motion:
            shot_payload["wan_motion"] = wan_motion
        if seed != -1:
            shot_payload["seed"] = seed
        if cfg_scale != 7.0:
            shot_payload["cfg_scale"] = cfg_scale
        if steps != 20:
            shot_payload["steps"] = steps

        shot = Shot.from_dict(shot_payload)
        setattr(shot, "camera_movement", camera_movement)
        storyboard.shots.append(shot)
        storyboard.raw.setdefault("shots", []).append(shot_payload)
        self.logger.info("Added shot %s to storyboard %s", shot_id, storyboard.project)
        return storyboard

    def update_shot(self, storyboard: Storyboard, shot_index: int, **fields) -> Storyboard:
        if shot_index < 0 or shot_index >= len(storyboard.shots):
            raise IndexError(f"Invalid shot index: {shot_index}")

        shot = storyboard.shots[shot_index]
        for key, value in fields.items():
            # Skip None/empty values except for special cases
            if value is None or (isinstance(value, str) and value == "" and key not in ["scene", "character", "negative_prompt"]):
                continue

            # Special handling for different field types
            if key == "camera_movement":
                setattr(shot, key, value)
                shot.raw[key] = value
            elif key == "duration":
                setattr(shot, key, float(value))
                shot.raw[key] = float(value)
            elif key in ["width", "height", "seed", "steps"]:
                # Integer fields
                if hasattr(shot, key):
                    setattr(shot, key, int(value))
                shot.raw[key] = int(value)
            elif key in ["cfg_scale"]:
                # Float fields
                shot.raw[key] = float(value)
            elif key in ["character", "negative_prompt"]:
                # String fields (can be empty)
                shot.raw[key] = value or ""
            elif key == "wan_motion":
                # wan_motion is a dict or None
                if value:
                    shot.wan_motion = type('MotionSettings', (), value)()
                    shot.raw[key] = value
                else:
                    shot.wan_motion = None
                    if key in shot.raw:
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
