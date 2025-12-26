"""Workflow registry with prefix-based discovery and legacy presets."""
import json
import os
from typing import Dict, List, Optional, Tuple

from infrastructure.settings_store import SettingsStore
from infrastructure.logger import get_logger

logger = get_logger(__name__)


# Workflow prefixes
PREFIX_KEYFRAME = "gcp_"        # Keyframe/Picture generation (Flux, SDXL, etc.)
PREFIX_KEYFRAME_LORA = "gcpl_"  # Keyframe with LoRA support (auto-selected when character_lora set)
PREFIX_VIDEO = "gcv_"           # Video generation (Wan i2v, etc.)
PREFIX_VIDEO_FIRSTLAST = "gcvfl_"  # First-Last-Frame video (image morphing)
PREFIX_LIPSYNC = "gcl_"         # Lipsync (Wan is2v)

# All prefixes for bulk operations
ALL_PREFIXES = [PREFIX_KEYFRAME, PREFIX_KEYFRAME_LORA, PREFIX_VIDEO, PREFIX_VIDEO_FIRSTLAST, PREFIX_LIPSYNC]


class WorkflowRegistry:
    """Manage workflow discovery based on filename prefixes and legacy presets.

    Workflows are cached in SQLite database for stability.
    Use rescan() to update the cache when workflows are added/removed.

    Workflow prefixes:
    - gcp_* : Keyframe/Picture workflows (for Keyframe Generator)
    - gcpl_* : Keyframe with LoRA workflows
    - gcv_* : Video workflows (for Video Generator)
    - gcvfl_* : First-Last-Frame video workflows
    - gcl_* : Lipsync workflows (for Lipsync Addon)
    """

    def __init__(
        self,
        config_path: str = "config/workflow_presets.json",
        workflow_dir: str = "config/workflow_templates",
    ):
        self.config_path = config_path
        self.workflow_dir = workflow_dir
        self.settings_store = SettingsStore()

    # -----------------------------
    # Prefix-based discovery (new)
    # -----------------------------
    def _scan_filesystem(self, prefix: str) -> List[str]:
        """Scan workflow directory for files with given prefix (internal).

        Args:
            prefix: Filename prefix to filter (e.g., 'gcp_', 'gcv_', 'gcl_')

        Returns:
            Sorted list of matching workflow filenames (excludes _sage.json variants)
        """
        if not os.path.exists(self.workflow_dir):
            logger.warning(f"Workflow-Verzeichnis nicht gefunden: {self.workflow_dir}")
            return []

        workflows = []
        for filename in os.listdir(self.workflow_dir):
            if filename.startswith(prefix) and filename.endswith(".json"):
                # Skip _sage.json variants - they are auto-selected based on config
                if filename.endswith("_sage.json"):
                    continue
                workflows.append(filename)

        workflows.sort()
        return workflows

    def _get_files_by_prefix(self, prefix: str) -> List[str]:
        """Get workflow files for a prefix from cache.

        Reads from SQLite cache. If cache is empty, performs initial scan.

        Args:
            prefix: Workflow prefix ('gcp_', 'gcv_', 'gcl_', etc.)

        Returns:
            List of workflow filenames
        """
        # Try to get from cache - check if prefix has been scanned before
        if self.settings_store.has_workflow_cache(prefix):
            return self.settings_store.get_workflow_list(prefix)

        # Cache empty - perform initial scan
        logger.info(f"Kein Workflow-Cache für {prefix} - scanne Filesystem...")
        workflows = self._scan_filesystem(prefix)
        # Always save to cache, even if empty (to avoid re-scanning)
        self.settings_store.set_workflow_list(prefix, workflows)
        return workflows

    def rescan(self, prefix: str = None) -> Tuple[int, List[str]]:
        """Rescan filesystem and update cache.

        Args:
            prefix: Specific prefix to rescan, or None for all prefixes

        Returns:
            Tuple of (total_count, list_of_prefixes_scanned)
        """
        prefixes = [prefix] if prefix else ALL_PREFIXES
        total = 0
        scanned = []

        for p in prefixes:
            workflows = self._scan_filesystem(p)
            self.settings_store.set_workflow_list(p, workflows)
            total += len(workflows)
            scanned.append(p)
            logger.info(f"Rescan {p}: {len(workflows)} Workflows gefunden")

        return total, scanned

    def _get_default_by_prefix(self, prefix: str) -> Optional[str]:
        """Get default workflow for a prefix from SQLite.

        Args:
            prefix: Workflow prefix ('gcp_', 'gcv_', 'gcl_')

        Returns:
            Default workflow filename or first available, or None
        """
        # Try to get saved default from database
        default = self.settings_store.get_default_workflow(prefix)

        if default:
            # Verify it's still in the cached list
            cached = self.get_files(prefix)
            if default in cached:
                return default
            else:
                logger.warning(f"Default Workflow '{default}' nicht mehr in Liste - verwende ersten")

        # Fallback to first available from cache
        workflows = self.get_files(prefix)
        if workflows:
            return workflows[0]
        return None

    def set_default(self, prefix: str, workflow_file: str) -> bool:
        """Set default workflow for a prefix in SQLite.

        Args:
            prefix: Workflow prefix ('gcp_', 'gcv_', 'gcl_')
            workflow_file: Workflow filename to set as default

        Returns:
            True if successful, False if file not in cache
        """
        # Verify it's in the cached list
        cached = self.get_files(prefix)
        if workflow_file not in cached:
            logger.error(f"Workflow '{workflow_file}' nicht in Cache - bitte zuerst scannen")
            return False

        # Verify prefix matches
        if not workflow_file.startswith(prefix):
            logger.error(f"Workflow {workflow_file} hat nicht Präfix {prefix}")
            return False

        self.settings_store.set_default_workflow(prefix, workflow_file)
        return True

    def get_workflow_path(self, filename: str) -> str:
        """Get full path to a workflow file.

        Args:
            filename: Workflow filename

        Returns:
            Full path to workflow file
        """
        return os.path.join(self.workflow_dir, filename)

    def workflow_exists(self, filename: str) -> bool:
        """Check if a workflow file exists on filesystem.

        Args:
            filename: Workflow filename

        Returns:
            True if file exists
        """
        return os.path.exists(self.get_workflow_path(filename))

    def get_display_name(self, filename: str) -> str:
        """Generate display name from workflow filename.

        Converts 'gcp_flux_krea_dev_fp8.json' to 'Flux Krea Dev Fp8'

        Args:
            filename: Workflow filename

        Returns:
            Human-readable display name
        """
        # Remove prefix and extension
        name = filename
        for prefix in ALL_PREFIXES:
            if name.startswith(prefix):
                name = name[len(prefix):]
                break

        if name.endswith(".json"):
            name = name[:-5]

        # Convert underscores to spaces and title case
        name = name.replace("_", " ").title()
        return name

    def get_dropdown_choices(self, prefix: str) -> List[tuple]:
        """Get workflow choices for Gradio dropdown.

        Args:
            prefix: Workflow prefix

        Returns:
            List of (display_name, filename) tuples
        """
        workflows = self.get_files(prefix)
        return [(self.get_display_name(f), f) for f in workflows]

    def get_lora_variant(self, workflow_file: str) -> Optional[str]:
        """Get LoRA variant of a keyframe workflow if it exists.

        Converts gcp_* to gcpl_* and checks if it exists in cache.

        Args:
            workflow_file: Original workflow filename (gcp_*)

        Returns:
            LoRA variant filename (gcpl_*) if exists, None otherwise
        """
        if not workflow_file or not workflow_file.startswith(PREFIX_KEYFRAME):
            return None

        # Convert gcp_ to gcpl_
        lora_file = PREFIX_KEYFRAME_LORA + workflow_file[len(PREFIX_KEYFRAME):]

        # Check if in cache
        lora_workflows = self.get_files(PREFIX_KEYFRAME_LORA)
        if lora_file in lora_workflows:
            logger.debug(f"LoRA-Variante gefunden: {lora_file}")
            return lora_file

        return None

    def has_lora_variant(self, workflow_file: str) -> bool:
        """Check if a LoRA variant exists for this workflow.

        Args:
            workflow_file: Original workflow filename (gcp_*)

        Returns:
            True if gcpl_* variant exists
        """
        return self.get_lora_variant(workflow_file) is not None

    def get_sage_variant(self, workflow_file: str) -> Optional[str]:
        """Get SageAttention variant of a workflow if it exists.

        Converts 'workflow.json' to 'workflow_sage.json' and checks filesystem.

        Args:
            workflow_file: Original workflow filename (e.g., 'gcv_wan22_14B_i2v_gguf.json')

        Returns:
            Sage variant filename (e.g., 'gcv_wan22_14B_i2v_gguf_sage.json') if exists, None otherwise
        """
        if not workflow_file or not workflow_file.endswith('.json'):
            return None

        # Insert _sage before .json
        base_name = workflow_file[:-5]  # Remove .json
        sage_file = f"{base_name}_sage.json"

        # Check if file exists
        sage_path = os.path.join(self.workflow_dir, sage_file)
        if os.path.exists(sage_path):
            logger.debug(f"SageAttention-Variante gefunden: {sage_file}")
            return sage_file

        return None

    def has_sage_variant(self, workflow_file: str) -> bool:
        """Check if a SageAttention variant exists for this workflow.

        Args:
            workflow_file: Original workflow filename

        Returns:
            True if *_sage.json variant exists
        """
        return self.get_sage_variant(workflow_file) is not None

    def resolve_workflow(self, workflow_file: str, use_sage: bool = False) -> str:
        """Resolve actual workflow file based on preferences.

        If use_sage is True and a _sage.json variant exists, returns that.
        Otherwise returns the original workflow file.

        Args:
            workflow_file: Base workflow filename
            use_sage: Whether to prefer SageAttention variant

        Returns:
            Resolved workflow filename (original or _sage variant)
        """
        if use_sage:
            sage_variant = self.get_sage_variant(workflow_file)
            if sage_variant:
                logger.info(f"Verwende SageAttention-Workflow: {sage_variant}")
                return sage_variant
            else:
                logger.debug(f"Keine SageAttention-Variante für {workflow_file}")

        return workflow_file

    def get_status(self) -> dict:
        """Get status information about the workflow registry.

        Returns:
            Status dictionary with counts per prefix
        """
        return {
            "workflow_dir": self.workflow_dir,
            "workflow_dir_exists": os.path.exists(self.workflow_dir),
            "keyframe_workflows": len(self._get_files_by_prefix(PREFIX_KEYFRAME)),
            "keyframe_lora_workflows": len(self._get_files_by_prefix(PREFIX_KEYFRAME_LORA)),
            "video_workflows": len(self._get_files_by_prefix(PREFIX_VIDEO)),
            "firstlast_workflows": len(self._get_files_by_prefix(PREFIX_VIDEO_FIRSTLAST)),
            "lipsync_workflows": len(self._get_files_by_prefix(PREFIX_LIPSYNC)),
            "default_keyframe": self._get_default_by_prefix(PREFIX_KEYFRAME),
            "default_video": self._get_default_by_prefix(PREFIX_VIDEO),
            "default_firstlast": self._get_default_by_prefix(PREFIX_VIDEO_FIRSTLAST),
            "default_lipsync": self._get_default_by_prefix(PREFIX_LIPSYNC),
        }

    def get_models_file_path(self, workflow_file: str) -> str:
        """Get path to the .models sidecar file for a workflow.

        Args:
            workflow_file: Workflow filename (e.g., 'gcp_flux1_krea_dev.json')

        Returns:
            Path to .models file (e.g., '/path/to/gcp_flux1_krea_dev.models')
        """
        base_name = workflow_file.rsplit('.', 1)[0]  # Remove .json
        return os.path.join(self.workflow_dir, f"{base_name}.models")

    def get_compatible_models(self, workflow_file: str) -> List[str]:
        """Parse .models sidecar file and return list of compatible model paths.

        Args:
            workflow_file: Workflow filename

        Returns:
            List of model paths (relative to ComfyUI/models/), empty if no .models file
        """
        slot_models = self.get_compatible_models_by_slot(workflow_file)
        # Flatten all slots to a simple list for backward compatibility
        models = []
        for slot_list in slot_models.values():
            models.extend(slot_list)
        return models

    def get_compatible_models_by_slot(self, workflow_file: str) -> Dict[str, List[str]]:
        """Parse .models sidecar file with slot support.

        Supports slot syntax for multi-model workflows:
            # Main/default slot (no prefix or [main])
            diffusion_models/model.safetensors

            # Named slots
            [high]
            diffusion_models/model_high.gguf

            [low]
            diffusion_models/model_low.gguf

        Args:
            workflow_file: Workflow filename

        Returns:
            Dict mapping slot names to model lists. "" key = main/default slot.
        """
        models_path = self.get_models_file_path(workflow_file)

        if not os.path.exists(models_path):
            logger.debug(f"Keine .models Datei für {workflow_file}")
            return {}

        result: Dict[str, List[str]] = {"": []}  # "" = main slot
        current_slot = ""

        try:
            with open(models_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue

                    # Check for slot marker [name]
                    if line.startswith('[') and line.endswith(']'):
                        slot_name = line[1:-1].lower()
                        if slot_name == "main":
                            current_slot = ""
                        else:
                            current_slot = slot_name
                        if current_slot not in result:
                            result[current_slot] = []
                        continue

                    # Add model to current slot
                    result[current_slot].append(line)

            # Remove empty slots
            result = {k: v for k, v in result.items() if v}

            total = sum(len(v) for v in result.values())
            logger.info(f"Geladene kompatible Modelle für {workflow_file}: {total} in {len(result)} Slot(s)")
            return result
        except Exception as e:
            logger.error(f"Fehler beim Lesen von {models_path}: {e}")
            return {}

    def get_available_compatible_models(
        self,
        workflow_file: str,
        comfy_models_dir: str
    ) -> List[Tuple[str, str]]:
        """Get models that are both compatible AND available on filesystem.

        Args:
            workflow_file: Workflow filename
            comfy_models_dir: Path to ComfyUI/models directory

        Returns:
            List of (display_name, relative_path) tuples for available models
        """
        compatible = self.get_compatible_models(workflow_file)

        if not compatible:
            # No .models file - return empty (no model selection)
            return []

        available = []
        for model_path in compatible:
            full_path = os.path.join(comfy_models_dir, model_path)
            if os.path.exists(full_path):
                # Create display name from filename
                filename = os.path.basename(model_path)
                display_name = filename.rsplit('.', 1)[0]  # Remove extension
                available.append((display_name, model_path))
            else:
                logger.debug(f"Kompatibles Modell nicht verfügbar: {model_path}")

        logger.info(f"Verfügbare kompatible Modelle: {len(available)} von {len(compatible)}")
        return available

    def get_available_compatible_models_by_slot(
        self,
        workflow_file: str,
        comfy_models_dir: str
    ) -> Dict[str, List[Tuple[str, str]]]:
        """Get available models organized by slot.

        Args:
            workflow_file: Workflow filename
            comfy_models_dir: Path to ComfyUI/models directory

        Returns:
            Dict mapping slot names to lists of (display_name, relative_path) tuples.
            "" key = main/default slot.
        """
        slot_models = self.get_compatible_models_by_slot(workflow_file)

        if not slot_models:
            return {}

        result: Dict[str, List[Tuple[str, str]]] = {}
        for slot, models in slot_models.items():
            available = []
            for model_path in models:
                full_path = os.path.join(comfy_models_dir, model_path)
                if os.path.exists(full_path):
                    filename = os.path.basename(model_path)
                    display_name = filename.rsplit('.', 1)[0]
                    available.append((display_name, model_path))
                else:
                    logger.debug(f"Kompatibles Modell nicht verfügbar: {model_path}")
            if available:
                result[slot] = available

        return result

    def get_slot_names(self, workflow_file: str) -> List[str]:
        """Get list of model slot names defined in .models file.

        Args:
            workflow_file: Workflow filename

        Returns:
            List of slot names ([""] for single-slot, ["high", "low"] for multi-slot, etc.)
        """
        slot_models = self.get_compatible_models_by_slot(workflow_file)
        return list(slot_models.keys())

    def has_models_file(self, workflow_file: str) -> bool:
        """Check if a .models sidecar file exists for this workflow.

        Args:
            workflow_file: Workflow filename

        Returns:
            True if .models file exists
        """
        return os.path.exists(self.get_models_file_path(workflow_file))

    # -----------------------------
    # Legacy presets (workflow_presets.json)
    # -----------------------------
    def _load_presets(self) -> Dict[str, Dict[str, list]]:
        """Load legacy presets JSON file."""
        if not os.path.exists(self.config_path):
            return {"categories": {}}
        try:
            with open(self.config_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict) or "categories" not in data:
                return {"categories": {}}
            return data
        except Exception:
            print("⚠️ Failed to load workflow presets")
            return {"categories": {}}

    def get_presets(self, category: Optional[str] = None) -> List[Dict[str, str]]:
        """Return workflow presets from config file."""
        data = self._load_presets()
        categories = data.get("categories", {})
        if category:
            return list(categories.get(category, []))
        presets: List[Dict[str, str]] = []
        for entries in categories.values():
            presets.extend(entries)
        return presets

    def _get_files_from_presets(self, category: Optional[str] = None) -> List[str]:
        """Get workflow files using legacy presets."""
        presets = self.get_presets(category=category)
        files: List[str] = []
        for entry in presets:
            filename = entry.get("file")
            if not filename:
                continue
            full_path = os.path.join(self.workflow_dir, filename)
            if os.path.exists(full_path):
                if filename not in files:
                    files.append(filename)
            else:
                print(f"⚠️ Workflow preset missing file: {filename}")

        if files:
            return files

        # Fallback to scanning directory
        if not os.path.isdir(self.workflow_dir):
            return []
        for filename in sorted(os.listdir(self.workflow_dir)):
            if filename.endswith(".json"):
                files.append(filename)
        return files

    def read_raw(self) -> str:
        """Read raw preset JSON content."""
        if not os.path.exists(self.config_path):
            return json.dumps({"categories": {}}, indent=2)
        with open(self.config_path, "r", encoding="utf-8") as handle:
            return handle.read()

    def save_raw(self, content: str) -> str:
        """Validate and save preset JSON content."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return "❌ Fehler: Ungültiges JSON"

        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        try:
            with open(self.config_path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
            display_name = "workflow_presets.json"
            return f"✅ Gespeichert: {display_name}"
        except Exception as exc:
            display_name = "workflow_presets.json"
            return f"❌ Fehler: Konnte {display_name} nicht speichern ({exc})"

    # -----------------------------
    # Compatibility dispatchers
    # -----------------------------
    def get_files(self, prefix: Optional[str] = None, category: Optional[str] = None) -> List[str]:
        """Get workflow files by prefix (new) or category (legacy)."""
        if prefix in ALL_PREFIXES:
            return self._get_files_by_prefix(prefix)

        if category is None and prefix:
            category = prefix
        return self._get_files_from_presets(category)

    def get_default(self, prefix: Optional[str] = None, category: Optional[str] = None) -> Optional[str]:
        """Get default workflow for prefix (new) or category (legacy)."""
        if prefix in ALL_PREFIXES:
            return self._get_default_by_prefix(prefix)

        if category is None and prefix:
            category = prefix

        presets = self.get_presets(category=category)
        if not presets:
            files = self._get_files_from_presets(category)
            return files[0] if files else None

        # Find marked default
        for entry in presets:
            if entry.get("default"):
                filename = entry.get("file")
                if filename and os.path.exists(os.path.join(self.workflow_dir, filename)):
                    return filename

        # Fallback to first available file
        files = self._get_files_from_presets(category)
        return files[0] if files else None


__all__ = [
    "WorkflowRegistry",
    "PREFIX_KEYFRAME",
    "PREFIX_KEYFRAME_LORA",
    "PREFIX_VIDEO",
    "PREFIX_VIDEO_FIRSTLAST",
    "PREFIX_LIPSYNC",
    "ALL_PREFIXES",
]
