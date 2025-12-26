"""Unit tests for ConfigManager (SQLite-based via SettingsStore)"""
import pytest
import os
from pathlib import Path

from infrastructure.config_manager import ConfigManager


class TestConfigManagerInit:
    """Test ConfigManager initialization"""

    @pytest.mark.unit
    def test_init_with_default_path(self, tmp_path, monkeypatch):
        """Should initialize with backwards-compatible config_path attribute"""
        manager = ConfigManager()
        assert manager.config_path is not None
        assert manager.config_dir == "config"

    @pytest.mark.unit
    def test_init_with_custom_path(self, tmp_path):
        """Should accept custom path for backwards compatibility"""
        custom_path = str(tmp_path / "custom" / "config.json")
        manager = ConfigManager(custom_path)
        assert manager.config_path == custom_path

    @pytest.mark.unit
    def test_init_uses_settings_store(self):
        """Should use SettingsStore internally"""
        manager = ConfigManager()
        assert hasattr(manager, '_store')
        assert manager._store is not None


class TestConfigManagerLoad:
    """Test ConfigManager.load()"""

    @pytest.mark.unit
    def test_load_returns_dict(self):
        """Should return settings as dictionary"""
        manager = ConfigManager()
        config = manager.load()
        assert isinstance(config, dict)

    @pytest.mark.unit
    def test_refresh_returns_current_settings(self):
        """Should return current settings on refresh"""
        manager = ConfigManager()
        manager.set("test_key", "test_value")

        config = manager.refresh()

        assert config.get("test_key") == "test_value"


class TestConfigManagerGetSet:
    """Test ConfigManager.get() and set()"""

    @pytest.mark.unit
    def test_get_existing_key(self):
        """Should get existing config value"""
        manager = ConfigManager()
        manager.set("test_key", "test_value")

        value = manager.get("test_key")

        assert value == "test_value"

    @pytest.mark.unit
    def test_get_missing_key_with_default(self):
        """Should return default for missing key"""
        manager = ConfigManager()

        value = manager.get("nonexistent_key", "default_value")

        assert value == "default_value"

    @pytest.mark.unit
    def test_set_persists_value(self):
        """Should persist value to SettingsStore"""
        manager = ConfigManager()

        manager.set("new_key", "new_value")

        # Create new manager to verify persistence
        manager2 = ConfigManager()
        assert manager2.get("new_key") == "new_value"

    @pytest.mark.unit
    def test_set_handles_dict_values(self):
        """Should serialize dict values as JSON"""
        manager = ConfigManager()

        manager.set("dict_key", {"nested": "value"})

        # Value should be retrievable
        result = manager._store.get_json("dict_key")
        assert result == {"nested": "value"}

    @pytest.mark.unit
    def test_set_handles_bool_values(self):
        """Should store bool values as strings"""
        manager = ConfigManager()

        manager.set("bool_true", True)
        manager.set("bool_false", False)

        assert manager._store.get("bool_true") == "true"
        assert manager._store.get("bool_false") == "false"


class TestConfigManagerConvenienceMethods:
    """Test convenience getter methods"""

    @pytest.mark.unit
    def test_get_comfy_url_default(self):
        """Should return default URL if not set"""
        manager = ConfigManager()

        url = manager.get_comfy_url()

        assert url == "http://127.0.0.1:8188"

    @pytest.mark.unit
    def test_get_comfy_url_from_backend(self):
        """Should get URL from active backend"""
        manager = ConfigManager()
        manager.add_backend("test", "Test", "http://custom:9000", "remote")
        manager.set_active_backend("test")

        url = manager.get_comfy_url()

        assert url == "http://custom:9000"

    @pytest.mark.unit
    def test_get_comfy_root_expands_tilde(self):
        """Should expand ~ in comfy_root path"""
        manager = ConfigManager()
        manager._store.set_comfy_root("~/ComfyUI")

        root = manager.get_comfy_root()

        assert "~" not in root
        assert "ComfyUI" in root

    @pytest.mark.unit
    def test_get_workflow_dir_default(self):
        """Should return default workflow directory"""
        manager = ConfigManager()

        wf_dir = manager.get_workflow_dir()

        assert wf_dir == "config/workflow_templates"

    @pytest.mark.unit
    def test_get_output_dir_default(self):
        """Should return default output directory"""
        manager = ConfigManager()

        output = manager.get_output_dir()

        assert output == "output"

    @pytest.mark.unit
    def test_get_output_dir_custom(self):
        """Should return custom output directory"""
        manager = ConfigManager()
        manager._store.set("output_dir", "custom_output")

        output = manager.get_output_dir()

        assert output == "custom_output"

    @pytest.mark.unit
    def test_get_log_level_default(self):
        """Should return default log level"""
        manager = ConfigManager()

        level = manager.get_log_level()

        assert level == "INFO"

    @pytest.mark.unit
    def test_get_log_level_custom(self):
        """Should return custom log level"""
        manager = ConfigManager()
        manager._store.set("log_level", "DEBUG")

        level = manager.get_log_level()

        assert level == "DEBUG"


class TestConfigManagerResolutionPresets:
    """Test resolution preset methods"""

    @pytest.mark.unit
    def test_get_resolution_preset_default(self):
        """Should return default preset"""
        manager = ConfigManager()

        preset = manager.get_resolution_preset()

        assert preset == "720p_landscape"

    @pytest.mark.unit
    def test_get_resolution_tuple_720p_landscape(self):
        """Should return 720p landscape dimensions by default"""
        manager = ConfigManager()

        width, height = manager.get_resolution_tuple()

        assert width == 1280
        assert height == 720

    @pytest.mark.unit
    def test_get_resolution_tuple_1080p_landscape(self):
        """Should return 1080p landscape dimensions"""
        manager = ConfigManager()
        manager._store.set_resolution_preset("1080p_landscape")

        width, height = manager.get_resolution_tuple()

        assert width == 1920
        assert height == 1080

    @pytest.mark.unit
    def test_get_resolution_tuple_720p_portrait(self):
        """Should return 720p portrait dimensions"""
        manager = ConfigManager()
        manager._store.set_resolution_preset("720p_portrait")

        width, height = manager.get_resolution_tuple()

        assert width == 720
        assert height == 1280

    @pytest.mark.unit
    def test_get_resolution_tuple_invalid_returns_default(self):
        """Should return default dimensions for invalid preset"""
        manager = ConfigManager()
        manager._store.set("global_resolution", "invalid_preset")

        width, height = manager.get_resolution_tuple()

        assert width == 1024
        assert height == 576

    @pytest.mark.unit
    @pytest.mark.parametrize("preset,expected", [
        ("1080p_landscape", (1920, 1080)),
        ("1080p_portrait", (1080, 1920)),
        ("720p_landscape", (1280, 720)),
        ("720p_portrait", (720, 1280)),
        ("540p_landscape", (960, 540)),
        ("540p_portrait", (540, 960)),
        ("480p_landscape", (832, 480)),
        ("480p_portrait", (480, 832)),
    ])
    def test_all_resolution_presets(self, preset, expected):
        """Should return correct dimensions for all presets"""
        manager = ConfigManager()
        manager._store.set_resolution_preset(preset)

        result = manager.get_resolution_tuple()

        assert result == expected


class TestConfigManagerVideoSettings:
    """Test video generation timing settings"""

    @pytest.mark.unit
    def test_get_video_initial_wait_default(self):
        """Should return default video initial wait"""
        manager = ConfigManager()

        assert manager.get_video_initial_wait() == 60

    @pytest.mark.unit
    def test_get_video_initial_wait_custom(self):
        """Should return custom video initial wait"""
        manager = ConfigManager()
        manager._store.set("video_initial_wait", "120")

        assert manager.get_video_initial_wait() == 120

    @pytest.mark.unit
    def test_get_video_retry_delay_default(self):
        """Should return default video retry delay"""
        manager = ConfigManager()

        assert manager.get_video_retry_delay() == 30

    @pytest.mark.unit
    def test_get_video_retry_delay_custom(self):
        """Should return custom video retry delay"""
        manager = ConfigManager()
        manager._store.set("video_retry_delay", "45")

        assert manager.get_video_retry_delay() == 45

    @pytest.mark.unit
    def test_get_video_max_retries_default(self):
        """Should return default video max retries"""
        manager = ConfigManager()

        assert manager.get_video_max_retries() == 20

    @pytest.mark.unit
    def test_get_video_max_retries_custom(self):
        """Should return custom video max retries"""
        manager = ConfigManager()
        manager._store.set("video_max_retries", "30")

        assert manager.get_video_max_retries() == 30


class TestConfigManagerSetupWizard:
    """Test setup wizard methods"""

    @pytest.mark.unit
    def test_is_first_run_setup_completed(self):
        """Should return False if setup_completed is True"""
        manager = ConfigManager()
        manager._store.set("setup_completed", "true")

        assert manager.is_first_run() is False

    @pytest.mark.unit
    def test_is_first_run_no_comfy_root(self):
        """Should return True if comfy_root is not set"""
        manager = ConfigManager()
        # Clear any existing comfy_root
        manager._store.delete("comfy_root")

        assert manager.is_first_run() is True

    @pytest.mark.unit
    def test_is_first_run_comfy_root_exists(self, tmp_path):
        """Should return False if comfy_root exists"""
        manager = ConfigManager()
        comfy_dir = tmp_path / "comfyui"
        comfy_dir.mkdir()
        manager._store.set_comfy_root(str(comfy_dir))

        assert manager.is_first_run() is False

    @pytest.mark.unit
    def test_is_first_run_comfy_root_not_exists(self):
        """Should return True if comfy_root path doesn't exist"""
        manager = ConfigManager()
        manager._store.set_comfy_root("/nonexistent/path/to/comfyui")

        assert manager.is_first_run() is True

    @pytest.mark.unit
    def test_mark_setup_completed(self):
        """Should mark setup as completed"""
        manager = ConfigManager()

        manager.mark_setup_completed()

        assert manager._store.get("setup_completed") == "true"
        assert manager.is_first_run() is False


class TestConfigManagerBackends:
    """Test backend management methods"""

    @pytest.mark.unit
    def test_get_backends_default(self):
        """Should return default local backend if none configured"""
        manager = ConfigManager()

        backends = manager.get_backends()

        assert "local" in backends
        assert backends["local"]["type"] == "local"

    @pytest.mark.unit
    def test_add_backend(self):
        """Should add a new backend"""
        manager = ConfigManager()

        manager.add_backend("colab", "Google Colab", "https://xyz.trycloudflare.com", "remote")

        backends = manager.get_backends()
        assert "colab" in backends
        assert backends["colab"]["name"] == "Google Colab"
        assert backends["colab"]["type"] == "remote"

    @pytest.mark.unit
    def test_set_active_backend(self):
        """Should switch active backend"""
        manager = ConfigManager()
        manager.add_backend("colab", "Colab", "https://example.com", "remote")

        result = manager.set_active_backend("colab")

        assert result is True
        assert manager.get_active_backend_id() == "colab"

    @pytest.mark.unit
    def test_set_active_backend_not_found(self):
        """Should return False if backend not found"""
        manager = ConfigManager()

        result = manager.set_active_backend("nonexistent")

        assert result is False

    @pytest.mark.unit
    def test_remove_backend(self):
        """Should remove a backend"""
        manager = ConfigManager()
        manager.add_backend("colab", "Colab", "https://example.com", "remote")

        result = manager.remove_backend("colab")

        assert result is True
        assert "colab" not in manager.get_backends()

    @pytest.mark.unit
    def test_remove_backend_cannot_remove_local(self):
        """Should not allow removing local backend"""
        manager = ConfigManager()

        result = manager.remove_backend("local")

        assert result is False
        assert "local" in manager.get_backends()

    @pytest.mark.unit
    def test_remove_active_backend_switches_to_local(self):
        """Should switch to local when removing active backend"""
        manager = ConfigManager()
        manager.add_backend("colab", "Colab", "https://example.com", "remote")
        manager.set_active_backend("colab")

        manager.remove_backend("colab")

        assert manager.get_active_backend_id() == "local"

    @pytest.mark.unit
    def test_update_backend(self):
        """Should update backend configuration"""
        manager = ConfigManager()

        result = manager.update_backend("local", name="My Local", url="http://localhost:9000")

        assert result is True
        backend = manager.get_backends()["local"]
        assert backend["name"] == "My Local"
        assert backend["url"] == "http://localhost:9000"

    @pytest.mark.unit
    def test_update_backend_not_found(self):
        """Should return False if backend not found"""
        manager = ConfigManager()

        result = manager.update_backend("nonexistent", name="Test")

        assert result is False

    @pytest.mark.unit
    def test_is_remote_backend(self):
        """Should detect remote backend"""
        manager = ConfigManager()
        manager.add_backend("colab", "Colab", "https://example.com", "remote")
        manager.set_active_backend("colab")

        assert manager.is_remote_backend() is True

    @pytest.mark.unit
    def test_is_remote_backend_local(self):
        """Should return False for local backend"""
        manager = ConfigManager()

        assert manager.is_remote_backend() is False


class TestConfigManagerApiKeys:
    """Test API key management (encrypted via SettingsStore)"""

    @pytest.mark.unit
    def test_civitai_api_key(self):
        """Should get and set Civitai API key (encrypted)"""
        manager = ConfigManager()

        assert manager.get_civitai_api_key() == ""

        manager.set_civitai_api_key("test-key-123")
        assert manager.get_civitai_api_key() == "test-key-123"

    @pytest.mark.unit
    def test_huggingface_token(self):
        """Should get and set Huggingface token (encrypted)"""
        manager = ConfigManager()

        assert manager.get_huggingface_token() == ""

        manager.set_huggingface_token("hf_token_xyz")
        assert manager.get_huggingface_token() == "hf_token_xyz"

    @pytest.mark.unit
    def test_google_tts_api_key(self):
        """Should get and set Google TTS API key (encrypted)"""
        manager = ConfigManager()

        assert manager.get_google_tts_api_key() == ""

        manager.set_google_tts_api_key("gcp-key-abc")
        assert manager.get_google_tts_api_key() == "gcp-key-abc"

    @pytest.mark.unit
    def test_max_parallel_downloads(self):
        """Should get and set max parallel downloads with bounds"""
        manager = ConfigManager()

        assert manager.get_max_parallel_downloads() == 2  # default

        manager.set_max_parallel_downloads(4)
        assert manager.get_max_parallel_downloads() == 4

        # Test bounds
        manager.set_max_parallel_downloads(10)  # over max
        assert manager.get_max_parallel_downloads() == 5

        manager.set_max_parallel_downloads(0)  # under min
        assert manager.get_max_parallel_downloads() == 1

    @pytest.mark.unit
    def test_api_keys_are_encrypted_in_database(self):
        """Should store API keys encrypted in the database"""
        import sqlite3

        manager = ConfigManager()
        manager.set_civitai_api_key("secret-api-key")

        # Check raw database value
        conn = sqlite3.connect(manager._store.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value, encrypted FROM settings WHERE key = ?", ("civitai_api_key",))
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        stored_value, is_encrypted = row
        assert is_encrypted == 1
        assert stored_value != "secret-api-key"  # Should be encrypted

        # But retrieving via API should decrypt
        assert manager.get_civitai_api_key() == "secret-api-key"


class TestConfigManagerSageAttention:
    """Test SageAttention setting"""

    @pytest.mark.unit
    def test_use_sage_attention_default(self):
        """Should return False by default"""
        manager = ConfigManager()

        assert manager.use_sage_attention() is False

    @pytest.mark.unit
    def test_use_sage_attention_enabled(self):
        """Should return True when enabled"""
        manager = ConfigManager()
        manager._store.set_sage_attention(True)

        assert manager.use_sage_attention() is True

    @pytest.mark.unit
    def test_use_sage_attention_disabled(self):
        """Should return False when disabled"""
        manager = ConfigManager()
        manager._store.set_sage_attention(False)

        assert manager.use_sage_attention() is False


class TestConfigManagerConfigProperty:
    """Test the backwards-compatible config property"""

    @pytest.mark.unit
    def test_config_property_returns_dict(self):
        """Should return all settings as dictionary"""
        manager = ConfigManager()
        manager.set("key1", "value1")
        manager.set("key2", "value2")

        config = manager.config

        assert isinstance(config, dict)
        assert config.get("key1") == "value1"
        assert config.get("key2") == "value2"
