"""Project management with SQLite storage for CINDERGRACE pipeline."""
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from infrastructure.config_manager import ConfigManager
from infrastructure.logger import get_logger

logger = get_logger(__name__)


def get_db_path() -> str:
    """Return path to cindergrace.db."""
    base_dir = Path(__file__).parent.parent
    return str(base_dir / "data" / "cindergrace.db")


class ProjectStore:
    """Handle creation, discovery and selection of pipeline projects using SQLite."""

    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config or ConfigManager()
        self.db_path = get_db_path()
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Create database and projects table if not exists."""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_opened TEXT,
                is_active INTEGER DEFAULT 0,
                version TEXT DEFAULT '1.0',
                current_storyboard TEXT
            )
        """)

        # Migration: Add current_storyboard column if missing (for existing databases)
        cursor.execute("PRAGMA table_info(projects)")
        columns = [col[1] for col in cursor.fetchall()]
        if "current_storyboard" not in columns:
            cursor.execute("ALTER TABLE projects ADD COLUMN current_storyboard TEXT")
            logger.info("Migration: current_storyboard Spalte hinzugefügt")

            # Migrate existing data from settings.json
            self._migrate_storyboard_from_json(cursor)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_projects_slug ON projects(slug)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_projects_active ON projects(is_active)
        """)

        conn.commit()
        conn.close()
        logger.debug(f"Projects-Datenbank initialisiert: {self.db_path}")

    def _migrate_storyboard_from_json(self, cursor) -> None:
        """Migrate current_storyboard from settings.json to active project in SQLite."""
        try:
            # Get current storyboard from JSON config
            old_storyboard = self.config.get("current_storyboard")
            if not old_storyboard:
                return

            # Find active project and update its storyboard
            cursor.execute("SELECT slug, path FROM projects WHERE is_active = 1 LIMIT 1")
            row = cursor.fetchone()
            if row:
                slug, project_path = row[0], row[1]
                # Only migrate if storyboard is in this project's directory
                if old_storyboard.startswith(project_path):
                    cursor.execute(
                        "UPDATE projects SET current_storyboard = ? WHERE slug = ?",
                        (old_storyboard, slug)
                    )
                    logger.info(f"Migration: Storyboard '{old_storyboard}' zu Projekt '{slug}' migriert")
        except Exception as e:
            logger.warning(f"Migration fehlgeschlagen: {e}")

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # -----------------------------
    # Path helpers
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
        """Return project directory path."""
        return os.path.join(self._comfy_output_root(), slug)

    # -----------------------------
    # Public API
    # -----------------------------
    def list_projects(self) -> List[Dict[str, str]]:
        """Return all projects from database."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT slug, name, path, created_at, last_opened, is_active, version, current_storyboard
            FROM projects
            ORDER BY last_opened DESC, name ASC
        """)

        projects = []
        for row in cursor.fetchall():
            projects.append({
                "slug": row["slug"],
                "name": row["name"],
                "path": row["path"],
                "created_at": row["created_at"],
                "last_opened": row["last_opened"],
                "is_active": bool(row["is_active"]),
                "version": row["version"],
                "current_storyboard": row["current_storyboard"],
            })

        conn.close()
        return projects

    def get_active_project(self, refresh: bool = False) -> Optional[Dict[str, str]]:
        """Return currently active project (or None)."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT slug, name, path, created_at, last_opened, version, current_storyboard
            FROM projects
            WHERE is_active = 1
            LIMIT 1
        """)

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "slug": row["slug"],
            "name": row["name"],
            "path": row["path"],
            "created_at": row["created_at"],
            "last_opened": row["last_opened"],
            "version": row["version"],
            "current_storyboard": row["current_storyboard"],
        }

    def load_project(self, slug: str) -> Optional[Dict[str, str]]:
        """Load project by slug."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT slug, name, path, created_at, last_opened, is_active, version, current_storyboard
            FROM projects
            WHERE slug = ?
        """, (slug,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "slug": row["slug"],
            "name": row["name"],
            "path": row["path"],
            "created_at": row["created_at"],
            "last_opened": row["last_opened"],
            "is_active": bool(row["is_active"]),
            "version": row["version"],
            "current_storyboard": row["current_storyboard"],
        }

    def set_active_project(self, slug: str) -> Optional[Dict[str, str]]:
        """Set project as active and update last_opened."""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Deactivate all projects
        cursor.execute("UPDATE projects SET is_active = 0")

        # Activate selected project and update last_opened
        now = datetime.utcnow().isoformat()
        cursor.execute("""
            UPDATE projects
            SET is_active = 1, last_opened = ?
            WHERE slug = ?
        """, (now, slug))

        conn.commit()
        conn.close()

        project = self.load_project(slug)

        # Update current_storyboard if needed
        if project:
            self._update_storyboard_for_project(project)

        return project

    def _update_storyboard_for_project(self, project: Dict[str, str]) -> None:
        """Ensure current_storyboard points to a file in the active project (stored in SQLite)."""
        current_sb = project.get("current_storyboard")
        project_path = project.get("path", "")
        slug = project.get("slug")

        # Check if current storyboard is already valid
        if current_sb and isinstance(current_sb, str) and project_path:
            if current_sb.startswith(project_path) and os.path.exists(current_sb):
                return  # Already valid, no change needed

        # Find available storyboards in the project
        storyboards_dir = os.path.join(project_path, "storyboards")
        if os.path.isdir(storyboards_dir):
            storyboards = [
                f for f in os.listdir(storyboards_dir)
                if f.endswith(".json")
            ]
            if storyboards:
                # Prefer example storyboard, otherwise take first available
                if "quick_demo.json" in storyboards:
                    new_sb = os.path.join(storyboards_dir, "quick_demo.json")
                else:
                    new_sb = os.path.join(storyboards_dir, storyboards[0])
                self._set_storyboard_in_db(slug, new_sb)
                logger.debug(f"Storyboard gewechselt: {new_sb}")
                return

        # No storyboard found - clear the setting
        self._set_storyboard_in_db(slug, None)

    def _set_storyboard_in_db(self, slug: str, storyboard_path: Optional[str]) -> None:
        """Set current_storyboard in SQLite database."""
        if not slug:
            return
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE projects SET current_storyboard = ? WHERE slug = ?",
            (storyboard_path, slug)
        )
        conn.commit()
        conn.close()

    def create_project(self, name: str) -> Dict[str, str]:
        """Create new project."""
        if not name or not name.strip():
            raise ValueError("Projektname darf nicht leer sein.")

        # Generate unique slug
        base_slug = self._slugify(name)
        slug = base_slug
        counter = 2

        conn = self._get_conn()
        cursor = conn.cursor()

        # Check for existing slugs
        while True:
            cursor.execute("SELECT 1 FROM projects WHERE slug = ?", (slug,))
            if not cursor.fetchone():
                break
            slug = f"{base_slug}-{counter}"
            counter += 1

        # Create project directory
        project_dir = self._project_dir(slug)
        os.makedirs(project_dir, exist_ok=True)

        # Create storyboards directory and copy example template
        storyboard_path = self._init_storyboards_dir(project_dir)

        now = datetime.utcnow().isoformat()

        # Deactivate all other projects
        cursor.execute("UPDATE projects SET is_active = 0")

        # Insert new project with storyboard
        cursor.execute("""
            INSERT INTO projects (slug, name, path, created_at, last_opened, is_active, version, current_storyboard)
            VALUES (?, ?, ?, ?, ?, 1, '1.0', ?)
        """, (slug, name.strip(), project_dir, now, now, storyboard_path))

        conn.commit()
        conn.close()

        logger.info(f"Projekt erstellt: {name} ({slug})")
        return self.load_project(slug)

    def _init_storyboards_dir(self, project_dir: str, template_name: str = None) -> Optional[str]:
        """Create storyboards directory and copy example template if available.

        Args:
            project_dir: Path to project directory
            template_name: Optional template filename (without path). If None, uses quick_demo.

        Returns:
            Path to the copied storyboard template, or None if not copied.
        """
        import shutil

        storyboards_dir = os.path.join(project_dir, "storyboards")
        os.makedirs(storyboards_dir, exist_ok=True)

        # Use specified template or default to quick_demo
        if template_name is None:
            template_name = "storyboard_quick_demo.json"

        template_path = Path(__file__).parent.parent / "data" / "templates" / template_name
        target_filename = template_name.replace("storyboard_", "")  # Remove prefix for cleaner name
        target_path = os.path.join(storyboards_dir, target_filename)

        if template_path.exists() and not os.path.exists(target_path):
            try:
                shutil.copy(str(template_path), target_path)
                logger.debug(f"Storyboard template copied: {target_path}")
                return target_path
            except Exception as e:
                logger.warning(f"Could not copy storyboard template: {e}")
                return None
        elif os.path.exists(target_path):
            return target_path
        return None

    def delete_project(self, slug: str) -> bool:
        """Delete a project from database and optionally from filesystem."""
        if not slug:
            return False

        project = self.load_project(slug)
        if not project:
            return False

        conn = self._get_conn()
        cursor = conn.cursor()

        # Remove from database
        cursor.execute("DELETE FROM projects WHERE slug = ?", (slug,))
        conn.commit()
        conn.close()

        # Optionally delete project directory
        project_dir = project.get("path")
        if project_dir and os.path.isdir(project_dir):
            import shutil
            try:
                shutil.rmtree(project_dir)
            except Exception as e:
                logger.warning(f"Konnte Projektordner nicht löschen: {e}")

        logger.info(f"Projekt gelöscht: {slug}")
        return True

    def update_project(self, slug: str, **kwargs) -> Optional[Dict[str, str]]:
        """Update project fields."""
        allowed_fields = {"name", "path", "last_opened", "version"}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return self.load_project(slug)

        conn = self._get_conn()
        cursor = conn.cursor()

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [slug]

        cursor.execute(f"""
            UPDATE projects
            SET {set_clause}
            WHERE slug = ?
        """, values)

        conn.commit()
        conn.close()

        return self.load_project(slug)

    def ensure_dir(self, project: Dict[str, str], *parts: str) -> str:
        """Ensure subdirectory exists for project."""
        if not project:
            raise RuntimeError("Kein aktives Projekt gesetzt.")
        path = os.path.join(project["path"], *parts)
        os.makedirs(path, exist_ok=True)
        return path

    def project_path(self, project: Dict[str, str], *parts: str) -> str:
        """Return path within project directory."""
        if not project:
            raise RuntimeError("Kein aktives Projekt gesetzt.")
        return os.path.join(project["path"], *parts) if parts else project["path"]

    def comfy_output_dir(self) -> str:
        """Expose validated ComfyUI/output path."""
        return self._comfy_output_root()

    # -----------------------------
    # Storyboard helpers
    # -----------------------------
    def get_project_storyboard_dir(self, project: Dict[str, str]) -> str:
        """Return path to project's storyboards directory."""
        if not project:
            raise RuntimeError("Kein aktives Projekt gesetzt.")
        return os.path.join(project["path"], "storyboards")

    def ensure_storyboard_dir(self, project: Dict[str, str]) -> str:
        """Create storyboards directory if not exists and return path."""
        storyboard_dir = self.get_project_storyboard_dir(project)
        os.makedirs(storyboard_dir, exist_ok=True)
        return storyboard_dir

    def get_current_storyboard(self) -> Optional[str]:
        """Get current storyboard path from active project (SQLite).

        Returns:
            Path to storyboard file or None if no active project/storyboard
        """
        project = self.get_active_project()
        if not project:
            return None
        return project.get("current_storyboard")

    def set_project_storyboard(
        self, project: Dict[str, str], file_path: str, set_as_default: bool = True
    ) -> None:
        """Set storyboard as current for the project (stored in SQLite).

        Args:
            project: Project dict
            file_path: Full path to storyboard file
            set_as_default: If True, sets as current_storyboard in SQLite
        """
        if set_as_default and file_path:
            slug = project.get("slug")
            if slug:
                self._set_storyboard_in_db(slug, file_path)
                logger.debug(f"Storyboard gesetzt: {file_path}")

    def list_project_storyboards(self, project: Dict[str, str]) -> List[str]:
        """List all storyboard files in project's storyboards directory."""
        if not project:
            return []
        storyboard_dir = self.get_project_storyboard_dir(project)
        if not os.path.isdir(storyboard_dir):
            return []
        return sorted([f for f in os.listdir(storyboard_dir) if f.endswith(".json")])

    def delete_storyboard(self, project: Dict[str, str], filename: str) -> bool:
        """Delete a storyboard file from the project.

        Args:
            project: Project dict
            filename: Storyboard filename (not full path)

        Returns:
            True if deleted, False if not found or error
        """
        if not project or not filename:
            return False

        storyboard_dir = self.get_project_storyboard_dir(project)
        file_path = os.path.join(storyboard_dir, filename)
        slug = project.get("slug")

        if not os.path.exists(file_path):
            return False

        try:
            os.remove(file_path)
            logger.info(f"Storyboard gelöscht: {filename}")

            # If this was the current storyboard, update SQLite
            current_sb = project.get("current_storyboard")
            if current_sb and os.path.normpath(current_sb) == os.path.normpath(file_path):
                # Try to find another storyboard in the project
                remaining = self.list_project_storyboards(project)
                if remaining:
                    new_sb = os.path.join(storyboard_dir, remaining[0])
                    self._set_storyboard_in_db(slug, new_sb)
                    logger.debug(f"Neues Storyboard gesetzt: {new_sb}")
                else:
                    self._set_storyboard_in_db(slug, None)

            return True
        except Exception as e:
            logger.warning(f"Konnte Storyboard nicht löschen: {e}")
            return False

    # -----------------------------
    # Migration helper
    # -----------------------------
    def import_from_filesystem(self) -> int:
        """Scan filesystem and import existing projects into database.

        Returns:
            Number of projects imported
        """
        try:
            root = self._comfy_output_root()
        except FileNotFoundError:
            return 0

        imported = 0
        for entry in sorted(os.listdir(root)):
            project_dir = os.path.join(root, entry)
            if not os.path.isdir(project_dir):
                continue

            # Skip if already in database
            if self.load_project(entry):
                continue

            # Check for project.json (old format)
            project_json = os.path.join(project_dir, "project.json")
            if os.path.exists(project_json):
                try:
                    import json
                    with open(project_json, "r") as f:
                        data = json.load(f)

                    conn = self._get_conn()
                    cursor = conn.cursor()

                    cursor.execute("""
                        INSERT OR IGNORE INTO projects (slug, name, path, created_at, last_opened, is_active, version)
                        VALUES (?, ?, ?, ?, ?, 0, ?)
                    """, (
                        entry,
                        data.get("name", entry),
                        project_dir,
                        data.get("created_at", datetime.utcnow().isoformat()),
                        data.get("last_opened"),
                        data.get("version", "0.x"),
                    ))

                    conn.commit()
                    conn.close()
                    imported += 1
                    logger.info(f"Projekt importiert: {entry}")
                except Exception as e:
                    logger.warning(f"Konnte {entry} nicht importieren: {e}")

        return imported

    # -----------------------------
    # Internal helpers
    # -----------------------------
    def _slugify(self, name: str) -> str:
        """Convert name to URL-safe slug."""
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip().lower())
        slug = re.sub(r"-{2,}", "-", slug).strip("-")
        return slug or "project"


__all__ = ["ProjectStore", "get_db_path"]
