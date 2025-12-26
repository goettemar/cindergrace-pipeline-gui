"""Configuration file management"""
import json
import os
import platform
from typing import Any, Dict, Optional

# Platform-specific file locking
_HAS_FCNTL = False
if platform.system() != "Windows":
    try:
        import fcntl
        _HAS_FCNTL = True
    except ImportError:
        pass


class ConfigManager:
    """Manage GUI settings and pipeline configuration"""

    def __init__(self, config_path: str = "config/settings.json"):
        """
        Initialize config manager

        Args:
            config_path: Path to settings JSON file
        """
        self.config_path = config_path
        self.config_dir = os.path.dirname(config_path) if config_path != "config/settings.json" else "config"
        self.config = self.load()

    def load(self) -> Dict[str, Any]:
        """
        Load config from JSON file

        Returns:
            Configuration dictionary
        """
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load config from {self.config_path}: {e}")
                return self._default_config()
        else:
            print(f"Config file not found, using defaults: {self.config_path}")
            return self._default_config()

    def refresh(self) -> Dict[str, Any]:
        """Reload configuration from disk"""
        self.config = self.load()
        return self.config

    def save(self, config: Dict[str, Any] = None):
        """Save config to JSON file with file-locking to prevent race conditions.

        On Linux/Mac, uses fcntl for exclusive locks.
        On Windows, relies on atomic file operations (no locking available).

        Args:
            config: Configuration dict to save (uses self.config if None)
        """
        if config is not None:
            self.config = config

        # Ensure directory exists
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                # Acquire exclusive lock (Linux/Mac only)
                if _HAS_FCNTL:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)

                try:
                    json.dump(self.config, f, indent=2, ensure_ascii=False)
                finally:
                    # Release lock (Linux/Mac only)
                    if _HAS_FCNTL:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            print(f"✓ Config saved to {self.config_path}")
        except Exception as e:
            print(f"✗ Failed to save config: {e}")

    def get(self, key: str, default=None) -> Any:
        """
        Get config value with default fallback

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        """
        Set config value and auto-save

        Args:
            key: Configuration key
            value: Value to set
        """
        self.config[key] = value
        self.save()

    def _default_config(self) -> Dict[str, Any]:
        """
        Get default configuration

        Returns:
            Default config dictionary
        """
        return {
            "comfy_url": "http://127.0.0.1:8188",
            "comfy_root": os.path.expanduser("~/comfyui"),
            "workflow_dir": "config/workflow_templates",
            "output_dir": "output",
            "current_storyboard": None,
            "global_resolution": "1080p_landscape",
            "log_level": "INFO",
            "theme": "default",
            "auto_save_results": True,
            "max_concurrent_jobs": 1,
            # Multi-backend support for local/cloud ComfyUI
            "active_backend": "local",
            "backends": {
                "local": {
                    "name": "Lokal",
                    "url": "http://127.0.0.1:8188",
                    "comfy_root": os.path.expanduser("~/comfyui"),
                    "type": "local"
                }
            }
        }

    # Convenience methods
    def get_comfy_url(self, refresh: bool = True) -> str:
        """Get ComfyUI server URL from active backend.

        Args:
            refresh: If True, reload config from disk first (default: True)
        """
        if refresh:
            self.refresh()
        backend = self.get_active_backend()
        return backend.get("url", "http://127.0.0.1:8188")

    def get_workflow_dir(self) -> str:
        """Get workflow templates directory"""
        return self.get("workflow_dir", "config/workflow_templates")

    def get_comfy_root(self, refresh: bool = True) -> str:
        """Get ComfyUI installation root from active backend (for model discovery).

        Args:
            refresh: If True, reload config from disk first (default: True)
        """
        if refresh:
            self.refresh()
        backend = self.get_active_backend()
        root = backend.get("comfy_root") or self.get("comfy_root", os.path.expanduser("~/comfyui"))
        return os.path.expanduser(root)

    def get_output_dir(self) -> str:
        """Get output directory"""
        return self.get("output_dir", "output")

    def get_current_storyboard(self) -> Optional[str]:
        """Return storyboard path from active project (SQLite).

        Falls back to JSON config for backwards compatibility.
        Automatically migrates JSON data to SQLite when found.
        """
        json_storyboard = self.get("current_storyboard")
        if json_storyboard:
            # Best-effort migration to SQLite
            try:
                from infrastructure.project_store import ProjectStore
                project_store = ProjectStore(self)
                project = project_store.get_active_project()
                if project and project.get("slug"):
                    project_store.set_project_storyboard(project, json_storyboard, set_as_default=True)
            except Exception:
                pass
            return json_storyboard

        # Lazy import to avoid circular dependency
        try:
            from infrastructure.project_store import ProjectStore
            project_store = ProjectStore(self)
            storyboard = project_store.get_current_storyboard()
            if storyboard:
                return storyboard
        except Exception:
            pass

        return None

    def get_resolution_preset(self) -> str:
        """Return selected resolution preset key."""
        return self.get("global_resolution", "1080p_landscape")

    def get_resolution_tuple(self) -> tuple[int, int]:
        """Map preset key to (width, height).

        Wan 2.2 unterstützt nur 480p, 720p und 1080p.
        """
        presets = {
            "720p_landscape": (1280, 720),
            "720p_portrait": (720, 1280),
            "480p_landscape": (854, 480),
            "480p_portrait": (480, 854),
            "1080p_landscape": (1920, 1080),
            "1080p_portrait": (1080, 1920),
            # Legacy (nicht empfohlen für Wan 2.2)
            "540p_landscape": (960, 540),
            "540p_portrait": (540, 960),
        }
        return presets.get(self.get_resolution_preset(), (1024, 576))

    def get_log_level(self) -> str:
        """Get logging level"""
        return self.get("log_level", "INFO")

    def get_video_initial_wait(self) -> int:
        """Get initial wait time in seconds before checking for video files (default: 60)"""
        return int(self.get("video_initial_wait", 60))

    def get_video_retry_delay(self) -> int:
        """Get delay between retry checks in seconds (default: 30)"""
        return int(self.get("video_retry_delay", 30))

    def get_video_max_retries(self) -> int:
        """Get maximum number of retries for video file detection (default: 20)"""
        return int(self.get("video_max_retries", 20))

    # Setup Wizard methods
    def is_first_run(self) -> bool:
        """Check if this is the first run (setup not completed).

        Returns:
            True if setup wizard should be shown, False otherwise
        """
        # Schneller Check: Wenn setup_completed True ist, kein First-Run
        if self.get("setup_completed", False):
            return False

        # Check ob comfy_root gesetzt und als Verzeichnis existiert
        comfy_root = self.get("comfy_root", "")
        if not comfy_root:
            return True

        # Pfad expandieren und prüfen
        expanded_path = os.path.expanduser(comfy_root)
        if os.path.isdir(expanded_path):
            # ComfyUI-Pfad existiert - kein First-Run Banner nötig
            return False

        return True

    def mark_setup_completed(self) -> None:
        """Mark the setup wizard as completed."""
        self.set("setup_completed", True)

    # Backend management methods
    def get_backends(self) -> Dict[str, Dict[str, Any]]:
        """Get all configured backends."""
        backends = self.get("backends")
        if backends:
            return backends
        return {
            "local": {
                "name": "Lokal",
                "url": self.get("comfy_url", "http://127.0.0.1:8188"),
                "comfy_root": self.get("comfy_root", os.path.expanduser("~/comfyui")),
                "type": "local",
            }
        }

    def get_active_backend_id(self) -> str:
        """Get the ID of the currently active backend."""
        return self.get("active_backend", "local")

    def get_active_backend(self) -> Dict[str, Any]:
        """Get the currently active backend configuration."""
        backends = self.get_backends()
        active_id = self.get_active_backend_id()
        return backends.get(active_id, backends.get("local", {}))

    def set_active_backend(self, backend_id: str) -> bool:
        """Switch to a different backend.

        Args:
            backend_id: The backend ID to switch to

        Returns:
            True if successful, False if backend not found
        """
        backends = self.get_backends()
        if backend_id not in backends:
            return False

        backend = backends[backend_id]
        self.config["active_backend"] = backend_id
        # Update legacy fields for compatibility
        self.config["comfy_url"] = backend.get("url", "http://127.0.0.1:8188")
        if backend.get("type") == "local":
            self.config["comfy_root"] = backend.get("comfy_root", os.path.expanduser("~/comfyui"))
        self.save()
        return True

    def add_backend(self, backend_id: str, name: str, url: str,
                    backend_type: str = "remote", comfy_root: str = "") -> None:
        """Add a new backend configuration.

        Args:
            backend_id: Unique identifier for the backend
            name: Display name
            url: ComfyUI URL (local or cloudflare tunnel)
            backend_type: "local" or "remote"
            comfy_root: ComfyUI path (only for local backends)
        """
        backends = self.get_backends()
        backends[backend_id] = {
            "name": name,
            "url": url,
            "type": backend_type,
            "comfy_root": comfy_root if backend_type == "local" else ""
        }
        self.config["backends"] = backends
        self.save()

    def remove_backend(self, backend_id: str) -> bool:
        """Remove a backend configuration.

        Args:
            backend_id: The backend to remove

        Returns:
            True if removed, False if not found or is the only backend
        """
        if backend_id == "local":
            return False  # Cannot remove default local backend

        backends = self.get_backends()
        if backend_id not in backends or len(backends) <= 1:
            return False

        # If removing active backend, switch to local
        if self.get_active_backend_id() == backend_id:
            self.set_active_backend("local")

        del backends[backend_id]
        self.config["backends"] = backends
        self.save()
        return True

    def update_backend(self, backend_id: str, name: str = None, url: str = None,
                       comfy_root: str = None) -> bool:
        """Update an existing backend configuration.

        Args:
            backend_id: The backend to update
            name: New display name (optional)
            url: New URL (optional)
            comfy_root: New comfy_root path (optional, local only)

        Returns:
            True if updated, False if not found
        """
        backends = self.get_backends()
        if backend_id not in backends:
            return False

        if name is not None:
            backends[backend_id]["name"] = name
        if url is not None:
            backends[backend_id]["url"] = url
        if comfy_root is not None and backends[backend_id].get("type") == "local":
            backends[backend_id]["comfy_root"] = comfy_root

        self.config["backends"] = backends

        # Update legacy fields if this is the active backend
        if self.get_active_backend_id() == backend_id:
            if url is not None:
                self.config["comfy_url"] = url
            if comfy_root is not None and backends[backend_id].get("type") == "local":
                self.config["comfy_root"] = comfy_root

        self.save()
        return True

    def is_remote_backend(self) -> bool:
        """Check if the current backend is remote (Colab/Cloud)."""
        backend = self.get_active_backend()
        return backend.get("type", "local") == "remote"
