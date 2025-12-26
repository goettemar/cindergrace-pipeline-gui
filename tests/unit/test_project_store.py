"""Unit tests for ProjectStore (SQLite-based)"""
import pytest
import os
import sqlite3
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime

from infrastructure.project_store import ProjectStore, get_db_path
from infrastructure.config_manager import ConfigManager


class TestProjectStoreInit:
    """Test ProjectStore initialization"""

    @pytest.mark.unit
    def test_init_without_config(self, tmp_path, monkeypatch):
        """Should initialize with default ConfigManager"""
        # Arrange - Use temp db path
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

        # Act
        store = ProjectStore()

        # Assert
        assert store.config is not None
        assert isinstance(store.config, ConfigManager)
        assert store.db_path == test_db
        assert os.path.exists(test_db)

    @pytest.mark.unit
    def test_init_with_config(self, tmp_path, monkeypatch):
        """Should initialize with provided ConfigManager"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)
        mock_config = Mock(spec=ConfigManager)

        # Act
        store = ProjectStore(config=mock_config)

        # Assert
        assert store.config == mock_config

    @pytest.mark.unit
    def test_init_creates_tables(self, tmp_path, monkeypatch):
        """Should create projects table on init"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)
        mock_config = Mock(spec=ConfigManager)

        # Act
        store = ProjectStore(config=mock_config)

        # Assert - Check table exists
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='projects'")
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == "projects"


class TestProjectStoreSlugify:
    """Test ProjectStore._slugify() internal method"""

    @pytest.mark.unit
    def test_slugify_basic_name(self, tmp_path, monkeypatch):
        """Should convert basic name to slug"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)
        mock_config = Mock(spec=ConfigManager)
        store = ProjectStore(config=mock_config)

        # Act
        result = store._slugify("My Project")

        # Assert
        assert result == "my-project"

    @pytest.mark.unit
    def test_slugify_special_characters(self, tmp_path, monkeypatch):
        """Should remove special characters"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)
        mock_config = Mock(spec=ConfigManager)
        store = ProjectStore(config=mock_config)

        # Act
        result = store._slugify("Test!@#$%Project")

        # Assert
        assert result == "test-project"

    @pytest.mark.unit
    def test_slugify_multiple_dashes(self, tmp_path, monkeypatch):
        """Should collapse multiple dashes"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)
        mock_config = Mock(spec=ConfigManager)
        store = ProjectStore(config=mock_config)

        # Act
        result = store._slugify("Test   --  Project")

        # Assert
        assert result == "test-project"

    @pytest.mark.unit
    def test_slugify_empty_string(self, tmp_path, monkeypatch):
        """Should return 'project' for empty input"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)
        mock_config = Mock(spec=ConfigManager)
        store = ProjectStore(config=mock_config)

        # Act
        result = store._slugify("")

        # Assert
        assert result == "project"

    @pytest.mark.unit
    def test_slugify_only_special_chars(self, tmp_path, monkeypatch):
        """Should return 'project' for only special chars"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)
        mock_config = Mock(spec=ConfigManager)
        store = ProjectStore(config=mock_config)

        # Act
        result = store._slugify("!@#$%^&*()")

        # Assert
        assert result == "project"


class TestProjectStoreComfyOutputRoot:
    """Test ProjectStore._comfy_output_root()"""

    @pytest.mark.unit
    def test_comfy_output_root_valid_path(self, tmp_path, monkeypatch):
        """Should return ComfyUI output directory"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

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
    def test_comfy_output_root_missing_path(self, tmp_path, monkeypatch):
        """Should raise FileNotFoundError for missing ComfyUI path"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value="/nonexistent/path")

        store = ProjectStore(config=mock_config)

        # Act & Assert
        with pytest.raises(FileNotFoundError) as exc_info:
            store._comfy_output_root()

        assert "ComfyUI-Pfad nicht gefunden" in str(exc_info.value)

    @pytest.mark.unit
    def test_comfy_output_root_empty_path(self, tmp_path, monkeypatch):
        """Should raise FileNotFoundError for empty ComfyUI path"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

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
    def test_create_project_basic(self, tmp_path, monkeypatch):
        """Should create project with valid name"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

        comfy_root = tmp_path / "comfyui"
        comfy_root.mkdir()

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))

        store = ProjectStore(config=mock_config)

        # Act
        project = store.create_project("Test Project")

        # Assert
        assert project["name"] == "Test Project"
        assert project["slug"] == "test-project"
        assert "created_at" in project
        assert "last_opened" in project
        assert project["version"] == "1.0"
        assert os.path.exists(project["path"])

        # Verify stored in database
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name, slug, is_active FROM projects WHERE slug = ?", ("test-project",))
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "Test Project"
        assert row[1] == "test-project"
        assert row[2] == 1  # is_active

    @pytest.mark.unit
    def test_create_project_duplicate_name(self, tmp_path, monkeypatch):
        """Should increment slug for duplicate project names"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

        comfy_root = tmp_path / "comfyui"
        comfy_root.mkdir()

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))

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
    def test_create_project_empty_name(self, tmp_path, monkeypatch):
        """Should raise ValueError for empty name"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

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
    def test_create_project_whitespace_only(self, tmp_path, monkeypatch):
        """Should raise ValueError for whitespace-only name"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

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
    def test_load_project_existing(self, tmp_path, monkeypatch):
        """Should load existing project from database"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

        comfy_root = tmp_path / "comfyui"
        comfy_root.mkdir()

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))

        store = ProjectStore(config=mock_config)

        # Create project first
        created = store.create_project("Test Project")

        # Act
        project = store.load_project("test-project")

        # Assert
        assert project is not None
        assert project["name"] == "Test Project"
        assert project["slug"] == "test-project"
        assert project["path"] == created["path"]

    @pytest.mark.unit
    def test_load_project_nonexistent(self, tmp_path, monkeypatch):
        """Should return None for non-existent project"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

        mock_config = Mock(spec=ConfigManager)
        store = ProjectStore(config=mock_config)

        # Act
        project = store.load_project("nonexistent")

        # Assert
        assert project is None


class TestProjectStoreListProjects:
    """Test ProjectStore.list_projects()"""

    @pytest.mark.unit
    def test_list_projects_multiple(self, tmp_path, monkeypatch):
        """Should list all projects from database"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

        comfy_root = tmp_path / "comfyui"
        comfy_root.mkdir()

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))

        store = ProjectStore(config=mock_config)

        # Create multiple projects
        for i in range(3):
            store.create_project(f"Project {i}")

        # Act
        projects = store.list_projects()

        # Assert
        assert len(projects) == 3
        assert all("slug" in p for p in projects)
        assert all("name" in p for p in projects)
        assert all("path" in p for p in projects)

    @pytest.mark.unit
    def test_list_projects_empty(self, tmp_path, monkeypatch):
        """Should return empty list when no projects exist"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

        mock_config = Mock(spec=ConfigManager)
        store = ProjectStore(config=mock_config)

        # Act
        projects = store.list_projects()

        # Assert
        assert projects == []

    @pytest.mark.unit
    def test_list_projects_ordered_by_last_opened(self, tmp_path, monkeypatch):
        """Should return projects ordered by last_opened DESC"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

        comfy_root = tmp_path / "comfyui"
        comfy_root.mkdir()

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))

        store = ProjectStore(config=mock_config)

        # Create projects
        store.create_project("First")
        store.create_project("Second")
        store.create_project("Third")

        # Set first project as active (updates last_opened)
        store.set_active_project("first")

        # Act
        projects = store.list_projects()

        # Assert - Most recently opened should be first
        assert projects[0]["slug"] == "first"


class TestProjectStoreSetActiveProject:
    """Test ProjectStore.set_active_project()"""

    @pytest.mark.unit
    def test_set_active_project_existing(self, tmp_path, monkeypatch):
        """Should set active project and update last_opened"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

        comfy_root = tmp_path / "comfyui"
        comfy_root.mkdir()

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))

        store = ProjectStore(config=mock_config)

        # Create two projects
        store.create_project("First")
        store.create_project("Second")  # This becomes active

        # Act - Switch to first project
        project = store.set_active_project("first")

        # Assert
        assert project is not None
        assert project["slug"] == "first"

        # Verify in database
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT slug FROM projects WHERE is_active = 1")
        row = cursor.fetchone()
        conn.close()

        assert row[0] == "first"

    @pytest.mark.unit
    def test_set_active_project_deactivates_others(self, tmp_path, monkeypatch):
        """Should deactivate other projects when setting active"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

        comfy_root = tmp_path / "comfyui"
        comfy_root.mkdir()

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))

        store = ProjectStore(config=mock_config)

        # Create projects
        store.create_project("First")
        store.create_project("Second")

        # Act
        store.set_active_project("first")

        # Assert - Only one should be active
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM projects WHERE is_active = 1")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 1

    @pytest.mark.unit
    def test_set_active_project_nonexistent(self, tmp_path, monkeypatch):
        """Should return None for non-existent project"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

        mock_config = Mock(spec=ConfigManager)
        store = ProjectStore(config=mock_config)

        # Act
        project = store.set_active_project("nonexistent")

        # Assert
        assert project is None


class TestProjectStoreGetActiveProject:
    """Test ProjectStore.get_active_project()"""

    @pytest.mark.unit
    def test_get_active_project_when_set(self, tmp_path, monkeypatch):
        """Should return active project from database"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

        comfy_root = tmp_path / "comfyui"
        comfy_root.mkdir()

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))

        store = ProjectStore(config=mock_config)

        # Create and set active project
        store.create_project("Test Project")

        # Act
        project = store.get_active_project()

        # Assert
        assert project is not None
        assert project["slug"] == "test-project"

    @pytest.mark.unit
    def test_get_active_project_when_not_set(self, tmp_path, monkeypatch):
        """Should return None when no active project"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

        mock_config = Mock(spec=ConfigManager)
        store = ProjectStore(config=mock_config)

        # Act
        project = store.get_active_project()

        # Assert
        assert project is None


class TestProjectStoreDeleteProject:
    """Test ProjectStore.delete_project()"""

    @pytest.mark.unit
    def test_delete_project_existing(self, tmp_path, monkeypatch):
        """Should delete project from database and filesystem"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

        comfy_root = tmp_path / "comfyui"
        comfy_root.mkdir()

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))

        store = ProjectStore(config=mock_config)

        # Create project
        project = store.create_project("Test Project")
        project_path = project["path"]

        # Verify it exists
        assert os.path.exists(project_path)

        # Act
        result = store.delete_project("test-project")

        # Assert
        assert result is True

        # Verify removed from database
        loaded = store.load_project("test-project")
        assert loaded is None

        # Verify directory removed
        assert not os.path.exists(project_path)

    @pytest.mark.unit
    def test_delete_project_nonexistent(self, tmp_path, monkeypatch):
        """Should return False for non-existent project"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

        mock_config = Mock(spec=ConfigManager)
        store = ProjectStore(config=mock_config)

        # Act
        result = store.delete_project("nonexistent")

        # Assert
        assert result is False

    @pytest.mark.unit
    def test_delete_project_empty_slug(self, tmp_path, monkeypatch):
        """Should return False for empty slug"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

        mock_config = Mock(spec=ConfigManager)
        store = ProjectStore(config=mock_config)

        # Act
        result = store.delete_project("")

        # Assert
        assert result is False


class TestProjectStoreUpdateProject:
    """Test ProjectStore.update_project()"""

    @pytest.mark.unit
    def test_update_project_name(self, tmp_path, monkeypatch):
        """Should update project name"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

        comfy_root = tmp_path / "comfyui"
        comfy_root.mkdir()

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))

        store = ProjectStore(config=mock_config)
        store.create_project("Original Name")

        # Act
        project = store.update_project("original-name", name="New Name")

        # Assert
        assert project is not None
        assert project["name"] == "New Name"
        assert project["slug"] == "original-name"  # Slug unchanged

    @pytest.mark.unit
    def test_update_project_ignores_invalid_fields(self, tmp_path, monkeypatch):
        """Should ignore invalid field updates"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

        comfy_root = tmp_path / "comfyui"
        comfy_root.mkdir()

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))

        store = ProjectStore(config=mock_config)
        store.create_project("Test")

        # Act - Try to update invalid field
        project = store.update_project("test", invalid_field="value")

        # Assert - Should not crash, just return project
        assert project is not None


class TestProjectStoreEnsureDir:
    """Test ProjectStore.ensure_dir()"""

    @pytest.mark.unit
    def test_ensure_dir_creates_directory(self, tmp_path, monkeypatch):
        """Should create subdirectory in project"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

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
    def test_ensure_dir_nested_path(self, tmp_path, monkeypatch):
        """Should create nested subdirectories"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

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
    def test_ensure_dir_no_project(self, tmp_path, monkeypatch):
        """Should raise RuntimeError when no project"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

        mock_config = Mock(spec=ConfigManager)
        store = ProjectStore(config=mock_config)

        # Act & Assert
        with pytest.raises(RuntimeError) as exc_info:
            store.ensure_dir(None, "keyframes")

        assert "Kein aktives Projekt" in str(exc_info.value)


class TestProjectStoreProjectPath:
    """Test ProjectStore.project_path()"""

    @pytest.mark.unit
    def test_project_path_with_parts(self, tmp_path, monkeypatch):
        """Should return path with joined parts"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

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
    def test_project_path_without_parts(self, tmp_path, monkeypatch):
        """Should return project path when no parts given"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

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
    def test_project_path_no_project(self, tmp_path, monkeypatch):
        """Should raise RuntimeError when no project"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

        mock_config = Mock(spec=ConfigManager)
        store = ProjectStore(config=mock_config)

        # Act & Assert
        with pytest.raises(RuntimeError) as exc_info:
            store.project_path(None, "keyframes")

        assert "Kein aktives Projekt" in str(exc_info.value)


class TestProjectStoreComfyOutputDir:
    """Test ProjectStore.comfy_output_dir()"""

    @pytest.mark.unit
    def test_comfy_output_dir_valid(self, tmp_path, monkeypatch):
        """Should return validated ComfyUI output directory"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

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


class TestProjectStoreImportFromFilesystem:
    """Test ProjectStore.import_from_filesystem()"""

    @pytest.mark.unit
    def test_import_from_filesystem_with_project_json(self, tmp_path, monkeypatch):
        """Should import projects with project.json files"""
        import json

        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

        comfy_root = tmp_path / "comfyui"
        output_dir = comfy_root / "output"
        output_dir.mkdir(parents=True)

        # Create project with project.json
        project_dir = output_dir / "old-project"
        project_dir.mkdir()
        with open(project_dir / "project.json", "w") as f:
            json.dump({
                "name": "Old Project",
                "created_at": "2024-01-01T00:00:00",
                "version": "0.9"
            }, f)

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))

        store = ProjectStore(config=mock_config)

        # Act
        imported = store.import_from_filesystem()

        # Assert
        assert imported == 1

        # Verify in database
        project = store.load_project("old-project")
        assert project is not None
        assert project["name"] == "Old Project"

    @pytest.mark.unit
    def test_import_from_filesystem_skips_existing(self, tmp_path, monkeypatch):
        """Should skip projects already in database"""
        import json

        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

        comfy_root = tmp_path / "comfyui"
        output_dir = comfy_root / "output"
        output_dir.mkdir(parents=True)

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))

        store = ProjectStore(config=mock_config)

        # Create project in database
        store.create_project("Existing Project")

        # Create same project on filesystem
        project_dir = output_dir / "existing-project"
        # Note: project_dir already created by create_project
        with open(project_dir / "project.json", "w") as f:
            json.dump({"name": "Existing Project"}, f)

        # Act
        imported = store.import_from_filesystem()

        # Assert
        assert imported == 0  # Should skip existing

    @pytest.mark.unit
    def test_import_from_filesystem_invalid_path(self, tmp_path, monkeypatch):
        """Should return 0 when ComfyUI path invalid"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value="/nonexistent")

        store = ProjectStore(config=mock_config)

        # Act
        imported = store.import_from_filesystem()

        # Assert
        assert imported == 0


class TestProjectStoreIntegration:
    """Integration tests for ProjectStore workflow"""

    @pytest.mark.unit
    def test_full_workflow_create_load_list(self, tmp_path, monkeypatch):
        """Should create, load, and list projects correctly"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

        comfy_root = tmp_path / "comfyui"
        comfy_root.mkdir()

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))

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
    def test_full_workflow_with_subdirectories(self, tmp_path, monkeypatch):
        """Should create project and manage subdirectories"""
        # Arrange
        test_db = str(tmp_path / "test.db")
        monkeypatch.setattr("infrastructure.project_store.get_db_path", lambda: test_db)

        comfy_root = tmp_path / "comfyui"
        comfy_root.mkdir()

        mock_config = Mock(spec=ConfigManager)
        mock_config.refresh = Mock()
        mock_config.get = Mock(return_value=str(comfy_root))

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
