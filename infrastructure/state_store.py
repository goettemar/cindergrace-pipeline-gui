"""Simple JSON-based state store for persisting addon state."""
import json
import os
from typing import Any, Dict, Optional


class VideoGeneratorStateStore:
    """Persist video generator UI state (selected files, plans, status texts)."""

    def __init__(self, state_path: Optional[str] = None):
        self.state_path = state_path

    def configure(self, state_path: Optional[str]):
        self.state_path = state_path

    def load(self) -> Dict[str, Any]:
        if not self.state_path or not os.path.exists(self.state_path):
            return {}
        try:
            with open(self.state_path, "r") as f:
                return json.load(f)
        except Exception as exc:
            print(f"⚠️  Failed to load video generator state ({exc})")
            return {}

    def save(self, data: Dict[str, Any]):
        if not self.state_path:
            return
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            with open(self.state_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as exc:
            print(f"⚠️  Failed to save video generator state ({exc})")

    def update(self, **kwargs):
        if not self.state_path:
            return
        state = self.load()
        for key, value in kwargs.items():
            state[key] = value
        self.save(state)

    def clear(self):
        if self.state_path and os.path.exists(self.state_path):
            try:
                os.remove(self.state_path)
            except Exception as exc:
                print(f"⚠️  Failed to clear video generator state ({exc})")


__all__ = ["VideoGeneratorStateStore"]
