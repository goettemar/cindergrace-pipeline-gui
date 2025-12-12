"""Unit tests for ProjectStore"""
import pytest
import os
import json
import platform
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from infrastructure.project_store import ProjectStore
from infrastructure.config_manager import ConfigManager


class TestProjectStoreInit:
    """Test ProjectStore initialization"""

    @pytest.mark.unit
    def test_init_without_config(self):
        """Should initialize with default ConfigManager"""
        # Act
        store = ProjectStore()

        # Assert
        assert store.config is not None
        assert isinstance(store.config, ConfigManager)
        assert store.PROJECT_FILE == "project.json"

    @pytest.mark.unit
    def test_init_with_config(self):
        """Should initialize with provided ConfigManager"""
        # Arrange
        mock_config = Mock(spec=ConfigManager)

        # Act
        store = ProjectStore(config=mock_config)

        # Assert
        assert store.config == mock_config


class TestProjectStoreSlugify:
    """Test ProjectStore._slugify() internal method"""

    @pytest.mark.unit
    def test_slugify_basic_name(self, tmp_path):
        """Should convert basic name to slug"""
        # Arrange
        mock_config = Mock(spec=ConfigManager)
        store = ProjectStore(config=mock_config)

        # Act
        result = store._slugify("My Project")

        # Assert
        assert result == "my-project"

    @pytest.mark.unit
    def test_slugify_special_characters(self, tmp_path):
        """Should remove special characters"""
        # Arrange
        mock_config = Mock(spec=ConfigManager)
        store = ProjectStore(config=mock_config)

        # Act
        result = store._slugify("Test!@#$%Project")

        # Assert
        assert result == "test-project"

    @pytest.mark.unit
    def test_slugify_multiple_dashes(self, tmp_path):
        """Should collapse multiple dashes"""
        # Arrange
        mock_config = Mock(spec=ConfigManager)
        store = ProjectStore(config=mock_config)

        # Act
        result = store._slugify("Test   --  Project")

        # Assert
        assert result == "test-project"

    @pytest.mark.unit
    def test_slugify_empty_string(self, tmp_path):
        """Should return 'project' for empty input"""
        # Arrange
        mock_config = Mock(spec=ConfigManager)
        store = ProjectStore(config=mock_config)

        # Act
        result = store._slugify("")

        # Assert
        assert result == "project"

    @pytest.mark.unit
    def test_slugify_only_special_chars(self, tmp_path):
        """Should return 'project' for only special chars"""
        # Arrange
        mock_config = Mock(spec=ConfigManager)
        store = ProjectStore(config=mock_config)

        # Act
        result = store._slugify("!@#$%^&*()")

        # Assert
        assert result == "project"


class TestProjectStoreComfyOutputRoot:
    """Test ProjectStore._comfy_output_root()"""

    @pytest.mark.unit
    def test_comfy_output_root_valid_path(self, tmp_path):
        """Should return ComfyUI output directory"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        comfy_root.mkdir()

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))

        store = ProjectStore(config=mock_config)

        # Act
        result = store._comfy_output_root()

        # Assert
        assert result == str(comfy_root / "output")
        assert os.path.exists(result)
        mock_config.refresh.assert_called_once()

    @pytest.mark.unit
    def test_comfy_output_root_missing_path(self):
        """Should raise FileNotFoundError for missing ComfyUI path"""
        # Arrange
        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value="/nonexistent/path")

        store = ProjectStore(config=mock_config)

        # Act & Assert
        with pytest.raises(FileNotFoundError) as exc_info:
            store._comfy_output_root()

        assert "ComfyUI-Pfad nicht gefunden" in str(exc_info.value)

    @pytest.mark.unit
    def test_comfy_output_root_empty_path(self):
        """Should raise FileNotFoundError for empty ComfyUI path"""
        # Arrange
        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value="")

        store = ProjectStore(config=mock_config)

        # Act & Assert
        with pytest.raises(FileNotFoundError) as exc_info:
            store._comfy_output_root()

        assert "(leer)" in str(exc_info.value)


class TestProjectStoreCreateProject:
    """Test ProjectStore.create_project()"""

    @pytest.mark.unit
    def test_create_project_basic(self, tmp_path):
        """Should create project with valid name"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        comfy_root.mkdir()

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))
        mock_config.set = Mock()

        store = ProjectStore(config=mock_config)

        # Act
        project = store.create_project("Test Project")

        # Assert
        assert project["name"] == "Test Project"
        assert project["slug"] == "test-project"
        assert "created_at" in project
        assert "last_opened" in project
        assert project["version"] == "0.10-beta"
        assert os.path.exists(project["path"])

        # Verify project.json was created
        project_file = Path(project["path"]) / "project.json"
        assert project_file.exists()

        # Verify content
        with open(project_file) as f:
            data = json.load(f)
        assert data["name"] == "Test Project"
        assert data["slug"] == "test-project"

        # Verify active project was set
        mock_config.set.assert_called_with("current_project", "test-project")

    @pytest.mark.unit
    def test_create_project_duplicate_name(self, tmp_path):
        """Should increment slug for duplicate project names"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        comfy_root.mkdir()

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))
        mock_config.set = Mock()

        store = ProjectStore(config=mock_config)

        # Act - Create first project
        project1 = store.create_project("Test Project")

        # Act - Create second project with same name
        project2 = store.create_project("Test Project")

        # Assert
        assert project1["slug"] == "test-project"
        assert project2["slug"] == "test-project-2"
        assert project1["path"] != project2["path"]

    @pytest.mark.unit
    def test_create_project_empty_name(self, tmp_path):
        """Should raise ValueError for empty name"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        comfy_root.mkdir()

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))

        store = ProjectStore(config=mock_config)

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            store.create_project("")

        assert "nicht leer sein" in str(exc_info.value)

    @pytest.mark.unit
    def test_create_project_whitespace_only(self, tmp_path):
        """Should raise ValueError for whitespace-only name"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        comfy_root.mkdir()

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))

        store = ProjectStore(config=mock_config)

        # Act & Assert
        with pytest.raises(ValueError):
            store.create_project("   ")


class TestProjectStoreLoadProject:
    """Test ProjectStore.load_project()"""

    @pytest.mark.unit
    def test_load_project_existing(self, tmp_path):
        """Should load existing project"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        output_dir = comfy_root / "output"
        project_dir = output_dir / "test-project"
        project_dir.mkdir(parents=True)

        project_data = {
            "name": "Test Project",
            "slug": "test-project",
            "created_at": "2024-01-01T00:00:00",
            "version": "0.10-beta"
        }

        project_file = project_dir / "project.json"
        with open(project_file, "w") as f:
            json.dump(project_data, f)

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))

        store = ProjectStore(config=mock_config)

        # Act
        project = store.load_project("test-project")

        # Assert
        assert project is not None
        assert project["name"] == "Test Project"
        assert project["slug"] == "test-project"
        assert project["path"] == str(project_dir)
        assert project["created_at"] == "2024-01-01T00:00:00"

    @pytest.mark.unit
    def test_load_project_nonexistent(self, tmp_path):
        """Should return None for non-existent project"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        comfy_root.mkdir()

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))

        store = ProjectStore(config=mock_config)

        # Act
        project = store.load_project("nonexistent")

        # Assert
        assert project is None


class TestProjectStoreListProjects:
    """Test ProjectStore.list_projects()"""

    @pytest.mark.unit
    def test_list_projects_multiple(self, tmp_path):
        """Should list all discovered projects"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        output_dir = comfy_root / "output"
        output_dir.mkdir(parents=True)

        # Create multiple projects
        for i in range(3):
            project_dir = output_dir / f"project-{i}"
            project_dir.mkdir()

            project_data = {
                "name": f"Project {i}",
                "slug": f"project-{i}",
                "created_at": "2024-01-01T00:00:00"
            }

            with open(project_dir / "project.json", "w") as f:
                json.dump(project_data, f)

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))

        store = ProjectStore(config=mock_config)

        # Act
        projects = store.list_projects()

        # Assert
        assert len(projects) == 3
        assert all("slug" in p for p in projects)
        assert all("name" in p for p in projects)
        assert all("path" in p for p in projects)

    @pytest.mark.unit
    def test_list_projects_empty(self, tmp_path):
        """Should return empty list when no projects exist"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        output_dir = comfy_root / "output"
        output_dir.mkdir(parents=True)

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))

        store = ProjectStore(config=mock_config)

        # Act
        projects = store.list_projects()

        # Assert
        assert projects == []

    @pytest.mark.unit
    def test_list_projects_invalid_comfy_path(self):
        """Should return empty list when ComfyUI path invalid"""
        # Arrange
        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value="/nonexistent")

        store = ProjectStore(config=mock_config)

        # Act
        projects = store.list_projects()

        # Assert
        assert projects == []

    @pytest.mark.unit
    def test_list_projects_skips_invalid_dirs(self, tmp_path):
        """Should skip directories without project.json"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        output_dir = comfy_root / "output"
        output_dir.mkdir(parents=True)

        # Create valid project
        valid_dir = output_dir / "valid-project"
        valid_dir.mkdir()
        with open(valid_dir / "project.json", "w") as f:
            json.dump({"name": "Valid", "slug": "valid-project"}, f)

        # Create invalid directories
        (output_dir / "no-config").mkdir()  # No project.json
        (output_dir / "just-a-file.txt").touch()  # Not a directory

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))

        store = ProjectStore(config=mock_config)

        # Act
        projects = store.list_projects()

        # Assert
        assert len(projects) == 1
        assert projects[0]["slug"] == "valid-project"


class TestProjectStoreSetActiveProject:
    """Test ProjectStore.set_active_project()"""

    @pytest.mark.unit
    def test_set_active_project_existing(self, tmp_path):
        """Should set active project and update last_opened"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        output_dir = comfy_root / "output"
        project_dir = output_dir / "test-project"
        project_dir.mkdir(parents=True)

        project_data = {
            "name": "Test Project",
            "slug": "test-project",
            "created_at": "2024-01-01T00:00:00"
        }

        with open(project_dir / "project.json", "w") as f:
            json.dump(project_data, f)

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))
        mock_config.set = Mock()

        store = ProjectStore(config=mock_config)

        # Act
        project = store.set_active_project("test-project")

        # Assert
        assert project is not None
        assert project["slug"] == "test-project"
        assert "last_opened" in project
        mock_config.set.assert_called_with("current_project", "test-project")

        # Verify last_opened was written to file
        with open(project_dir / "project.json") as f:
            updated_data = json.load(f)
        assert "last_opened" in updated_data

    @pytest.mark.unit
    def test_set_active_project_nonexistent(self, tmp_path):
        """Should return None for non-existent project"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        comfy_root.mkdir()

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))
        mock_config.set = Mock()

        store = ProjectStore(config=mock_config)

        # Act
        project = store.set_active_project("nonexistent")

        # Assert
        assert project is None
        mock_config.set.assert_not_called()


class TestProjectStoreGetActiveProject:
    """Test ProjectStore.get_active_project()"""

    @pytest.mark.unit
    def test_get_active_project_when_set(self, tmp_path):
        """Should return active project when set"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        output_dir = comfy_root / "output"
        project_dir = output_dir / "test-project"
        project_dir.mkdir(parents=True)

        project_data = {
            "name": "Test Project",
            "slug": "test-project"
        }

        with open(project_dir / "project.json", "w") as f:
            json.dump(project_data, f)

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(side_effect=lambda key, default=None: {
            "comfy_root": str(comfy_root),
            "current_project": "test-project"
        }.get(key, default))

        store = ProjectStore(config=mock_config)

        # Act
        project = store.get_active_project()

        # Assert
        assert project is not None
        assert project["slug"] == "test-project"

    @pytest.mark.unit
    def test_get_active_project_when_not_set(self, tmp_path):
        """Should return None when no active project"""
        # Arrange
        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=None)

        store = ProjectStore(config=mock_config)

        # Act
        project = store.get_active_project()

        # Assert
        assert project is None

    @pytest.mark.unit
    def test_get_active_project_with_refresh(self, tmp_path):
        """Should refresh config when refresh=True"""
        # Arrange
        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=None)

        store = ProjectStore(config=mock_config)

        # Act
        store.get_active_project(refresh=True)

        # Assert
        mock_config.refresh.assert_called_once()


class TestProjectStoreEnsureDir:
    """Test ProjectStore.ensure_dir()"""

    @pytest.mark.unit
    def test_ensure_dir_creates_directory(self, tmp_path):
        """Should create subdirectory in project"""
        # Arrange
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        project = {
            "path": str(project_dir),
            "slug": "test-project"
        }

        mock_config = Mock(spec=ConfigManager)
        store = ProjectStore(config=mock_config)

        # Act
        result = store.ensure_dir(project, "keyframes")

        # Assert
        expected_path = str(project_dir / "keyframes")
        assert result == expected_path
        assert os.path.exists(expected_path)

    @pytest.mark.unit
    def test_ensure_dir_nested_path(self, tmp_path):
        """Should create nested subdirectories"""
        # Arrange
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        project = {
            "path": str(project_dir),
            "slug": "test-project"
        }

        mock_config = Mock(spec=ConfigManager)
        store = ProjectStore(config=mock_config)

        # Act
        result = store.ensure_dir(project, "video", "_startframes")

        # Assert
        expected_path = str(project_dir / "video" / "_startframes")
        assert result == expected_path
        assert os.path.exists(expected_path)

    @pytest.mark.unit
    def test_ensure_dir_no_project(self):
        """Should raise RuntimeError when no project"""
        # Arrange
        mock_config = Mock(spec=ConfigManager)
        store = ProjectStore(config=mock_config)

        # Act & Assert
        with pytest.raises(RuntimeError) as exc_info:
            store.ensure_dir(None, "keyframes")

        assert "Kein aktives Projekt" in str(exc_info.value)


class TestProjectStoreProjectPath:
    """Test ProjectStore.project_path()"""

    @pytest.mark.unit
    def test_project_path_with_parts(self, tmp_path):
        """Should return path with joined parts"""
        # Arrange
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        project = {
            "path": str(project_dir),
            "slug": "test-project"
        }

        mock_config = Mock(spec=ConfigManager)
        store = ProjectStore(config=mock_config)

        # Act
        result = store.project_path(project, "keyframes", "shot-001.png")

        # Assert
        expected_path = str(project_dir / "keyframes" / "shot-001.png")
        assert result == expected_path

    @pytest.mark.unit
    def test_project_path_without_parts(self, tmp_path):
        """Should return project path when no parts given"""
        # Arrange
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        project = {
            "path": str(project_dir),
            "slug": "test-project"
        }

        mock_config = Mock(spec=ConfigManager)
        store = ProjectStore(config=mock_config)

        # Act
        result = store.project_path(project)

        # Assert
        assert result == str(project_dir)

    @pytest.mark.unit
    def test_project_path_no_project(self):
        """Should raise RuntimeError when no project"""
        # Arrange
        mock_config = Mock(spec=ConfigManager)
        store = ProjectStore(config=mock_config)

        # Act & Assert
        with pytest.raises(RuntimeError) as exc_info:
            store.project_path(None, "keyframes")

        assert "Kein aktives Projekt" in str(exc_info.value)


class TestProjectStoreComfyOutputDir:
    """Test ProjectStore.comfy_output_dir()"""

    @pytest.mark.unit
    def test_comfy_output_dir_valid(self, tmp_path):
        """Should return validated ComfyUI output directory"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        comfy_root.mkdir()

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))

        store = ProjectStore(config=mock_config)

        # Act
        result = store.comfy_output_dir()

        # Assert
        expected_path = str(comfy_root / "output")
        assert result == expected_path
        assert os.path.exists(expected_path)


class TestProjectStoreWriteProjectFile:
    """Test ProjectStore._write_project_file() file locking"""

    @pytest.mark.unit
    @pytest.mark.skipif(platform.system() == "Windows", reason="fcntl not available on Windows")
    def test_write_project_file_with_locking(self, tmp_path):
        """Should write project file with file locking (Linux/Mac)"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        output_dir = comfy_root / "output"
        project_dir = output_dir / "test-project"
        project_dir.mkdir(parents=True)

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))

        store = ProjectStore(config=mock_config)

        project = {
            "path": str(project_dir),
            "name": "Test Project",
            "slug": "test-project",
            "created_at": "2024-01-01T00:00:00"
        }

        # Act
        store._write_project_file(project)

        # Assert - File should exist and contain correct data
        project_file = project_dir / "project.json"
        assert project_file.exists()

        with open(project_file) as f:
            data = json.load(f)

        assert data["name"] == "Test Project"
        assert data["slug"] == "test-project"
        assert "path" not in data  # path should be excluded

    @pytest.mark.unit
    def test_write_project_file_excludes_path_key(self, tmp_path):
        """Should exclude 'path' key from written JSON"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        output_dir = comfy_root / "output"
        project_dir = output_dir / "test-project"
        project_dir.mkdir(parents=True)

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))

        store = ProjectStore(config=mock_config)

        project = {
            "path": str(project_dir),
            "name": "Test Project",
            "slug": "test-project"
        }

        # Act
        store._write_project_file(project)

        # Assert
        with open(project_dir / "project.json") as f:
            data = json.load(f)

        assert "path" not in data
        assert "name" in data
        assert "slug" in data


class TestProjectStoreIntegration:
    """Integration tests for ProjectStore workflow"""

    @pytest.mark.unit
    def test_full_workflow_create_load_list(self, tmp_path):
        """Should create, load, and list projects correctly"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        comfy_root.mkdir()

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))
        mock_config.set = Mock()

        store = ProjectStore(config=mock_config)

        # Act - Create projects
        project1 = store.create_project("First Project")
        project2 = store.create_project("Second Project")

        # Act - List projects
        all_projects = store.list_projects()

        # Act - Load specific project
        loaded = store.load_project("first-project")

        # Assert
        assert len(all_projects) == 2
        assert loaded["name"] == "First Project"
        assert os.path.exists(project1["path"])
        assert os.path.exists(project2["path"])

    @pytest.mark.unit
    def test_full_workflow_with_subdirectories(self, tmp_path):
        """Should create project and manage subdirectories"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        comfy_root.mkdir()

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))
        mock_config.set = Mock()

        store = ProjectStore(config=mock_config)

        # Act - Create project
        project = store.create_project("Video Project")

        # Act - Create subdirectories
        keyframes_dir = store.ensure_dir(project, "keyframes")
        video_dir = store.ensure_dir(project, "video", "_startframes")

        # Act - Get project paths
        path1 = store.project_path(project, "keyframes")
        path2 = store.project_path(project, "video")

        # Assert
        assert os.path.exists(keyframes_dir)
        assert os.path.exists(video_dir)
        assert path1 == str(Path(project["path"]) / "keyframes")
        assert path2 == str(Path(project["path"]) / "video")
