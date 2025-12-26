"""Character LoRA Service - Scan and manage character LoRA files."""
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

from infrastructure.config_manager import ConfigManager
from infrastructure.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CharacterLora:
    """Represents a character LoRA file.

    CINDERGRACE character LoRAs use the cg_* prefix.
    Example: cg_elena.safetensors -> id="cg_elena", name="Elena"

    Model compatibility is defined via optional .models sidecar file:
    cg_elena.models -> lists compatible diffusion models and model type
    """
    id: str  # Full ID with prefix, e.g., "cg_elena"
    name: str  # Display name, e.g., "Elena"
    trigger_word: str  # Same as id, used in prompts
    lora_file: str  # Filename, e.g., "cg_elena.safetensors"
    lora_path: str  # Full path to file
    strength: float = 1.0  # Fixed strength for character LoRAs
    compatible_models: Optional[List[str]] = None  # From .models sidecar file
    model_type: Optional[str] = None  # "flux", "sdxl", "sd3" from .models file


class CharacterLoraService:
    """Service for scanning and managing character LoRA files.

    LoRA files are expected in: <ComfyUI>/models/loras/
    Only files with prefix 'cg_' are recognized as CINDERGRACE characters.
    Naming convention: cg_<character_name>.safetensors

    The filename (without cg_ prefix and extension) becomes:
    - Character ID (e.g., "cg_elena" -> "elena")
    - Trigger word (for prompts)
    - Display name (with underscores replaced by spaces, title case)
    """

    DEFAULT_STRENGTH = 1.0  # Fixed strength for character LoRAs
    SUPPORTED_EXTENSIONS = ('.safetensors',)
    CG_PREFIX = "cg_"  # Prefix for CINDERGRACE character LoRAs

    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config or ConfigManager()
        self._cache: Optional[List[CharacterLora]] = None
        self._cache_mtime: float = 0

    def get_lora_directory(self) -> str:
        """Get the LoRA directory path.

        Returns <ComfyUI>/models/loras/ where cg_* character LoRAs are stored.
        """
        comfy_root = self.config.get_comfy_root()
        if comfy_root:
            lora_dir = os.path.join(comfy_root, "models", "loras")
            if os.path.isdir(lora_dir):
                return lora_dir
        return ""

    def scan_loras(self, force_refresh: bool = False) -> List[CharacterLora]:
        """Scan the LoRA directory for cg_* character LoRAs.

        Only files with 'cg_' prefix are recognized as CINDERGRACE characters.

        Args:
            force_refresh: If True, ignore cache and rescan

        Returns:
            List of CharacterLora objects
        """
        lora_dir = self.get_lora_directory()
        if not lora_dir or not os.path.isdir(lora_dir):
            logger.warning(f"LoRA directory not found: {lora_dir}")
            return []

        # Check cache validity
        try:
            current_mtime = os.path.getmtime(lora_dir)
            if not force_refresh and self._cache is not None and current_mtime <= self._cache_mtime:
                return self._cache
        except OSError:
            pass

        loras: List[CharacterLora] = []

        try:
            for filename in sorted(os.listdir(lora_dir)):
                # Only process cg_* files
                if not filename.lower().startswith(self.CG_PREFIX):
                    continue
                if not filename.lower().endswith(self.SUPPORTED_EXTENSIONS):
                    continue

                filepath = os.path.join(lora_dir, filename)
                if not os.path.isfile(filepath):
                    continue

                # Extract character info from filename
                # e.g., "cg_cindergrace.safetensors" -> id="cg_cindergrace", trigger="cindergrace"
                base_name = os.path.splitext(filename)[0]

                # The full cg_* name is the ID (for file matching)
                character_id = base_name.lower()

                # Trigger word: remove cg_ prefix (this is what goes in the prompt)
                trigger_word = base_name[len(self.CG_PREFIX):].lower()

                # Display name: format nicely (without prefix)
                display_name = self._id_to_display_name(trigger_word)

                # Check for .models sidecar file
                model_type, compatible_models = self._load_models_file(filepath)

                lora = CharacterLora(
                    id=character_id,
                    name=display_name,
                    trigger_word=trigger_word,  # "cindergrace" (without cg_ prefix)
                    lora_file=filename,
                    lora_path=filepath,
                    strength=self.DEFAULT_STRENGTH,
                    compatible_models=compatible_models,
                    model_type=model_type
                )
                loras.append(lora)
                logger.debug(f"Found character LoRA: {lora.id} ({lora.lora_file})")

            # Update cache
            self._cache = loras
            self._cache_mtime = current_mtime if 'current_mtime' in dir() else 0

            logger.info(f"Scanned {len(loras)} cg_* character LoRAs from {lora_dir}")

        except OSError as e:
            logger.error(f"Error scanning LoRA directory: {e}")
            return []

        return loras

    def _clean_character_id(self, base_name: str) -> str:
        """Clean up training artifacts from filename to get character ID.

        Examples:
            "cindergrace_rank16_bf16-step00750" -> "cindergrace"
            "elena_warrior" -> "elena_warrior"
            "marco" -> "marco"
        """
        # Common training artifact patterns to remove
        patterns_to_remove = [
            "_rank",  # LoRA rank info
            "_bf16",  # Precision info
            "_fp16",
            "-step",  # Step count
            "_step",
        ]

        result = base_name.lower()

        for pattern in patterns_to_remove:
            if pattern in result:
                # Cut off everything from the pattern onwards
                result = result.split(pattern)[0]

        return result.strip("_- ")

    def _id_to_display_name(self, character_id: str) -> str:
        """Convert character ID to display name.

        Examples:
            "elena" -> "Elena"
            "marco_knight" -> "Marco Knight"
        """
        return character_id.replace("_", " ").title()

    def _load_models_file(self, lora_path: str) -> Tuple[Optional[str], Optional[List[str]]]:
        """Load model type and compatible models from .models sidecar file.

        The .models file has the same base name as the .safetensors file.
        Example: cg_elena.safetensors -> cg_elena.models

        Format:
            type=flux           # Model type (flux, sdxl, sd3)
            model1.safetensors  # Compatible base models (one per line)
            model2.safetensors
        Lines starting with # are comments.

        Args:
            lora_path: Full path to the .safetensors file

        Returns:
            Tuple of (model_type, compatible_models_list)
            Both can be None if file doesn't exist or has no data
        """
        # Construct .models file path
        models_path = lora_path.rsplit('.', 1)[0] + '.models'

        if not os.path.exists(models_path):
            return None, None

        model_type = None
        models = []
        try:
            with open(models_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    # Parse type= line
                    if line.lower().startswith('type='):
                        model_type = line.split('=', 1)[1].strip().lower()
                        continue
                    models.append(line)

            if model_type:
                logger.debug(f"LoRA type from {models_path}: {model_type}")
            if models:
                logger.debug(f"Loaded {len(models)} compatible models from {models_path}")

            return model_type, models if models else None
        except Exception as e:
            logger.error(f"Error reading models file {models_path}: {e}")
            return None, None

    def get_lora(self, character_id: str) -> Optional[CharacterLora]:
        """Get a specific character LoRA by ID.

        Args:
            character_id: The character ID (e.g., "elena")

        Returns:
            CharacterLora if found, None otherwise
        """
        loras = self.scan_loras()
        for lora in loras:
            if lora.id == character_id:
                return lora
        return None

    def get_lora_by_file(self, filename: str) -> Optional[CharacterLora]:
        """Get a specific character LoRA by filename.

        Args:
            filename: The LoRA filename (e.g., "elena.safetensors")

        Returns:
            CharacterLora if found, None otherwise
        """
        loras = self.scan_loras()
        for lora in loras:
            if lora.lora_file == filename:
                return lora
        return None

    def get_choices(self) -> List[Tuple[str, str]]:
        """Get LoRA choices for Gradio Dropdown.

        Returns:
            List of (display_name, id) tuples for Dropdown choices
        """
        loras = self.scan_loras()
        return [(lora.name, lora.id) for lora in loras]

    def get_choices_with_none(self) -> List[Tuple[str, str]]:
        """Get LoRA choices with a 'None' option for Gradio Dropdown.

        Returns:
            List of (display_name, id) tuples, starting with ("Kein Character", "")
        """
        choices = [("Kein Character", "")]
        choices.extend(self.get_choices())
        return choices

    def get_choices_by_type(self, model_type: Optional[str] = None) -> List[Tuple[str, str]]:
        """Get LoRA choices filtered by model type.

        Args:
            model_type: Filter by type ("flux", "sdxl", "sd3").
                        If None, returns all LoRAs.

        Returns:
            List of (display_name, id) tuples
        """
        loras = self.scan_loras()
        if model_type is None:
            return [(lora.name, lora.id) for lora in loras]

        model_type = model_type.lower()
        return [
            (lora.name, lora.id)
            for lora in loras
            if lora.model_type is None or lora.model_type == model_type
        ]

    def get_choices_by_type_with_none(
        self,
        model_type: Optional[str] = None
    ) -> List[Tuple[str, str]]:
        """Get LoRA choices filtered by model type, with 'None' option.

        Args:
            model_type: Filter by type ("flux", "sdxl", "sd3").
                        If None, returns all LoRAs.
                        LoRAs without a type are always included.

        Returns:
            List of (display_name, id) tuples, starting with ("Kein Character", "")
        """
        choices = [("Kein Character", "")]
        choices.extend(self.get_choices_by_type(model_type))
        return choices

    def get_model_type(self, character_id: str) -> Optional[str]:
        """Get the model type for a character LoRA.

        Args:
            character_id: The character ID (e.g., "cg_elena")

        Returns:
            Model type ("flux", "sdxl", "sd3") or None if unknown
        """
        lora = self.get_lora(character_id)
        if not lora:
            return None
        return lora.model_type

    def validate_characters(self, character_ids: List[str]) -> Tuple[bool, List[str]]:
        """Validate that all character IDs have corresponding LoRA files.

        Args:
            character_ids: List of character IDs to validate

        Returns:
            Tuple of (all_valid, list_of_missing_ids)
        """
        if not character_ids:
            return True, []

        loras = self.scan_loras()
        available_ids = {lora.id for lora in loras}

        missing = [cid for cid in character_ids if cid and cid not in available_ids]

        return len(missing) == 0, missing

    def get_loras_for_shot(
        self,
        character_ids: List[str],
        storyboard_characters: Optional[List[dict]] = None
    ) -> List[CharacterLora]:
        """Get LoRA objects for a shot's characters, with optional strength overrides.

        Args:
            character_ids: List of character IDs used in the shot
            storyboard_characters: Optional list of character configs from storyboard
                                   with potential strength overrides

        Returns:
            List of CharacterLora objects with applied strength settings
        """
        if not character_ids:
            return []

        # Build strength override map from storyboard
        strength_overrides = {}
        if storyboard_characters:
            for char in storyboard_characters:
                char_id = char.get("id", "")
                if char_id and "strength" in char:
                    strength_overrides[char_id] = char["strength"]

        result = []
        for char_id in character_ids:
            lora = self.get_lora(char_id)
            if lora:
                # Apply strength override if exists
                if char_id in strength_overrides:
                    lora = CharacterLora(
                        id=lora.id,
                        name=lora.name,
                        trigger_word=lora.trigger_word,
                        lora_file=lora.lora_file,
                        lora_path=lora.lora_path,
                        strength=strength_overrides[char_id],
                        compatible_models=lora.compatible_models,
                        model_type=lora.model_type
                    )
                result.append(lora)
            else:
                logger.warning(f"Character LoRA not found: {char_id}")

        return result

    def has_model_restrictions(self, character_id: str) -> bool:
        """Check if a character has model compatibility restrictions.

        Args:
            character_id: The character ID (e.g., "cg_elena")

        Returns:
            True if character has a .models file defining type or compatible models
        """
        lora = self.get_lora(character_id)
        if not lora:
            return False
        has_type = lora.model_type is not None
        has_models = lora.compatible_models is not None and len(lora.compatible_models) > 0
        return has_type or has_models

    def is_model_compatible(
        self,
        character_id: str,
        model_path: str,
        workflow_type: Optional[str] = None
    ) -> bool:
        """Check if a diffusion model is compatible with a character LoRA.

        Args:
            character_id: The character ID (e.g., "cg_elena")
            model_path: Model path relative to ComfyUI/models/
            workflow_type: Optional workflow type ("flux", "sdxl", "sd3")
                          If not provided, will try to detect from model_path

        Returns:
            True if compatible or no restrictions defined, False if incompatible
        """
        lora = self.get_lora(character_id)
        if not lora:
            return True  # Character not found - let it fail later

        # Check model_type compatibility first (if LoRA has type defined)
        if lora.model_type:
            # Determine the workflow/model type
            detected_type = workflow_type or self._detect_model_type(model_path)
            if detected_type and detected_type != lora.model_type:
                return False

        # If no compatible_models list, type check is sufficient
        if lora.compatible_models is None:
            return True

        # Check if model_path matches any compatible model
        # Support both exact match and filename-only match
        model_filename = os.path.basename(model_path)

        for compatible in lora.compatible_models:
            if model_path == compatible:
                return True
            if model_filename == os.path.basename(compatible):
                return True

        return False

    def _detect_model_type(self, model_path: str) -> Optional[str]:
        """Detect model type from model path/filename.

        Args:
            model_path: Path to the model file

        Returns:
            Detected type ("flux", "sdxl", "sd3") or None
        """
        if not model_path:
            return None

        path_lower = model_path.lower()

        # Check for FLUX indicators
        if 'flux' in path_lower:
            return 'flux'

        # Check for SD3 indicators
        if 'sd3' in path_lower or 'sd_3' in path_lower:
            return 'sd3'

        # Check for SDXL indicators
        if 'sdxl' in path_lower or 'sd_xl' in path_lower:
            return 'sdxl'

        return None

    def get_compatible_models_for_character(self, character_id: str) -> Optional[List[str]]:
        """Get list of compatible models for a character.

        Args:
            character_id: The character ID (e.g., "cg_elena")

        Returns:
            List of compatible model paths, or None if no restrictions
        """
        lora = self.get_lora(character_id)
        if not lora:
            return None
        return lora.compatible_models

    def get_compatibility_warning(
        self,
        character_id: str,
        model_path: str,
        workflow_type: Optional[str] = None
    ) -> Optional[Tuple[str, List[str]]]:
        """Get compatibility warning message and suggested alternatives.

        Args:
            character_id: The character ID (e.g., "cg_elena")
            model_path: Selected model path
            workflow_type: Optional workflow type ("flux", "sdxl", "sd3")

        Returns:
            Tuple of (warning_message, list_of_compatible_models) if incompatible,
            None if compatible or no restrictions
        """
        if self.is_model_compatible(character_id, model_path, workflow_type):
            return None

        lora = self.get_lora(character_id)
        if not lora:
            return None

        model_name = os.path.basename(model_path)
        char_name = lora.name
        detected_type = workflow_type or self._detect_model_type(model_path)

        # Check if it's a model_type mismatch
        if lora.model_type and detected_type and lora.model_type != detected_type:
            warning = (
                f"⚠️ **LoRA-Typ Inkompatibilität:** Der Character **{char_name}** "
                f"wurde für **{lora.model_type.upper()}** trainiert, "
                f"aber das gewählte Model ist **{detected_type.upper()}**.\n\n"
                f"Bitte wähle ein {lora.model_type.upper()}-Modell oder einen anderen Character."
            )
            return warning, []

        # Fallback to compatible_models list warning
        compatible = lora.compatible_models or []
        if compatible:
            warning = (
                f"⚠️ **Model-Inkompatibilität:** Das gewählte Model `{model_name}` "
                f"ist nicht für den Character **{char_name}** getestet.\n\n"
                f"Der Character wurde trainiert für: {', '.join(os.path.basename(m) for m in compatible)}"
            )
        else:
            warning = (
                f"⚠️ **Model-Inkompatibilität:** Das gewählte Model `{model_name}` "
                f"ist möglicherweise nicht mit dem Character **{char_name}** kompatibel."
            )

        return warning, compatible
