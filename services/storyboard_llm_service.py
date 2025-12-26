"""Service for LLM-based storyboard generation via OpenRouter.

Orchestrates the OpenRouter client and storyboard validation.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from domain.exceptions import OpenRouterAPIError, StoryboardValidationError
from domain.validators import StoryboardDraft, StoryboardDraftValidator
from infrastructure.config_manager import ConfigManager
from infrastructure.logger import get_logger
from infrastructure.openrouter_client import OpenRouterClient

logger = get_logger(__name__)


class StoryboardLLMService:
    """Service for generating storyboards from natural language via LLM."""

    def __init__(self, config: ConfigManager = None):
        """Initialize service.

        Args:
            config: ConfigManager instance (creates new one if not provided)
        """
        self.config = config or ConfigManager()
        self._prompt_template: Optional[str] = None

    def _get_client(self) -> OpenRouterClient:
        """Get OpenRouter client with current API key."""
        api_key = self.config.get_openrouter_api_key()
        if not api_key:
            raise OpenRouterAPIError("OpenRouter API key not configured")
        return OpenRouterClient(api_key)

    def get_prompt_template(self) -> str:
        """Load the prompt template for storyboard generation.

        Returns:
            System prompt template string
        """
        if self._prompt_template is not None:
            return self._prompt_template

        # Try to load from file
        template_paths = [
            Path(__file__).parent.parent / "data" / "templates" / "storyboard_prompt_template.txt",
            Path("data/templates/storyboard_prompt_template.txt"),
        ]

        for path in template_paths:
            if path.exists():
                self._prompt_template = path.read_text(encoding="utf-8")
                logger.info(f"Loaded prompt template from {path}")
                return self._prompt_template

        # Fallback to inline template
        logger.warning("Prompt template file not found, using inline fallback")
        self._prompt_template = self._get_fallback_template()
        return self._prompt_template

    def _get_fallback_template(self) -> str:
        """Get fallback prompt template."""
        return """Du bist ein Storyboard-Designer. Erstelle ein JSON-Storyboard mit diesem Schema:
{
  "project": "Name",
  "description": "Beschreibung",
  "version": "2.2",
  "shots": [
    {
      "shot_id": "001",
      "filename_base": "name-ohne-leerzeichen",
      "description": "Kurze Beschreibung",
      "prompt": "Detaillierter englischer Prompt...",
      "negative_prompt": "blurry, low quality",
      "width": 1024,
      "height": 576,
      "duration": 3.0
    }
  ]
}

Regeln:
- shot_id: "001", "002", etc.
- filename_base: lowercase, keine Leerzeichen
- duration: 3.0 Standard
- Nur valides JSON, keine Erklaerungen

Erstelle ein Storyboard fuer:
"""

    def get_available_models(self) -> List[str]:
        """Get list of configured models for dropdown.

        Returns:
            List of model IDs
        """
        return self.config.get_openrouter_models()

    def generate_draft(
        self,
        idea: str,
        model: str,
        temperature: float = 0.7,
    ) -> Tuple[Dict[str, Any], List[str], List[str]]:
        """Generate a storyboard draft from a natural language idea.

        Args:
            idea: User's video/storyboard idea
            model: OpenRouter model ID to use
            temperature: LLM temperature (0.0-1.0)

        Returns:
            Tuple of (storyboard_dict, errors, warnings)
            If errors is non-empty, storyboard_dict may be incomplete

        Raises:
            OpenRouterAPIError: For API errors
        """
        logger.info(f"Generating storyboard draft with {model}")
        logger.debug(f"Idea: {idea[:100]}...")

        # Get client and prompt template
        client = self._get_client()
        system_prompt = self.get_prompt_template()

        # Generate via LLM
        storyboard_dict = client.generate_storyboard(
            idea=idea,
            model=model,
            system_prompt=system_prompt,
            temperature=temperature,
        )

        # Validate the generated storyboard
        is_valid, draft, errors = StoryboardDraftValidator.validate_dict(storyboard_dict)

        if is_valid and draft:
            warnings = StoryboardDraftValidator.get_warnings(draft)
            logger.info(f"Draft generated successfully: {len(draft.shots)} shots")
            return storyboard_dict, [], warnings
        else:
            logger.warning(f"Draft validation failed: {errors}")
            return storyboard_dict, errors, []

    def validate_draft(self, json_str: str) -> Tuple[bool, List[str], List[str]]:
        """Validate a storyboard draft JSON string.

        Args:
            json_str: JSON string to validate

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        is_valid, draft, errors = StoryboardDraftValidator.validate_json_string(json_str)

        if is_valid and draft:
            warnings = StoryboardDraftValidator.get_warnings(draft)
            return True, [], warnings
        else:
            return False, errors, []

    def draft_to_storyboard_dict(self, draft: StoryboardDraft) -> Dict[str, Any]:
        """Convert a validated draft to a storyboard dictionary.

        Args:
            draft: Validated StoryboardDraft

        Returns:
            Dictionary suitable for saving as storyboard JSON
        """
        return {
            "project": draft.project,
            "description": draft.description or "",
            "version": draft.version,
            "shots": [
                {
                    "shot_id": shot.shot_id,
                    "filename_base": shot.filename_base,
                    "description": shot.description or "",
                    "prompt": shot.prompt,
                    "negative_prompt": shot.negative_prompt or "blurry, low quality, distorted",
                    "width": shot.width,
                    "height": shot.height,
                    "duration": shot.duration,
                    "presets": shot.presets or {},
                }
                for shot in draft.shots
            ],
            "video_settings": draft.video_settings or {
                "default_fps": 24,
                "max_duration": 3.0,
            },
        }

    def save_storyboard(
        self,
        storyboard_dict: Dict[str, Any],
        output_path: str,
    ) -> str:
        """Save a storyboard to a JSON file.

        Args:
            storyboard_dict: Storyboard dictionary
            output_path: Path to save to

        Returns:
            Absolute path to saved file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(storyboard_dict, f, indent=2, ensure_ascii=False)

        logger.info(f"Storyboard saved to {output_path}")
        return str(output_path.absolute())

    def test_connection(self) -> Dict[str, Any]:
        """Test OpenRouter API connection.

        Returns:
            Dict with connection status

        Raises:
            OpenRouterAPIError: If connection fails
        """
        client = self._get_client()
        return client.test_connection()


__all__ = ["StoryboardLLMService"]
