"""Global settings storage in SQLite for CINDERGRACE pipeline.

Supports encrypted storage for sensitive values like API keys.
"""
import base64
import hashlib
import json
import os
import platform
import sqlite3
from typing import Any, Dict, List, Optional

from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from infrastructure.logger import get_logger


def _get_db_path() -> str:
    """Return path to cindergrace.db.

    Duplicated from project_store to avoid circular import.
    """
    base_dir = Path(__file__).parent.parent
    db_dir = base_dir / "data"
    db_dir.mkdir(parents=True, exist_ok=True)
    return str(db_dir / "cindergrace.db")

logger = get_logger(__name__)


def _get_machine_id() -> str:
    """Get a machine-specific identifier for key derivation.

    Uses a combination of hostname and platform info.
    This is not meant to be highly secure, but provides
    basic protection against copying the database to another machine.
    """
    parts = [
        platform.node(),  # hostname
        platform.system(),
        platform.machine(),
    ]
    return "-".join(parts)


class SettingsStore:
    """Handle global application settings in SQLite database.

    Supports both plain and encrypted storage. Sensitive values
    (API keys, tokens) are automatically encrypted using Fernet.
    """

    # Keys that should be encrypted
    SENSITIVE_KEYS = {
        "civitai_api_key",
        "huggingface_token",
        "google_tts_api_key",
        "openrouter_api_key",
    }

    def __init__(self):
        self.db_path = _get_db_path()
        self._fernet: Optional[Fernet] = None
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Create settings table if not exists, with migration support."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                encrypted INTEGER DEFAULT 0
            )
        """)

        # Check if 'encrypted' column exists (migration for existing DBs)
        cursor.execute("PRAGMA table_info(settings)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'encrypted' not in columns:
            cursor.execute("ALTER TABLE settings ADD COLUMN encrypted INTEGER DEFAULT 0")
            logger.info("Migrated settings table: added 'encrypted' column")

        conn.commit()
        conn.close()
        logger.debug("Settings table initialized")

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection."""
        return sqlite3.connect(self.db_path)

    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create the encryption key.

        The key is derived from:
        - A random salt stored in the database
        - A machine-specific identifier

        This means the encrypted values can only be decrypted
        on the same machine where they were created.
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # Check for existing salt
        cursor.execute("SELECT value FROM settings WHERE key = '_encryption_salt'")
        row = cursor.fetchone()

        if row:
            salt = base64.b64decode(row[0])
        else:
            # Generate new salt
            salt = os.urandom(16)
            salt_b64 = base64.b64encode(salt).decode('utf-8')
            cursor.execute(
                "INSERT INTO settings (key, value, encrypted) VALUES (?, ?, 0)",
                ("_encryption_salt", salt_b64)
            )
            conn.commit()
            logger.info("Created new encryption salt")

        conn.close()

        # Derive key from salt + machine ID
        machine_id = _get_machine_id().encode('utf-8')
        key_material = hashlib.pbkdf2_hmac(
            'sha256',
            machine_id,
            salt,
            100000,  # iterations
            dklen=32
        )

        # Fernet requires base64-encoded 32-byte key
        return base64.urlsafe_b64encode(key_material)

    def _get_fernet(self) -> Fernet:
        """Get Fernet instance for encryption/decryption."""
        if self._fernet is None:
            key = self._get_or_create_encryption_key()
            self._fernet = Fernet(key)
        return self._fernet

    def _encrypt(self, value: str) -> str:
        """Encrypt a string value."""
        fernet = self._get_fernet()
        encrypted = fernet.encrypt(value.encode('utf-8'))
        return base64.b64encode(encrypted).decode('utf-8')

    def _decrypt(self, encrypted_value: str) -> Optional[str]:
        """Decrypt a string value. Returns None if decryption fails."""
        try:
            fernet = self._get_fernet()
            encrypted = base64.b64decode(encrypted_value)
            decrypted = fernet.decrypt(encrypted)
            return decrypted.decode('utf-8')
        except (InvalidToken, Exception) as e:
            logger.warning(f"Failed to decrypt value: {e}")
            return None

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a setting value by key.

        Args:
            key: Setting key
            default: Default value if key not found

        Returns:
            Setting value or default
        """
        # Skip internal keys
        if key.startswith('_'):
            return default

        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT value, encrypted FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return default

        value, is_encrypted = row

        if is_encrypted:
            decrypted = self._decrypt(value)
            return decrypted if decrypted is not None else default

        return value

    def set(self, key: str, value: str) -> None:
        """Set a setting value.

        Sensitive keys are automatically encrypted.

        Args:
            key: Setting key
            value: Setting value
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # Check if this is a sensitive key
        is_sensitive = key in self.SENSITIVE_KEYS

        if is_sensitive and value:
            stored_value = self._encrypt(value)
            encrypted = 1
        else:
            stored_value = value
            encrypted = 0

        cursor.execute("""
            INSERT INTO settings (key, value, encrypted) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, encrypted = excluded.encrypted
        """, (key, stored_value, encrypted))

        conn.commit()
        conn.close()

        if is_sensitive:
            logger.debug(f"Setting saved (encrypted): {key}")
        else:
            logger.debug(f"Setting saved: {key} = {value}")

    def delete(self, key: str) -> bool:
        """Delete a setting.

        Args:
            key: Setting key

        Returns:
            True if deleted, False if not found
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM settings WHERE key = ?", (key,))
        deleted = cursor.rowcount > 0

        conn.commit()
        conn.close()
        return deleted

    def get_all(self) -> Dict[str, str]:
        """Get all settings as dictionary.

        Note: Encrypted values are returned decrypted.
        Internal keys (starting with _) are excluded.

        Returns:
            Dictionary of all settings
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT key, value, encrypted FROM settings WHERE key NOT LIKE '\\_%' ESCAPE '\\'")
        rows = cursor.fetchall()
        conn.close()

        result = {}
        for key, value, is_encrypted in rows:
            if is_encrypted:
                decrypted = self._decrypt(value)
                if decrypted is not None:
                    result[key] = decrypted
            else:
                result[key] = value

        return result

    def get_json(self, key: str, default: Any = None) -> Any:
        """Get a JSON-encoded setting value.

        Args:
            key: Setting key
            default: Default value if key not found or invalid JSON

        Returns:
            Parsed JSON value or default
        """
        value = self.get(key)
        if value is None:
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default

    def set_json(self, key: str, value: Any) -> None:
        """Set a JSON-encoded setting value.

        Args:
            key: Setting key
            value: Value to JSON-encode and store
        """
        self.set(key, json.dumps(value))

    # === Convenience methods for common settings ===

    def get_comfy_url(self) -> str:
        """Get ComfyUI server URL."""
        return self.get("comfy_url", "http://127.0.0.1:8188")

    def set_comfy_url(self, url: str) -> None:
        """Set ComfyUI server URL."""
        self.set("comfy_url", url)

    def get_comfy_root(self) -> str:
        """Get ComfyUI installation root path.

        Returns empty string if not configured - user must set this explicitly.
        """
        value = self.get("comfy_root", "")
        return os.path.expanduser(value) if value else ""

    def set_comfy_root(self, path: str) -> None:
        """Set ComfyUI installation root path."""
        self.set("comfy_root", path)

    def get_backends(self) -> Dict[str, Dict[str, Any]]:
        """Get all configured backends."""
        backends = self.get_json("backends")
        if backends:
            return backends
        # Default local backend
        return {
            "local": {
                "name": "Local",
                "url": self.get_comfy_url(),
                "comfy_root": self.get_comfy_root(),
                "type": "local",
            }
        }

    def set_backends(self, backends: Dict[str, Dict[str, Any]]) -> None:
        """Set all backends."""
        self.set_json("backends", backends)

    def get_active_backend_id(self) -> str:
        """Get the ID of the currently active backend."""
        return self.get("active_backend", "local")

    def set_active_backend_id(self, backend_id: str) -> None:
        """Set the active backend ID."""
        self.set("active_backend", backend_id)

    def get_resolution_preset(self) -> str:
        """Get global resolution preset."""
        return self.get("global_resolution", "720p_landscape")

    def set_resolution_preset(self, preset: str) -> None:
        """Set global resolution preset."""
        self.set("global_resolution", preset)

    def use_sage_attention(self) -> bool:
        """Check if SageAttention is enabled."""
        return self.get("use_sage_attention", "false").lower() == "true"

    def set_sage_attention(self, enabled: bool) -> None:
        """Enable/disable SageAttention."""
        self.set("use_sage_attention", "true" if enabled else "false")

    # === API Keys (encrypted) ===

    def get_civitai_api_key(self) -> str:
        """Get Civitai API key (decrypted)."""
        return self.get("civitai_api_key", "")

    def set_civitai_api_key(self, key: str) -> None:
        """Set Civitai API key (will be encrypted)."""
        self.set("civitai_api_key", key)

    def get_huggingface_token(self) -> str:
        """Get Huggingface token (decrypted)."""
        return self.get("huggingface_token", "")

    def set_huggingface_token(self, token: str) -> None:
        """Set Huggingface token (will be encrypted)."""
        self.set("huggingface_token", token)

    def get_google_tts_api_key(self) -> str:
        """Get Google TTS API key (decrypted)."""
        return self.get("google_tts_api_key", "")

    def set_google_tts_api_key(self, key: str) -> None:
        """Set Google TTS API key (will be encrypted)."""
        self.set("google_tts_api_key", key)

    def get_openrouter_api_key(self) -> str:
        """Get OpenRouter API key (decrypted)."""
        return self.get("openrouter_api_key", "")

    def set_openrouter_api_key(self, key: str) -> None:
        """Set OpenRouter API key (will be encrypted)."""
        self.set("openrouter_api_key", key)

    def get_openrouter_models(self) -> List[str]:
        """Get configured OpenRouter models (up to 3)."""
        default_models = [
            "anthropic/claude-sonnet-4",
            "openai/gpt-4o",
            "meta-llama/llama-3.1-70b-instruct",
        ]
        return self.get_json("openrouter_models", default_models)

    def set_openrouter_models(self, models: List[str]) -> None:
        """Set OpenRouter models (up to 3)."""
        # Limit to 3 models
        models = models[:3] if len(models) > 3 else models
        self.set_json("openrouter_models", models)

    # === Workflow defaults ===

    def get_default_workflow(self, prefix: str) -> Optional[str]:
        """Get default workflow for a prefix (gcp_, gcv_, gcl_).

        Args:
            prefix: Workflow prefix (e.g., 'gcp_', 'gcv_', 'gcl_')

        Returns:
            Default workflow filename or None
        """
        key = f"default_workflow_{prefix.rstrip('_')}"
        return self.get(key)

    def set_default_workflow(self, prefix: str, workflow_file: str) -> None:
        """Set default workflow for a prefix.

        Args:
            prefix: Workflow prefix (e.g., 'gcp_', 'gcv_', 'gcl_')
            workflow_file: Workflow filename
        """
        key = f"default_workflow_{prefix.rstrip('_')}"
        self.set(key, workflow_file)
        logger.info(f"Default workflow set: {prefix} -> {workflow_file}")

    # === Cached workflow lists ===

    def get_workflow_list(self, prefix: str) -> List[str]:
        """Get cached workflow list for a prefix.

        Args:
            prefix: Workflow prefix (e.g., 'gcp_', 'gcv_', 'gcl_')

        Returns:
            List of workflow filenames (empty if not cached)
        """
        key = f"workflows_{prefix.rstrip('_')}"
        return self.get_json(key, [])

    def set_workflow_list(self, prefix: str, workflows: List[str]) -> None:
        """Cache workflow list for a prefix.

        Args:
            prefix: Workflow prefix (e.g., 'gcp_', 'gcv_', 'gcl_')
            workflows: List of workflow filenames
        """
        key = f"workflows_{prefix.rstrip('_')}"
        self.set_json(key, workflows)
        logger.info(f"Workflow list cached: {prefix} -> {len(workflows)} workflows")

    def clear_workflow_list(self, prefix: str) -> None:
        """Clear cached workflow list for a prefix.

        Args:
            prefix: Workflow prefix
        """
        key = f"workflows_{prefix.rstrip('_')}"
        self.delete(key)

    def has_workflow_cache(self, prefix: str) -> bool:
        """Check if workflow list is cached for a prefix.

        Args:
            prefix: Workflow prefix (e.g., 'gcp_', 'gcv_', 'gcl_')

        Returns:
            True if cache exists (even if empty list)
        """
        key = f"workflows_{prefix.rstrip('_')}"
        # Use get() - returns None if key doesn't exist
        return self.get(key) is not None


# Singleton instance
_settings_store: Optional[SettingsStore] = None


def get_settings_store() -> SettingsStore:
    """Get the global SettingsStore instance."""
    global _settings_store
    if _settings_store is None:
        _settings_store = SettingsStore()
    return _settings_store


__all__ = ["SettingsStore", "get_settings_store"]
