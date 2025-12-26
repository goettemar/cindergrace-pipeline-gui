"""Utility to validate required model files referenced in a workflow"""
import os
from typing import Dict, Any, List, Set, Optional


MODEL_EXTENSIONS = (".safetensors", ".ckpt", ".pt", ".bin")


class ModelValidator:
    """Scan workflow dictionaries for referenced model files and ensure they exist locally."""

    def __init__(self, comfy_root: Optional[str] = None):
        self.comfy_root = comfy_root
        self.enabled = bool(comfy_root and os.path.exists(comfy_root))
        self._index = None  # type: Optional[Dict[str, List[str]]]

    def _build_index(self):
        if not self.enabled:
            self._index = {}
            return

        models_dir = os.path.join(self.comfy_root, "models")
        if not os.path.exists(models_dir):
            print(f"⚠️  Model directory not found: {models_dir}")
            self._index = {}
            return

        index: Dict[str, List[str]] = {}
        for root, _, files in os.walk(models_dir):
            for filename in files:
                key = filename.lower()
                index.setdefault(key, []).append(os.path.join(root, filename))

        self._index = index

    def _ensure_index(self):
        if self._index is None:
            self._build_index()

    def _extract_model_refs(self, workflow: Dict[str, Any]) -> Set[str]:
        refs: Set[str] = set()

        def scan(value):
            if isinstance(value, str) and value.lower().endswith(MODEL_EXTENSIONS):
                refs.add(os.path.basename(value))
            elif isinstance(value, list):
                for item in value:
                    scan(item)
            elif isinstance(value, dict):
                for item in value.values():
                    scan(item)

        for node in workflow.values():
            if isinstance(node, dict):
                inputs = node.get("inputs", {})
                scan(inputs)

        return refs

    def find_missing(self, workflow: Dict[str, Any]) -> List[str]:
        if not self.enabled:
            return []

        refs = self._extract_model_refs(workflow)
        if not refs:
            return []

        self._ensure_index()
        missing = []

        for ref in refs:
            if not self._has_model(ref):
                missing.append(ref)

        return sorted(missing)

    def _has_model(self, filename: str) -> bool:
        if not self._index:
            return False

        return filename.lower() in self._index

    def rebuild_index(self) -> int:
        """Rebuild the model index from scratch. Returns number of models found."""
        self._index = None
        self._build_index()
        return len(self._index) if self._index else 0


__all__ = ["ModelValidator"]
