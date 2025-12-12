"""Service helpers for keyframe selection and export."""
import glob
import json
import os
import shutil
from datetime import datetime
from typing import Dict, Any, List

from infrastructure.project_store import ProjectStore


class SelectionService:
    def __init__(self, project_store: ProjectStore):
        self.project_store = project_store

    def collect_keyframes(self, project: Dict[str, Any], filename_base: str) -> List[Dict[str, Any]]:
        directory = self.project_store.ensure_dir(project, "keyframes")
        pattern = os.path.join(directory, f"{filename_base}_v*.png")
        files = sorted(glob.glob(pattern))
        keyframes: List[Dict[str, Any]] = []
        for idx, path in enumerate(files, start=1):
            filename = os.path.basename(path)
            variant = self._extract_variant(filename) or idx
            keyframes.append(
                {
                    "variant": variant,
                    "filename": filename,
                    "path": path,
                    "label": f"Var {variant} – {filename}",
                    "caption": f"{filename_base} · Var {variant}",
                }
            )
        return keyframes

    def export_selections(
        self,
        project: Dict[str, Any],
        storyboard: Dict[str, Any],
        selections_state: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        export_payload = self._build_payload(storyboard, selections_state)
        export_payload["exported_at"] = datetime.utcnow().isoformat()

        selected_dir = self.project_store.ensure_dir(project, "selected")
        export_path = os.path.join(selected_dir, "selected_keyframes.json")

        copied = 0
        for selection in export_payload.get("selections", []):
            source = selection.get("source_path")
            if not source or not os.path.exists(source):
                continue
            dest = os.path.join(selected_dir, selection["selected_file"])
            shutil.copy2(source, dest)
            selection["export_path"] = dest
            copied += 1

        with open(export_path, "w") as f:
            json.dump(export_payload, f, indent=2)

        export_payload["_copied"] = copied
        export_payload["_path"] = export_path
        return export_payload

    def _build_payload(self, storyboard: Dict[str, Any], selections_state: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        payload = {
            "project": storyboard.get("project", ""),
            "total_shots": len(storyboard.get("shots", [])),
            "selections": list(selections_state.values()),
        }
        return payload

    @staticmethod
    def _extract_variant(filename: str) -> int:
        import re

        match = re.search(r"_v(\d+)", filename)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None


__all__ = ["SelectionService"]
