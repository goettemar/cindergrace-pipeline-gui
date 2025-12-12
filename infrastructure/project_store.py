"""Project management helper for CINDERGRACE pipeline."""
import json
import os
import re
import platform
from datetime import datetime
from typing import Dict, List, Optional

from infrastructure.config_manager import ConfigManager

# Platform-specific file locking
_HAS_FCNTL = False
if platform.system() != "Windows":
    try:
        import fcntl
        _HAS_FCNTL = True
    except ImportError:
        pass


class ProjectStore:
    """Handle creation, discovery and selection of pipeline projects."""

    PROJECT_FILE = "project.json"

    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config or ConfigManager()

    # -----------------------------
    # Basic paths
    # -----------------------------
    def _comfy_output_root(self) -> str:
        """Return ComfyUI output directory (validated)."""
        self.config.refresh()
        comfy_root = os.path.expanduser(self.config.get("comfy_root", ""))
        if not comfy_root or not os.path.isdir(comfy_root):
            raise FileNotFoundError(
                f"ComfyUI-Pfad nicht gefunden: {comfy_root or '(leer)'} – bitte im Settings-Tab korrigieren."
            )

        output_root = os.path.join(comfy_root, "output")
        os.makedirs(output_root, exist_ok=True)
        return output_root

    def _project_dir(self, slug: str) -> str:
        return os.path.join(self._comfy_output_root(), slug)

    def _project_file(self, slug: str) -> str:
        return os.path.join(self._project_dir(slug), self.PROJECT_FILE)

    # -----------------------------
    # Public helpers
    # -----------------------------
    def list_projects(self) -> List[Dict[str, str]]:
        """Return all discovered projects (slug, name, path)."""
        projects = []
        try:
            root = self._comfy_output_root()
        except FileNotFoundError:
            return projects

        for entry in sorted(os.listdir(root)):
            project_dir = os.path.join(root, entry)
            config_path = os.path.join(project_dir, self.PROJECT_FILE)
            if not os.path.isdir(project_dir) or not os.path.exists(config_path):
                continue
            data = self._read_project_file(config_path)
            data.setdefault("name", entry)
            data["slug"] = entry
            data["path"] = project_dir
            projects.append(data)

        return projects

    def get_active_project(self, refresh: bool = False) -> Optional[Dict[str, str]]:
        """Return currently active project (or None)."""
        if refresh:
            self.config.refresh()
        slug = self.config.get("current_project")
        if not slug:
            return None
        return self.load_project(slug)

    def load_project(self, slug: str) -> Optional[Dict[str, str]]:
        """Load project metadata by slug."""
        config_path = self._project_file(slug)
        if not os.path.exists(config_path):
            return None

        data = self._read_project_file(config_path)
        data["slug"] = slug
        data["path"] = self._project_dir(slug)
        data.setdefault("name", slug)
        return data

    def set_active_project(self, slug: str) -> Optional[Dict[str, str]]:
        """Persist active project slug + update last_opened."""
        project = self.load_project(slug)
        if not project:
            return None

        self.config.set("current_project", slug)
        project["last_opened"] = datetime.utcnow().isoformat()
        self._write_project_file(project)
        return project

    def create_project(self, name: str) -> Dict[str, str]:
        """Create new project folder + config file."""
        if not name or not name.strip():
            raise ValueError("Projektname darf nicht leer sein.")

        base_slug = self._slugify(name)
        slug = base_slug
        counter = 2
        while os.path.exists(self._project_dir(slug)):
            slug = f"{base_slug}-{counter}"
            counter += 1

        project_dir = self._project_dir(slug)
        os.makedirs(project_dir, exist_ok=True)

        data = {
            "name": name.strip(),
            "slug": slug,
            "created_at": datetime.utcnow().isoformat(),
            "last_opened": datetime.utcnow().isoformat(),
            "version": "0.10-beta"
        }
        self._write_project_file({"path": project_dir, **data})
        self.config.set("current_project", slug)
        return self.load_project(slug)

    def ensure_dir(self, project: Dict[str, str], *parts: str) -> str:
        """Ensure subdirectory exists for active project."""
        if not project:
            raise RuntimeError("Kein aktives Projekt gesetzt.")
        path = os.path.join(project["path"], *parts)
        os.makedirs(path, exist_ok=True)
        return path

    def project_path(self, project: Dict[str, str], *parts: str) -> str:
        if not project:
            raise RuntimeError("Kein aktives Projekt gesetzt.")
        return os.path.join(project["path"], *parts) if parts else project["path"]

    def comfy_output_dir(self) -> str:
        """Expose validated ComfyUI/output path."""
        return self._comfy_output_root()

    # -----------------------------
    # Internal helpers
    # -----------------------------
    def _slugify(self, name: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip().lower())
        slug = re.sub(r"-{2,}", "-", slug).strip("-")
        return slug or "project"

    def _read_project_file(self, path: str) -> Dict[str, str]:
        with open(path, "r") as f:
            data = json.load(f)
        return data

    def _write_project_file(self, project: Dict[str, str]):
        """Write project file with file-locking to prevent race conditions.

        On Linux/Mac, uses fcntl for exclusive locks.
        On Windows, relies on atomic file operations (no locking available).
        """
        path = project["path"] if "path" in project else self._project_dir(project["slug"])
        os.makedirs(path, exist_ok=True)
        file_path = os.path.join(path, self.PROJECT_FILE)
        data = {k: v for k, v in project.items() if k not in {"path"}}

        with open(file_path, "w", encoding="utf-8") as f:
            # Acquire exclusive lock (Linux/Mac only)
            if _HAS_FCNTL:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)

            try:
                json.dump(data, f, indent=2, ensure_ascii=False)
            finally:
                # Release lock (Linux/Mac only)
                if _HAS_FCNTL:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)


__all__ = ["ProjectStore"]
