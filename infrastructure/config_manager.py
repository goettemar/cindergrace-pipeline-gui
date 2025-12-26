"""Configuration management via SQLite SettingsStore.

This module provides backwards-compatible access to settings
while storing all data securely in SQLite with encryption for
sensitive values like API keys.
"""
import os
from typing import Any, Dict, Optional

from infrastructure.settings_store import get_settings_store


class ConfigManager:
    """Manage GUI settings and pipeline configuration.

    Uses SQLite-based SettingsStore for persistent storage.
    Sensitive values (API keys) are automatically encrypted.
    """

    def __init__(self, config_path: str = None):
        """Initialize config manager.

        Args:
            config_path: Deprecated, kept for backwards compatibility.
                        All settings are stored in SQLite.
        """
        self._store = get_settings_store()
        # For backwards compatibility with code that checks config_dir
        self.config_dir = "config"
        # Deprecated: config_path no longer used
        self.config_path = config_path or "config/settings.json"

        # Migrate from JSON if needed (one-time)
        self._migrate_from_json()

    def _migrate_from_json(self) -> None:
        """Migrate settings from old JSON config if it exists."""
        json_path = "config/settings.json"
        if not os.path.exists(json_path):
            return

        try:
            import json
            with open(json_path, 'r') as f:
                old_config = json.load(f)

            # Check if already migrated
            if self._store.get("_migrated_from_json"):
                return

            # Migrate each setting
            for key, value in old_config.items():
                if key.startswith('_'):
                    continue

                # Handle special types
                if isinstance(value, (dict, list)):
                    self._store.set_json(key, value)
                elif isinstance(value, bool):
                    self._store.set(key, "true" if value else "false")
                elif value is not None:
                    self._store.set(key, str(value))

            # Mark as migrated
            self._store.set("_migrated_from_json", "true")
            print(f"✓ Migrated settings from {json_path} to SQLite")

            # Rename old config to backup
            backup_path = json_path + ".backup"
            os.rename(json_path, backup_path)
            print(f"✓ Old config backed up to {backup_path}")

        except Exception as e:
            print(f"Warning: Failed to migrate from JSON: {e}")

    @property
    def config(self) -> Dict[str, Any]:
        """Get all settings as dictionary for backwards compatibility."""
        return self._store.get_all()

    def load(self) -> Dict[str, Any]:
        """Load config (returns current settings)."""
        return self._store.get_all()

    def refresh(self) -> Dict[str, Any]:
        """Reload configuration (no-op for SQLite, always fresh)."""
        return self._store.get_all()

    def save(self, config: Dict[str, Any] = None):
        """Save config (applies all values from dict).

        Args:
            config: Configuration dict to save (optional)
        """
        if config is not None:
            for key, value in config.items():
                if key.startswith('_'):
                    continue
                if isinstance(value, (dict, list)):
                    self._store.set_json(key, value)
                elif isinstance(value, bool):
                    self._store.set(key, "true" if value else "false")
                elif value is not None:
                    self._store.set(key, str(value))

    def get(self, key: str, default=None) -> Any:
        """Get config value with default fallback.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        value = self._store.get(key)
        if value is None:
            return default
        return value

    def set(self, key: str, value: Any):
        """Set config value and auto-save.

        Args:
            key: Configuration key
            value: Value to set
        """
        if isinstance(value, (dict, list)):
            self._store.set_json(key, value)
        elif isinstance(value, bool):
            self._store.set(key, "true" if value else "false")
        elif value is not None:
            self._store.set(key, str(value))

    def _get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean setting."""
        value = self._store.get(key)
        if value is None:
            return default
        return value.lower() == "true"

    def _get_int(self, key: str, default: int = 0) -> int:
        """Get integer setting."""
        value = self._store.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            return default

    # === Convenience methods ===

    def get_comfy_url(self, refresh: bool = True) -> str:
        """Get ComfyUI server URL from active backend."""
        backend = self.get_active_backend()
        return backend.get("url", "http://127.0.0.1:8188")

    def get_workflow_dir(self) -> str:
        """Get workflow templates directory."""
        return self._store.get("workflow_dir") or "config/workflow_templates"

    def get_comfy_root(self, refresh: bool = True) -> str:
        """Get ComfyUI installation root from active backend."""
        backend = self.get_active_backend()
        root = backend.get("comfy_root") or self._store.get_comfy_root()
        return os.path.expanduser(root)

    def get_output_dir(self) -> str:
        """Get output directory."""
        return self._store.get("output_dir") or "output"

    def use_sage_attention(self) -> bool:
        """Check if SageAttention is enabled for faster inference."""
        return self._store.use_sage_attention()

    def get_current_storyboard(self) -> Optional[str]:
        """Return storyboard path from active project (SQLite)."""
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
        return self._store.get_resolution_preset()

    def get_resolution_tuple(self) -> tuple[int, int]:
        """Map preset key to (width, height)."""
        presets = {
            "720p_landscape": (1280, 720),
            "720p_portrait": (720, 1280),
            "480p_landscape": (832, 480),
            "480p_portrait": (480, 832),
            "1080p_landscape": (1920, 1080),
            "1080p_portrait": (1080, 1920),
            "540p_landscape": (960, 540),
            "540p_portrait": (540, 960),
            "512_square": (512, 512),
            "1024_square": (1024, 1024),
            # LTX-Video presets (flexible resolutions)
            "ltx_768x512": (768, 512),
            "ltx_512x768": (512, 768),
        }
        return presets.get(self.get_resolution_preset(), (1024, 576))

    def get_log_level(self) -> str:
        """Get logging level."""
        return self._store.get("log_level") or "INFO"

    def get_video_initial_wait(self) -> int:
        """Get initial wait time in seconds before checking for video files."""
        return self._get_int("video_initial_wait", 60)

    def get_video_retry_delay(self) -> int:
        """Get delay between retry checks in seconds."""
        return self._get_int("video_retry_delay", 30)

    def get_video_max_retries(self) -> int:
        """Get maximum number of retries for video file detection."""
        return self._get_int("video_max_retries", 20)

    # === Setup Wizard methods ===

    def is_first_run(self) -> bool:
        """Check if this is the first run (setup not completed)."""
        if self._get_bool("setup_completed", False):
            return False

        comfy_root = self._store.get("comfy_root") or ""
        if not comfy_root:
            return True

        expanded_path = os.path.expanduser(comfy_root)
        if os.path.isdir(expanded_path):
            return False

        return True

    def mark_setup_completed(self) -> None:
        """Mark the setup wizard as completed."""
        self._store.set("setup_completed", "true")

    # === Backend management methods ===

    def get_backends(self) -> Dict[str, Dict[str, Any]]:
        """Get all configured backends."""
        return self._store.get_backends()

    def get_active_backend_id(self) -> str:
        """Get the ID of the currently active backend."""
        return self._store.get_active_backend_id()

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

        self._store.set_active_backend_id(backend_id)
        return True

    def add_backend(self, backend_id: str, name: str, url: str,
                    backend_type: str = "remote", comfy_root: str = "") -> None:
        """Add a new backend configuration."""
        backends = self.get_backends()
        backends[backend_id] = {
            "name": name,
            "url": url,
            "type": backend_type,
            "comfy_root": comfy_root if backend_type == "local" else ""
        }
        self._store.set_backends(backends)

    def remove_backend(self, backend_id: str) -> bool:
        """Remove a backend configuration."""
        if backend_id == "local":
            return False

        backends = self.get_backends()
        if backend_id not in backends or len(backends) <= 1:
            return False

        if self.get_active_backend_id() == backend_id:
            self.set_active_backend("local")

        del backends[backend_id]
        self._store.set_backends(backends)
        return True

    def update_backend(self, backend_id: str, name: str = None, url: str = None,
                       comfy_root: str = None) -> bool:
        """Update an existing backend configuration."""
        backends = self.get_backends()
        if backend_id not in backends:
            return False

        if name is not None:
            backends[backend_id]["name"] = name
        if url is not None:
            backends[backend_id]["url"] = url
        if comfy_root is not None and backends[backend_id].get("type") == "local":
            backends[backend_id]["comfy_root"] = comfy_root

        self._store.set_backends(backends)
        return True

    def is_remote_backend(self) -> bool:
        """Check if the current backend is remote (Colab/Cloud)."""
        backend = self.get_active_backend()
        return backend.get("type", "local") == "remote"

    # === API Keys (encrypted via SettingsStore) ===

    def get_civitai_api_key(self) -> str:
        """Get Civitai API key for model downloads (decrypted)."""
        return self._store.get_civitai_api_key()

    def set_civitai_api_key(self, key: str) -> None:
        """Set Civitai API key (will be encrypted)."""
        self._store.set_civitai_api_key(key)

    def get_huggingface_token(self) -> str:
        """Get Huggingface token for model downloads (decrypted)."""
        return self._store.get_huggingface_token()

    def set_huggingface_token(self, token: str) -> None:
        """Set Huggingface token (will be encrypted)."""
        self._store.set_huggingface_token(token)

    def get_google_tts_api_key(self) -> str:
        """Get Google TTS API key (decrypted)."""
        return self._store.get_google_tts_api_key()

    def set_google_tts_api_key(self, key: str) -> None:
        """Set Google TTS API key (will be encrypted)."""
        self._store.set_google_tts_api_key(key)

    # === OpenRouter API ===

    def get_openrouter_api_key(self) -> str:
        """Get OpenRouter API key for LLM access (decrypted)."""
        return self._store.get_openrouter_api_key()

    def set_openrouter_api_key(self, key: str) -> None:
        """Set OpenRouter API key (will be encrypted)."""
        self._store.set_openrouter_api_key(key)

    def get_openrouter_models(self) -> list:
        """Get configured OpenRouter models (up to 3)."""
        return self._store.get_openrouter_models()

    def set_openrouter_models(self, models: list) -> None:
        """Set OpenRouter models (up to 3)."""
        self._store.set_openrouter_models(models)

    def get_max_parallel_downloads(self) -> int:
        """Get maximum parallel downloads (1-5)."""
        value = self._get_int("max_parallel_downloads", 2)
        return max(1, min(5, value))

    def set_max_parallel_downloads(self, count: int) -> None:
        """Set maximum parallel downloads."""
        self._store.set("max_parallel_downloads", str(max(1, min(5, count))))
