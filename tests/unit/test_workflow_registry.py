"""Unit tests for WorkflowRegistry"""
import pytest
import os
import json
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from infrastructure.workflow_registry import WorkflowRegistry


class TestWorkflowRegistryInit:
    """Test WorkflowRegistry initialization"""

    @pytest.mark.unit
    def test_init_default_paths(self):
        """Should initialize with default paths"""
        # Act
        registry = WorkflowRegistry()

        # Assert
        assert registry.config_path == "config/workflow_presets.json"
        assert registry.workflow_dir == "config/workflow_templates"

    @pytest.mark.unit
    def test_init_custom_paths(self):
        """Should initialize with custom paths"""
        # Act
        registry = WorkflowRegistry(
            config_path="custom/presets.json",
            workflow_dir="custom/workflows"
        )

        # Assert
        assert registry.config_path == "custom/presets.json"
        assert registry.workflow_dir == "custom/workflows"


class TestWorkflowRegistryLoadPresets:
    """Test WorkflowRegistry._load_presets()"""

    @pytest.mark.unit
    def test_load_presets_valid_file(self, tmp_path):
        """Should load presets from valid JSON file"""
        # Arrange
        config_file = tmp_path / "presets.json"
        presets_data = {
            "categories": {
                "flux": [
                    {"file": "flux_test.json", "name": "Flux Test", "default": True}
                ],
                "wan": [
                    {"file": "wan_test.json", "name": "Wan Test"}
                ]
            }
        }

        with open(config_file, "w") as f:
            json.dump(presets_data, f)

        registry = WorkflowRegistry(
            config_path=str(config_file),
            workflow_dir=str(tmp_path)
        )

        # Act
        result = registry._load_presets()

        # Assert
        assert "categories" in result
        assert "flux" in result["categories"]
        assert "wan" in result["categories"]
        assert len(result["categories"]["flux"]) == 1
        assert result["categories"]["flux"][0]["name"] == "Flux Test"

    @pytest.mark.unit
    def test_load_presets_file_not_exists(self, tmp_path):
        """Should return default structure when file doesn't exist"""
        # Arrange
        config_file = tmp_path / "nonexistent.json"

        registry = WorkflowRegistry(
            config_path=str(config_file),
            workflow_dir=str(tmp_path)
        )

        # Act
        result = registry._load_presets()

        # Assert
        assert result == {"categories": {}}

    @pytest.mark.unit
    def test_load_presets_invalid_json(self, tmp_path, capsys):
        """Should return default structure and print warning for invalid JSON"""
        # Arrange
        config_file = tmp_path / "invalid.json"
        with open(config_file, "w") as f:
            f.write("{ invalid json }")

        registry = WorkflowRegistry(
            config_path=str(config_file),
            workflow_dir=str(tmp_path)
        )

        # Act
        result = registry._load_presets()

        # Assert
        assert result == {"categories": {}}

        # Verify warning was printed
        captured = capsys.readouterr()
        assert "⚠️" in captured.out
        assert "Failed to load workflow presets" in captured.out


class TestWorkflowRegistryGetPresets:
    """Test WorkflowRegistry.get_presets()"""

    @pytest.mark.unit
    def test_get_presets_all(self, tmp_path):
        """Should return all presets when no category specified"""
        # Arrange
        config_file = tmp_path / "presets.json"
        presets_data = {
            "categories": {
                "flux": [
                    {"file": "flux1.json", "name": "Flux 1"},
                    {"file": "flux2.json", "name": "Flux 2"}
                ],
                "wan": [
                    {"file": "wan1.json", "name": "Wan 1"}
                ]
            }
        }

        with open(config_file, "w") as f:
            json.dump(presets_data, f)

        registry = WorkflowRegistry(
            config_path=str(config_file),
            workflow_dir=str(tmp_path)
        )

        # Act
        result = registry.get_presets()

        # Assert
        assert len(result) == 3
        assert any(p["name"] == "Flux 1" for p in result)
        assert any(p["name"] == "Flux 2" for p in result)
        assert any(p["name"] == "Wan 1" for p in result)

    @pytest.mark.unit
    def test_get_presets_specific_category(self, tmp_path):
        """Should return presets for specific category"""
        # Arrange
        config_file = tmp_path / "presets.json"
        presets_data = {
            "categories": {
                "flux": [
                    {"file": "flux1.json", "name": "Flux 1"}
                ],
                "wan": [
                    {"file": "wan1.json", "name": "Wan 1"}
                ]
            }
        }

        with open(config_file, "w") as f:
            json.dump(presets_data, f)

        registry = WorkflowRegistry(
            config_path=str(config_file),
            workflow_dir=str(tmp_path)
        )

        # Act
        result = registry.get_presets(category="flux")

        # Assert
        assert len(result) == 1
        assert result[0]["name"] == "Flux 1"

    @pytest.mark.unit
    def test_get_presets_nonexistent_category(self, tmp_path):
        """Should return empty list for non-existent category"""
        # Arrange
        config_file = tmp_path / "presets.json"
        presets_data = {
            "categories": {
                "flux": [
                    {"file": "flux1.json", "name": "Flux 1"}
                ]
            }
        }

        with open(config_file, "w") as f:
            json.dump(presets_data, f)

        registry = WorkflowRegistry(
            config_path=str(config_file),
            workflow_dir=str(tmp_path)
        )

        # Act
        result = registry.get_presets(category="nonexistent")

        # Assert
        assert result == []


class TestWorkflowRegistryGetFiles:
    """Test WorkflowRegistry.get_files()"""

    @pytest.mark.unit
    def test_get_files_with_valid_presets(self, tmp_path):
        """Should return files from presets when files exist"""
        # Arrange
        workflow_dir = tmp_path / "workflows"
        workflow_dir.mkdir()

        # Create workflow files
        (workflow_dir / "flux1.json").touch()
        (workflow_dir / "wan1.json").touch()

        config_file = tmp_path / "presets.json"
        presets_data = {
            "categories": {
                "flux": [
                    {"file": "flux1.json", "name": "Flux 1"}
                ],
                "wan": [
                    {"file": "wan1.json", "name": "Wan 1"}
                ]
            }
        }

        with open(config_file, "w") as f:
            json.dump(presets_data, f)

        registry = WorkflowRegistry(
            config_path=str(config_file),
            workflow_dir=str(workflow_dir)
        )

        # Act
        result = registry.get_files()

        # Assert
        assert len(result) == 2
        assert "flux1.json" in result
        assert "wan1.json" in result

    @pytest.mark.unit
    def test_get_files_with_missing_files(self, tmp_path, capsys):
        """Should warn about missing files and skip them"""
        # Arrange
        workflow_dir = tmp_path / "workflows"
        workflow_dir.mkdir()

        # Create only one file
        (workflow_dir / "flux1.json").touch()

        config_file = tmp_path / "presets.json"
        presets_data = {
            "categories": {
                "flux": [
                    {"file": "flux1.json", "name": "Flux 1"}
                ],
                "wan": [
                    {"file": "missing.json", "name": "Missing"}  # File doesn't exist
                ]
            }
        }

        with open(config_file, "w") as f:
            json.dump(presets_data, f)

        registry = WorkflowRegistry(
            config_path=str(config_file),
            workflow_dir=str(workflow_dir)
        )

        # Act
        result = registry.get_files()

        # Assert
        assert len(result) == 1
        assert "flux1.json" in result

        # Verify warning was printed
        captured = capsys.readouterr()
        assert "⚠️" in captured.out
        assert "Workflow preset missing file" in captured.out
        assert "missing.json" in captured.out

    @pytest.mark.unit
    def test_get_files_fallback_to_directory_scan(self, tmp_path):
        """Should fallback to directory scan when no valid presets"""
        # Arrange
        workflow_dir = tmp_path / "workflows"
        workflow_dir.mkdir()

        # Create workflow files
        (workflow_dir / "workflow1.json").touch()
        (workflow_dir / "workflow2.json").touch()
        (workflow_dir / "workflow3.json").touch()
        (workflow_dir / "not_json.txt").touch()  # Should be ignored

        config_file = tmp_path / "presets.json"
        presets_data = {
            "categories": {
                "flux": [
                    {"file": "missing.json", "name": "Missing"}  # File doesn't exist
                ]
            }
        }

        with open(config_file, "w") as f:
            json.dump(presets_data, f)

        registry = WorkflowRegistry(
            config_path=str(config_file),
            workflow_dir=str(workflow_dir)
        )

        # Act
        result = registry.get_files()

        # Assert
        assert len(result) == 3
        assert "workflow1.json" in result
        assert "workflow2.json" in result
        assert "workflow3.json" in result
        assert "not_json.txt" not in result

    @pytest.mark.unit
    def test_get_files_workflow_dir_not_exists(self, tmp_path):
        """Should return empty list when workflow directory doesn't exist"""
        # Arrange
        workflow_dir = tmp_path / "nonexistent"

        config_file = tmp_path / "presets.json"
        presets_data = {
            "categories": {
                "flux": [
                    {"file": "missing.json", "name": "Missing"}
                ]
            }
        }

        with open(config_file, "w") as f:
            json.dump(presets_data, f)

        registry = WorkflowRegistry(
            config_path=str(config_file),
            workflow_dir=str(workflow_dir)
        )

        # Act
        result = registry.get_files()

        # Assert
        assert result == []

    @pytest.mark.unit
    def test_get_files_deduplication(self, tmp_path):
        """Should deduplicate files listed multiple times"""
        # Arrange
        workflow_dir = tmp_path / "workflows"
        workflow_dir.mkdir()

        # Create workflow file
        (workflow_dir / "flux1.json").touch()

        config_file = tmp_path / "presets.json"
        presets_data = {
            "categories": {
                "flux": [
                    {"file": "flux1.json", "name": "Flux 1"},
                    {"file": "flux1.json", "name": "Flux 1 Duplicate"}  # Same file
                ]
            }
        }

        with open(config_file, "w") as f:
            json.dump(presets_data, f)

        registry = WorkflowRegistry(
            config_path=str(config_file),
            workflow_dir=str(workflow_dir)
        )

        # Act
        result = registry.get_files()

        # Assert
        assert len(result) == 1
        assert "flux1.json" in result

    @pytest.mark.unit
    def test_get_files_specific_category(self, tmp_path):
        """Should return files for specific category"""
        # Arrange
        workflow_dir = tmp_path / "workflows"
        workflow_dir.mkdir()

        # Create workflow files
        (workflow_dir / "flux1.json").touch()
        (workflow_dir / "wan1.json").touch()

        config_file = tmp_path / "presets.json"
        presets_data = {
            "categories": {
                "flux": [
                    {"file": "flux1.json", "name": "Flux 1"}
                ],
                "wan": [
                    {"file": "wan1.json", "name": "Wan 1"}
                ]
            }
        }

        with open(config_file, "w") as f:
            json.dump(presets_data, f)

        registry = WorkflowRegistry(
            config_path=str(config_file),
            workflow_dir=str(workflow_dir)
        )

        # Act
        result = registry.get_files(category="flux")

        # Assert
        assert len(result) == 1
        assert "flux1.json" in result


class TestWorkflowRegistryGetDefault:
    """Test WorkflowRegistry.get_default()"""

    @pytest.mark.unit
    def test_get_default_with_marked_default(self, tmp_path):
        """Should return file marked as default"""
        # Arrange
        workflow_dir = tmp_path / "workflows"
        workflow_dir.mkdir()

        # Create workflow files
        (workflow_dir / "flux1.json").touch()
        (workflow_dir / "flux2.json").touch()

        config_file = tmp_path / "presets.json"
        presets_data = {
            "categories": {
                "flux": [
                    {"file": "flux1.json", "name": "Flux 1"},
                    {"file": "flux2.json", "name": "Flux 2", "default": True}
                ]
            }
        }

        with open(config_file, "w") as f:
            json.dump(presets_data, f)

        registry = WorkflowRegistry(
            config_path=str(config_file),
            workflow_dir=str(workflow_dir)
        )

        # Act
        result = registry.get_default(category="flux")

        # Assert
        assert result == "flux2.json"

    @pytest.mark.unit
    def test_get_default_no_marked_default(self, tmp_path):
        """Should return first file when no default marked"""
        # Arrange
        workflow_dir = tmp_path / "workflows"
        workflow_dir.mkdir()

        # Create workflow files
        (workflow_dir / "flux1.json").touch()
        (workflow_dir / "flux2.json").touch()

        config_file = tmp_path / "presets.json"
        presets_data = {
            "categories": {
                "flux": [
                    {"file": "flux1.json", "name": "Flux 1"},
                    {"file": "flux2.json", "name": "Flux 2"}
                ]
            }
        }

        with open(config_file, "w") as f:
            json.dump(presets_data, f)

        registry = WorkflowRegistry(
            config_path=str(config_file),
            workflow_dir=str(workflow_dir)
        )

        # Act
        result = registry.get_default(category="flux")

        # Assert
        assert result == "flux1.json"

    @pytest.mark.unit
    def test_get_default_file_missing(self, tmp_path):
        """Should return first available file when marked default doesn't exist"""
        # Arrange
        workflow_dir = tmp_path / "workflows"
        workflow_dir.mkdir()

        # Create only one file
        (workflow_dir / "flux1.json").touch()

        config_file = tmp_path / "presets.json"
        presets_data = {
            "categories": {
                "flux": [
                    {"file": "flux1.json", "name": "Flux 1"},
                    {"file": "missing.json", "name": "Missing", "default": True}  # Doesn't exist
                ]
            }
        }

        with open(config_file, "w") as f:
            json.dump(presets_data, f)

        registry = WorkflowRegistry(
            config_path=str(config_file),
            workflow_dir=str(workflow_dir)
        )

        # Act
        result = registry.get_default(category="flux")

        # Assert
        assert result == "flux1.json"

    @pytest.mark.unit
    def test_get_default_no_files(self, tmp_path):
        """Should return None when no files available"""
        # Arrange
        workflow_dir = tmp_path / "workflows"
        workflow_dir.mkdir()

        config_file = tmp_path / "presets.json"
        presets_data = {
            "categories": {
                "flux": [
                    {"file": "missing.json", "name": "Missing"}  # Doesn't exist
                ]
            }
        }

        with open(config_file, "w") as f:
            json.dump(presets_data, f)

        registry = WorkflowRegistry(
            config_path=str(config_file),
            workflow_dir=str(workflow_dir)
        )

        # Act
        result = registry.get_default(category="flux")

        # Assert
        assert result is None


class TestWorkflowRegistryReadRaw:
    """Test WorkflowRegistry.read_raw()"""

    @pytest.mark.unit
    def test_read_raw_existing_file(self, tmp_path):
        """Should read raw config content"""
        # Arrange
        config_file = tmp_path / "presets.json"
        presets_data = {
            "categories": {
                "flux": [
                    {"file": "flux1.json", "name": "Flux 1"}
                ]
            }
        }

        with open(config_file, "w") as f:
            json.dump(presets_data, f, indent=2)

        registry = WorkflowRegistry(
            config_path=str(config_file),
            workflow_dir=str(tmp_path)
        )

        # Act
        result = registry.read_raw()

        # Assert
        assert "categories" in result
        assert "flux" in result
        # Verify it's valid JSON
        parsed = json.loads(result)
        assert "flux" in parsed["categories"]

    @pytest.mark.unit
    def test_read_raw_file_not_exists(self, tmp_path):
        """Should return default structure when file doesn't exist"""
        # Arrange
        config_file = tmp_path / "nonexistent.json"

        registry = WorkflowRegistry(
            config_path=str(config_file),
            workflow_dir=str(tmp_path)
        )

        # Act
        result = registry.read_raw()

        # Assert
        expected = json.dumps({"categories": {}}, indent=2)
        assert result == expected


class TestWorkflowRegistrySaveRaw:
    """Test WorkflowRegistry.save_raw()"""

    @pytest.mark.unit
    def test_save_raw_valid_json(self, tmp_path):
        """Should save valid JSON content"""
        # Arrange
        config_file = tmp_path / "config" / "presets.json"

        registry = WorkflowRegistry(
            config_path=str(config_file),
            workflow_dir=str(tmp_path)
        )

        content = json.dumps({
            "categories": {
                "flux": [
                    {"file": "flux1.json", "name": "Flux 1"}
                ]
            }
        }, indent=2)

        # Act
        result = registry.save_raw(content)

        # Assert
        assert "✅ Gespeichert" in result
        assert "workflow_presets.json" in result

        # Verify file was written
        assert config_file.exists()
        with open(config_file) as f:
            data = json.load(f)
        assert "flux" in data["categories"]

    @pytest.mark.unit
    def test_save_raw_invalid_json(self, tmp_path):
        """Should return error message for invalid JSON"""
        # Arrange
        config_file = tmp_path / "presets.json"

        registry = WorkflowRegistry(
            config_path=str(config_file),
            workflow_dir=str(tmp_path)
        )

        content = "{ invalid json }"

        # Act
        result = registry.save_raw(content)

        # Assert
        assert "❌ Fehler" in result
        assert "Ungültiges JSON" in result

    @pytest.mark.unit
    @patch("builtins.open", side_effect=PermissionError("Permission denied"))
    def test_save_raw_permission_error(self, mock_file, tmp_path):
        """Should return error message when file write fails"""
        # Arrange
        config_file = tmp_path / "presets.json"

        registry = WorkflowRegistry(
            config_path=str(config_file),
            workflow_dir=str(tmp_path)
        )

        content = json.dumps({"categories": {}})

        # Act
        result = registry.save_raw(content)

        # Assert
        assert "❌ Fehler" in result
        assert "Konnte workflow_presets.json nicht speichern" in result


class TestWorkflowRegistryIntegration:
    """Integration tests for WorkflowRegistry workflow"""

    @pytest.mark.unit
    def test_full_workflow_load_and_get(self, tmp_path):
        """Should load presets and retrieve files correctly"""
        # Arrange
        workflow_dir = tmp_path / "workflows"
        workflow_dir.mkdir()

        # Create workflow files
        (workflow_dir / "flux1.json").touch()
        (workflow_dir / "flux2.json").touch()
        (workflow_dir / "wan1.json").touch()

        config_file = tmp_path / "presets.json"
        presets_data = {
            "categories": {
                "flux": [
                    {"file": "flux1.json", "name": "Flux 1", "default": True},
                    {"file": "flux2.json", "name": "Flux 2"}
                ],
                "wan": [
                    {"file": "wan1.json", "name": "Wan 1"}
                ]
            }
        }

        with open(config_file, "w") as f:
            json.dump(presets_data, f)

        registry = WorkflowRegistry(
            config_path=str(config_file),
            workflow_dir=str(workflow_dir)
        )

        # Act - Get all presets
        all_presets = registry.get_presets()

        # Act - Get flux files
        flux_files = registry.get_files(category="flux")

        # Act - Get default
        default = registry.get_default(category="flux")

        # Assert
        assert len(all_presets) == 3
        assert len(flux_files) == 2
        assert default == "flux1.json"

    @pytest.mark.unit
    def test_full_workflow_save_and_read(self, tmp_path):
        """Should save and read raw config correctly"""
        # Arrange
        config_file = tmp_path / "config" / "presets.json"

        registry = WorkflowRegistry(
            config_path=str(config_file),
            workflow_dir=str(tmp_path)
        )

        new_content = json.dumps({
            "categories": {
                "test": [
                    {"file": "test.json", "name": "Test"}
                ]
            }
        }, indent=2)

        # Act - Save
        save_result = registry.save_raw(new_content)

        # Act - Read
        read_result = registry.read_raw()

        # Assert
        assert "✅ Gespeichert" in save_result
        assert "test" in read_result

        # Verify data is correct
        parsed = json.loads(read_result)
        assert "test" in parsed["categories"]
