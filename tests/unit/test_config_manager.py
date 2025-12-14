"""Unit tests for ConfigManager"""
import pytest
import json
import os
from pathlib import Path

from infrastructure.config_manager import ConfigManager


class TestConfigManagerInit:
    """Test ConfigManager initialization"""

    @pytest.mark.unit
    def test_init_with_default_path(self, tmp_path, monkeypatch):
        """Should initialize with default config path"""
        # Arrange
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "settings.json"
        config_file.write_text('{"comfy_url": "http://localhost:8188"}')

        # Act
        manager = ConfigManager(str(config_file))

        # Assert
        assert manager.config_path == str(config_file)
        assert manager.config["comfy_url"] == "http://localhost:8188"

    @pytest.mark.unit
    def test_init_with_custom_path(self, tmp_path):
        """Should initialize with custom config path"""
        # Arrange
        custom_config = tmp_path / "custom" / "config.json"
        custom_config.parent.mkdir()
        custom_config.write_text('{"test": "value"}')

        # Act
        manager = ConfigManager(str(custom_config))

        # Assert
        assert manager.config_path == str(custom_config)
        assert manager.config["test"] == "value"

    @pytest.mark.unit
    def test_init_creates_default_if_missing(self, tmp_path):
        """Should create default config if file doesn't exist"""
        # Arrange
        nonexistent_path = tmp_path / "missing" / "config.json"

        # Act
        manager = ConfigManager(str(nonexistent_path))

        # Assert
        assert manager.config["comfy_url"] == "http://127.0.0.1:8188"
        assert "workflow_dir" in manager.config
        assert manager.config_dir.endswith("missing")

    @pytest.mark.unit
    def test_init_sets_config_dir_for_default(self, tmp_path, monkeypatch):
        """Default path should yield config_dir='config' when relative default used."""
        monkeypatch.chdir(tmp_path)
        default_path = tmp_path / "config" / "settings.json"
        default_path.parent.mkdir()
        default_path.write_text("{}", encoding="utf-8")

        manager = ConfigManager(str(default_path))
        assert manager.config_dir == str(default_path.parent)


class TestConfigManagerLoad:
    """Test ConfigManager.load()"""

    @pytest.mark.unit
    def test_load_valid_config(self, sample_config_file):
        """Should load valid config file"""
        # Act
        manager = ConfigManager(str(sample_config_file))
        config = manager.load()

        # Assert
        assert config["comfy_url"] == "http://127.0.0.1:8188"
        assert config["comfy_root"] == "/home/user/ComfyUI"

    @pytest.mark.unit
    def test_load_invalid_json_returns_default(self, tmp_path):
        """Should return default config if JSON is invalid"""
        # Arrange
        invalid_config = tmp_path / "invalid.json"
        invalid_config.write_text("{broken json")

        # Act
        manager = ConfigManager(str(invalid_config))

        # Assert
        assert manager.config["comfy_url"] == "http://127.0.0.1:8188"

    @pytest.mark.unit
    def test_load_missing_file_returns_default(self, tmp_path):
        """Should return default config if file missing"""
        # Arrange
        missing_file = tmp_path / "missing.json"

        # Act
        manager = ConfigManager(str(missing_file))

        # Assert
        assert manager.config is not None
        assert "comfy_url" in manager.config


class TestConfigManagerSave:
    """Test ConfigManager.save()"""

    @pytest.mark.unit
    def test_save_creates_file(self, tmp_path):
        """Should create config file when saving"""
        # Arrange
        config_file = tmp_path / "config" / "new_settings.json"
        manager = ConfigManager(str(config_file))
        manager.config["test_key"] = "test_value"

        # Act
        manager.save()

        # Assert
        assert config_file.exists()
        with open(config_file) as f:
            saved = json.load(f)
        assert saved["test_key"] == "test_value"

    @pytest.mark.unit
    def test_save_with_explicit_config(self, tmp_path):
        """Should save explicit config dict"""
        # Arrange
        config_file = tmp_path / "settings.json"
        manager = ConfigManager(str(config_file))
        new_config = {"custom": "data", "another": 123}

        # Act
        manager.save(new_config)

        # Assert
        with open(config_file) as f:
            saved = json.load(f)
        assert saved["custom"] == "data"
        assert saved["another"] == 123

    @pytest.mark.unit
    def test_save_preserves_encoding(self, tmp_path):
        """Should preserve UTF-8 encoding"""
        # Arrange
        config_file = tmp_path / "settings.json"
        manager = ConfigManager(str(config_file))
        manager.config["german"] = "Überprüfung"

        # Act
        manager.save()

        # Assert
        with open(config_file, encoding='utf-8') as f:
            saved = json.load(f)
        assert saved["german"] == "Überprüfung"

    @pytest.mark.unit
    def test_save_handles_exception(self, tmp_path, capsys, monkeypatch):
        """Should print failure message when save raises"""
        config_file = tmp_path / "settings.json"
        manager = ConfigManager(str(config_file))

        def fake_open(*_args, **_kwargs):
            raise PermissionError("no write")

        monkeypatch.setattr("builtins.open", fake_open)

        manager.save()
        captured = capsys.readouterr()
        assert "Failed to save config" in captured.out


class TestConfigManagerRefresh:
    """Test ConfigManager.refresh()"""

    @pytest.mark.unit
    def test_refresh_reloads_from_disk(self, tmp_path):
        """Should reload config from disk"""
        # Arrange
        config_file = tmp_path / "settings.json"
        config_file.write_text('{"value": "original"}')
        manager = ConfigManager(str(config_file))
        assert manager.config["value"] == "original"

        # Modify file externally
        config_file.write_text('{"value": "updated"}')

        # Act
        result = manager.refresh()

        # Assert
        assert manager.config["value"] == "updated"
        assert result["value"] == "updated"


class TestConfigManagerGetSet:
    """Test ConfigManager.get() and set()"""

    @pytest.mark.unit
    def test_get_existing_key(self, sample_config_file):
        """Should get existing config value"""
        # Arrange
        manager = ConfigManager(str(sample_config_file))

        # Act
        value = manager.get("comfy_url")

        # Assert
        assert value == "http://127.0.0.1:8188"

    @pytest.mark.unit
    def test_get_missing_key_with_default(self, sample_config_file):
        """Should return default for missing key"""
        # Arrange
        manager = ConfigManager(str(sample_config_file))

        # Act
        value = manager.get("nonexistent_key", "default_value")

        # Assert
        assert value == "default_value"

    @pytest.mark.unit
    def test_set_updates_and_saves(self, tmp_path):
        """Should update value and auto-save"""
        # Arrange
        config_file = tmp_path / "settings.json"
        manager = ConfigManager(str(config_file))

        # Act
        manager.set("new_key", "new_value")

        # Assert
        assert manager.config["new_key"] == "new_value"
        # Verify saved to disk
        with open(config_file) as f:
            saved = json.load(f)
        assert saved["new_key"] == "new_value"


class TestConfigManagerConvenienceMethods:
    """Test convenience getter methods"""

    @pytest.mark.unit
    def test_get_comfy_url(self, sample_config_file):
        """Should get ComfyUI URL"""
        # Arrange
        manager = ConfigManager(str(sample_config_file))

        # Act
        url = manager.get_comfy_url()

        # Assert
        assert url == "http://127.0.0.1:8188"

    @pytest.mark.unit
    def test_get_comfy_url_default(self, tmp_path):
        """Should return default URL if not set"""
        # Arrange
        config_file = tmp_path / "empty.json"
        config_file.write_text("{}")
        manager = ConfigManager(str(config_file))

        # Act
        url = manager.get_comfy_url()

        # Assert
        assert url == "http://127.0.0.1:8188"

    @pytest.mark.unit
    def test_get_comfy_root_expands_tilde(self, tmp_path):
        """Should expand ~ in comfy_root path"""
        # Arrange
        config_file = tmp_path / "settings.json"
        config_file.write_text('{"comfy_root": "~/ComfyUI"}')
        manager = ConfigManager(str(config_file))

        # Act
        root = manager.get_comfy_root()

        # Assert
        assert "~" not in root
        assert "ComfyUI" in root

    @pytest.mark.unit
    def test_get_workflow_dir(self, sample_config_file):
        """Should get workflow directory"""
        # Arrange
        manager = ConfigManager(str(sample_config_file))

        # Act
        wf_dir = manager.get_workflow_dir()

        # Assert
        assert wf_dir == "config/workflow_templates"

    @pytest.mark.unit
    def test_get_current_project(self, tmp_path):
        """Should get current project slug"""
        # Arrange
        config_file = tmp_path / "settings.json"
        config_file.write_text('{"current_project": "test-project"}')
        manager = ConfigManager(str(config_file))

        # Act
        project = manager.get_current_project()

        # Assert
        assert project == "test-project"

    @pytest.mark.unit
    def test_get_current_storyboard(self, tmp_path):
        """Should get current storyboard path"""
        # Arrange
        config_file = tmp_path / "settings.json"
        config_file.write_text('{"current_storyboard": "storyboard.json"}')
        manager = ConfigManager(str(config_file))

        # Act
        storyboard = manager.get_current_storyboard()

        # Assert
        assert storyboard == "storyboard.json"


class TestConfigManagerResolutionPresets:
    """Test resolution preset methods"""

    @pytest.mark.unit
    def test_get_resolution_preset_default(self, tmp_path):
        """Should return default preset"""
        # Arrange
        config_file = tmp_path / "settings.json"
        config_file.write_text("{}")
        manager = ConfigManager(str(config_file))

        # Act
        preset = manager.get_resolution_preset()

        # Assert
        assert preset == "1080p_landscape"

    @pytest.mark.unit
    def test_get_resolution_tuple_1080p_landscape(self, tmp_path):
        """Should return 1080p landscape dimensions"""
        # Arrange
        config_file = tmp_path / "settings.json"
        config_file.write_text('{"global_resolution": "1080p_landscape"}')
        manager = ConfigManager(str(config_file))

        # Act
        width, height = manager.get_resolution_tuple()

        # Assert
        assert width == 1920
        assert height == 1080

    @pytest.mark.unit
    def test_get_resolution_tuple_720p_portrait(self, tmp_path):
        """Should return 720p portrait dimensions"""
        # Arrange
        config_file = tmp_path / "settings.json"
        config_file.write_text('{"global_resolution": "720p_portrait"}')
        manager = ConfigManager(str(config_file))

        # Act
        width, height = manager.get_resolution_tuple()

        # Assert
        assert width == 720
        assert height == 1280

    @pytest.mark.unit
    def test_get_resolution_tuple_invalid_returns_default(self, tmp_path):
        """Should return default dimensions for invalid preset"""
        # Arrange
        config_file = tmp_path / "settings.json"
        config_file.write_text('{"global_resolution": "invalid_preset"}')
        manager = ConfigManager(str(config_file))

        # Act
        width, height = manager.get_resolution_tuple()

        # Assert
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
    ])
    def test_all_resolution_presets(self, tmp_path, preset, expected):
        """Should return correct dimensions for all presets"""
        # Arrange
        config_file = tmp_path / "settings.json"
        config_file.write_text(f'{{"global_resolution": "{preset}"}}')
        manager = ConfigManager(str(config_file))

        # Act
        result = manager.get_resolution_tuple()

        # Assert
        assert result == expected


class TestConfigManagerDefaultConfig:
    """Test default configuration"""

    @pytest.mark.unit
    def test_default_config_structure(self, tmp_path):
        """Should have all required default keys"""
        # Arrange
        config_file = tmp_path / "new.json"
        manager = ConfigManager(str(config_file))

        # Act
        default = manager._default_config()

        # Assert
        required_keys = [
            "comfy_url",
            "comfy_root",
            "workflow_dir",
            "output_dir",
            "current_project",
            "current_storyboard",
            "global_resolution",
            "log_level"
        ]
        for key in required_keys:
            assert key in default

    @pytest.mark.unit
    def test_default_values(self, tmp_path):
        """Should have sensible default values"""
        # Arrange
        config_file = tmp_path / "new.json"
        manager = ConfigManager(str(config_file))

        # Act
        default = manager._default_config()

        # Assert
        assert default["comfy_url"] == "http://127.0.0.1:8188"
        assert default["log_level"] == "INFO"
        assert default["max_concurrent_jobs"] == 1
        assert default["auto_save_results"] is True


class TestConfigManagerMissingCoverage:
    """Test remaining uncovered methods"""

    @pytest.mark.unit
    def test_get_output_dir(self, tmp_path):
        """Should get output directory from config"""
        # Arrange
        config_file = tmp_path / "settings.json"
        manager = ConfigManager(str(config_file))
        manager.config["output_dir"] = "my_custom_output"

        # Act
        result = manager.get_output_dir()

        # Assert
        assert result == "my_custom_output"

    @pytest.mark.unit
    def test_get_output_dir_default(self, tmp_path):
        """Should return default output dir if not set"""
        # Arrange
        config_file = tmp_path / "settings.json"
        manager = ConfigManager(str(config_file))
        manager.config.pop("output_dir", None)

        # Act
        result = manager.get_output_dir()

        # Assert
        assert result == "output"

    @pytest.mark.unit
    def test_get_log_level(self, tmp_path):
        """Should get log level from config"""
        # Arrange
        config_file = tmp_path / "settings.json"
        manager = ConfigManager(str(config_file))
        manager.config["log_level"] = "DEBUG"

        # Act
        result = manager.get_log_level()

        # Assert
        assert result == "DEBUG"

    @pytest.mark.unit
    def test_get_log_level_default(self, tmp_path):
        """Should return default log level if not set"""
        # Arrange
        config_file = tmp_path / "settings.json"
        manager = ConfigManager(str(config_file))
        manager.config.pop("log_level", None)

        # Act
        result = manager.get_log_level()

        # Assert
        assert result == "INFO"
