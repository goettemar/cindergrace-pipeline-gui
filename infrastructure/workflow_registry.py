"""Workflow preset registry and helpers"""
import json
import os
from typing import Dict, List, Any, Optional


class WorkflowRegistry:
    """Manage categorized workflow presets stored in config/workflow_presets.json"""

    def __init__(
        self,
        config_path: str = "config/workflow_presets.json",
        workflow_dir: str = "config/workflow_templates"
    ):
        self.config_path = config_path
        self.workflow_dir = workflow_dir

    # ------------------------------------------------------------------ #
    # Preset loading / saving
    # ------------------------------------------------------------------ #
    def _load_presets(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_path):
            return {"categories": {}}
        try:
            with open(self.config_path, "r") as f:
                return json.load(f)
        except Exception as exc:
            print(f"⚠️  Failed to load workflow presets ({exc}). Falling back to directory scan.")
            return {"categories": {}}

    def get_presets(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        data = self._load_presets()
        categories = data.get("categories", {})
        if category:
            return categories.get(category, [])

        presets: List[Dict[str, Any]] = []
        for items in categories.values():
            presets.extend(items)
        return presets

    def get_files(self, category: Optional[str] = None) -> List[str]:
        presets = self.get_presets(category)
        files: List[str] = []
        seen = set()

        for preset in presets:
            file_name = preset.get("file")
            if not file_name or file_name in seen:
                continue
            path = os.path.join(self.workflow_dir, file_name)
            if os.path.exists(path):
                files.append(file_name)
                seen.add(file_name)
            else:
                print(f"⚠️  Workflow preset missing file: {file_name} ({path})")

        if files:
            return files

        # fallback: scan directory
        if not os.path.exists(self.workflow_dir):
            return []

        return sorted(
            [
                f for f in os.listdir(self.workflow_dir)
                if f.endswith(".json")
            ]
        )

    def get_default(self, category: Optional[str] = None) -> Optional[str]:
        presets = self.get_presets(category)

        for preset in presets:
            if preset.get("default"):
                file_name = preset.get("file")
                if file_name:
                    path = os.path.join(self.workflow_dir, file_name)
                    if os.path.exists(path):
                        return file_name

        files = self.get_files(category)
        return files[0] if files else None

    # ------------------------------------------------------------------ #
    # Raw config helpers (used by Settings tab)
    # ------------------------------------------------------------------ #
    def read_raw(self) -> str:
        if not os.path.exists(self.config_path):
            return json.dumps({"categories": {}}, indent=2)
        with open(self.config_path, "r") as f:
            return f.read()

    def save_raw(self, content: str) -> str:
        try:
            data = json.loads(content)
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w") as f:
                json.dump(data, f, indent=2)
            return "**✅ Gespeichert:** workflow_presets.json aktualisiert."
        except json.JSONDecodeError as exc:
            return f"**❌ Fehler:** Ungültiges JSON ({exc})"
        except Exception as exc:
            return f"**❌ Fehler:** Konnte workflow_presets.json nicht speichern ({exc})"


__all__ = ["WorkflowRegistry"]
