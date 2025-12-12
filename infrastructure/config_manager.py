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
            "current_project": None,
            "current_storyboard": None,
            "global_resolution": "1080p_landscape",
            "log_level": "INFO",
            "theme": "default",
            "auto_save_results": True,
            "max_concurrent_jobs": 1
        }

    # Convenience methods
    def get_comfy_url(self) -> str:
        """Get ComfyUI server URL"""
        return self.get("comfy_url", "http://127.0.0.1:8188")

    def get_workflow_dir(self) -> str:
        """Get workflow templates directory"""
        return self.get("workflow_dir", "config/workflow_templates")

    def get_comfy_root(self) -> str:
        """Get ComfyUI installation root for model discovery"""
        root = self.get("comfy_root", os.path.expanduser("~/comfyui"))
        return os.path.expanduser(root)

    def get_output_dir(self) -> str:
        """Get output directory"""
        return self.get("output_dir", "output")

    def get_current_project(self) -> Optional[str]:
        """Return active project slug"""
        return self.get("current_project")

    def get_current_storyboard(self) -> Optional[str]:
        """Return storyboard path selected in project tab."""
        return self.get("current_storyboard")

    def get_resolution_preset(self) -> str:
        """Return selected resolution preset key."""
        return self.get("global_resolution", "1080p_landscape")

    def get_resolution_tuple(self) -> tuple[int, int]:
        """Map preset key to (width, height)."""
        presets = {
            "1080p_landscape": (1920, 1080),
            "1080p_portrait": (1080, 1920),
            "720p_landscape": (1280, 720),
            "720p_portrait": (720, 1280),
            "540p_landscape": (960, 540),
            "540p_portrait": (540, 960),
        }
        return presets.get(self.get_resolution_preset(), (1024, 576))

    def get_log_level(self) -> str:
        """Get logging level"""
        return self.get("log_level", "INFO")
