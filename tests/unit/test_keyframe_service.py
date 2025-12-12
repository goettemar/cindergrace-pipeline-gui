"""Unit tests for KeyframeService"""
import pytest
import os
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from services.keyframe_service import KeyframeService, KeyframeGenerationService
from domain.models import Storyboard, Shot
from infrastructure.config_manager import ConfigManager
from infrastructure.project_store import ProjectStore


class TestKeyframeServicePrepareCheckpoint:
    """Test KeyframeService.prepare_checkpoint()"""

    @pytest.mark.unit
    def test_prepare_checkpoint_basic(self):
        """Should create valid checkpoint structure"""
        # Arrange
        mock_store = Mock(spec=ProjectStore)
        mock_config = Mock(spec=ConfigManager)
        mock_registry = Mock()

        service = KeyframeService(mock_store, mock_config, mock_registry)

        storyboard = Storyboard(
            project="Test Project",
            shots=[Shot(shot_id="001", filename_base="test", prompt="test prompt")],
            raw={"storyboard_file": "test_storyboard.json"}
        )

        # Act
        checkpoint = service.prepare_checkpoint(
            storyboard=storyboard,
            workflow_file="test_workflow.json",
            variants_per_shot=4,
            base_seed=2000
        )

        # Assert
        assert checkpoint["storyboard_file"] == "test_storyboard.json"
        assert checkpoint["workflow_file"] == "test_workflow.json"
        assert checkpoint["variants_per_shot"] == 4
        assert checkpoint["base_seed"] == 2000
        assert checkpoint["completed_shots"] == []
        assert checkpoint["current_shot"] is None
        assert checkpoint["total_images_generated"] == 0
        assert checkpoint["status"] == "running"
        assert "started_at" in checkpoint

    @pytest.mark.unit
    def test_prepare_checkpoint_converts_types(self):
        """Should convert variants_per_shot and base_seed to int"""
        # Arrange
        mock_store = Mock(spec=ProjectStore)
        mock_config = Mock(spec=ConfigManager)
        mock_registry = Mock()

        service = KeyframeService(mock_store, mock_config, mock_registry)

        storyboard = Storyboard(project="Test", shots=[], raw={})

        # Act - Pass floats/strings
        checkpoint = service.prepare_checkpoint(
            storyboard=storyboard,
            workflow_file="test.json",
            variants_per_shot="3",  # String
            base_seed=1500.5  # Float
        )

        # Assert - Should be converted to int
        assert checkpoint["variants_per_shot"] == 3
        assert isinstance(checkpoint["variants_per_shot"], int)
        assert checkpoint["base_seed"] == 1500
        assert isinstance(checkpoint["base_seed"], int)


class TestKeyframeGenerationServiceInit:
    """Test KeyframeGenerationService initialization"""

    @pytest.mark.unit
    def test_initialization_without_api(self):
        """Should initialize without ComfyUI API"""
        # Arrange
        mock_config = Mock(spec=ConfigManager)
        mock_store = Mock(spec=ProjectStore)

        # Act
        service = KeyframeGenerationService(
            config=mock_config,
            project_store=mock_store,
            comfy_api=None
        )

        # Assert
        assert service.config == mock_config
        assert service.project_store == mock_store
        assert service.api is None
        assert service.is_running is False
        assert service.stop_requested is False

    @pytest.mark.unit
    def test_initialization_with_api(self, mock_comfy_api):
        """Should initialize with ComfyUI API"""
        # Arrange
        mock_config = Mock(spec=ConfigManager)
        mock_store = Mock(spec=ProjectStore)

        # Act
        service = KeyframeGenerationService(
            config=mock_config,
            project_store=mock_store,
            comfy_api=mock_comfy_api
        )

        # Assert
        assert service.api == mock_comfy_api


class TestKeyframeGenerationServiceStopGeneration:
    """Test KeyframeGenerationService.stop_generation()"""

    @pytest.mark.unit
    def test_stop_generation_when_not_running(self):
        """Should return message when not running"""
        # Arrange
        mock_config = Mock(spec=ConfigManager)
        mock_store = Mock(spec=ProjectStore)

        service = KeyframeGenerationService(mock_config, mock_store)
        service.is_running = False

        # Act
        status, message = service.stop_generation()

        # Assert
        assert "ℹ️" in status or "Kein Lauf aktiv" in status
        assert "Kein aktiver" in message or "aktiv" in message.lower()
        assert service.stop_requested is False

    @pytest.mark.unit
    def test_stop_generation_when_running(self):
        """Should set stop_requested flag when running"""
        # Arrange
        mock_config = Mock(spec=ConfigManager)
        mock_store = Mock(spec=ProjectStore)

        service = KeyframeGenerationService(mock_config, mock_store)
        service.is_running = True

        # Act
        status, message = service.stop_generation()

        # Assert
        assert "info" in status.lower() or "stop" in status.lower()
        assert service.stop_requested is True


class TestKeyframeGenerationServiceFormatProgress:
    """Test KeyframeGenerationService._format_progress()"""

    @pytest.mark.unit
    def test_format_progress_basic(self):
        """Should format progress markdown"""
        # Arrange
        mock_config = Mock(spec=ConfigManager)
        mock_store = Mock(spec=ProjectStore)

        service = KeyframeGenerationService(mock_config, mock_store)

        checkpoint = {
            "completed_shots": ["001", "002"],
            "total_images_generated": 8,
            "status": "running"
        }

        # Act
        result = service._format_progress(checkpoint, total_shots=5)

        # Assert
        assert "2/5" in result  # Completed shots
        assert "8" in result    # Total images
        assert isinstance(result, str)

    @pytest.mark.unit
    def test_format_progress_completed_status(self):
        """Should show completed status"""
        # Arrange
        mock_config = Mock(spec=ConfigManager)
        mock_store = Mock(spec=ProjectStore)

        service = KeyframeGenerationService(mock_config, mock_store)

        checkpoint = {
            "completed_shots": ["001", "002", "003"],
            "total_images_generated": 12,
            "status": "completed"
        }

        # Act
        result = service._format_progress(checkpoint, total_shots=3)

        # Assert
        assert "3/3" in result
        assert "12" in result


class TestKeyframeGenerationServiceSaveCheckpoint:
    """Test KeyframeGenerationService._save_checkpoint()"""

    @pytest.mark.unit
    def test_save_checkpoint_success(self, tmp_path):
        """Should save checkpoint to project directory"""
        # Arrange
        mock_config = Mock(spec=ConfigManager)
        mock_store = Mock(spec=ProjectStore)

        project_dir = tmp_path / "project"
        checkpoints_dir = project_dir / "checkpoints"
        checkpoints_dir.mkdir(parents=True)

        mock_store.ensure_dir.return_value = str(checkpoints_dir)

        service = KeyframeGenerationService(mock_config, mock_store)

        checkpoint = {
            "storyboard_file": "test_storyboard.json",
            "workflow_file": "test_workflow.json",
            "variants_per_shot": 4,
            "base_seed": 2000,
            "completed_shots": ["001"],
            "total_images_generated": 4,
            "status": "running"
        }

        project = {"path": str(project_dir)}
        storyboard_file = "test_storyboard"

        # Act
        service._save_checkpoint(checkpoint, storyboard_file, project)

        # Assert - Filename format is "checkpoint_{storyboard_file}"
        checkpoint_file = checkpoints_dir / "checkpoint_test_storyboard"
        assert checkpoint_file.exists()

        # Verify content
        with open(checkpoint_file) as f:
            saved = json.load(f)
        assert saved["completed_shots"] == ["001"]
        assert saved["total_images_generated"] == 4


class TestKeyframeGenerationServiceCopyImages:
    """Test KeyframeGenerationService._copy_generated_images()"""

    @pytest.mark.unit
    def test_copy_generated_images_success(self, tmp_path, create_test_image):
        """Should copy images from ComfyUI output to project keyframes"""
        # Arrange
        mock_config = Mock(spec=ConfigManager)
        mock_store = Mock(spec=ProjectStore)

        # Create source directory (ComfyUI output)
        comfy_output_dir = tmp_path / "comfyui" / "output"
        comfy_output_dir.mkdir(parents=True)

        # Create destination directory (project keyframes)
        project_keyframes_dir = tmp_path / "project" / "keyframes"
        project_keyframes_dir.mkdir(parents=True)

        # Mock comfy_output_dir method
        mock_store.comfy_output_dir = Mock(return_value=str(comfy_output_dir))

        service = KeyframeGenerationService(mock_config, mock_store)

        # Create test images in ComfyUI output
        test_image_1 = comfy_output_dir / "test-shot_v1_00001_.png"
        test_image_2 = comfy_output_dir / "test-shot_v1_00002_.png"
        create_test_image(str(test_image_1))
        create_test_image(str(test_image_2))

        # Act
        result = service._copy_generated_images(
            variant_name="test-shot_v1",  # Correct parameter name
            output_dir=str(project_keyframes_dir),
            api_result={}  # Required parameter
        )

        # Assert
        assert len(result) == 2
        assert (project_keyframes_dir / "test-shot_v1_00001_.png").exists()
        assert (project_keyframes_dir / "test-shot_v1_00002_.png").exists()

    @pytest.mark.unit
    def test_copy_generated_images_no_matches(self, tmp_path):
        """Should return empty list when no images found"""
        # Arrange
        mock_config = Mock(spec=ConfigManager)
        mock_store = Mock(spec=ProjectStore)

        comfy_output_dir = tmp_path / "comfyui" / "output"
        comfy_output_dir.mkdir(parents=True)

        project_keyframes_dir = tmp_path / "project" / "keyframes"
        project_keyframes_dir.mkdir(parents=True)

        # Mock comfy_output_dir method
        mock_store.comfy_output_dir = Mock(return_value=str(comfy_output_dir))

        service = KeyframeGenerationService(mock_config, mock_store)

        # Act - No images in ComfyUI output
        result = service._copy_generated_images(
            variant_name="nonexistent",  # Correct parameter name
            output_dir=str(project_keyframes_dir),
            api_result={}  # Required parameter
        )

        # Assert
        assert result == []


class TestKeyframeGenerationServiceRunGeneration:
    """Test KeyframeGenerationService.run_generation() - Basic scenarios"""

    @pytest.mark.unit
    @patch('services.keyframe_service.ComfyUIAPI')
    def test_run_generation_connection_failure(self, mock_api_class, tmp_path):
        """Should yield error when ComfyUI connection fails"""
        # Arrange
        mock_config = Mock(spec=ConfigManager)
        mock_store = Mock(spec=ProjectStore)

        # Mock API instance
        mock_api_instance = Mock()
        mock_api_instance.test_connection.return_value = {
            "connected": False,
            "error": "Connection refused"
        }
        mock_api_class.return_value = mock_api_instance

        service = KeyframeGenerationService(mock_config, mock_store)

        storyboard = Storyboard(project="Test", shots=[], raw={})
        checkpoint = {"storyboard_file": "test.json", "variants_per_shot": 4, "base_seed": 2000}
        project = {"path": str(tmp_path)}

        # Act
        generator = service.run_generation(
            storyboard=storyboard,
            workflow_file="test_workflow.json",
            checkpoint=checkpoint,
            project=project,
            comfy_url="http://127.0.0.1:8188"
        )

        # Get first yield
        images, status, progress, updated_checkpoint, current_shot = next(generator)

        # Assert
        assert "error" in status.lower() or "❌" in status
        assert "connection" in status.lower()
        assert images == []
        assert service.is_running is False

    @pytest.mark.unit
    @patch('services.keyframe_service.ComfyUIAPI')
    def test_run_generation_workflow_not_found(self, mock_api_class, tmp_path):
        """Should yield error when workflow file doesn't exist"""
        # Arrange
        mock_config = Mock(spec=ConfigManager)
        mock_store = Mock(spec=ProjectStore)

        # Mock API instance
        mock_api_instance = Mock()
        mock_api_instance.test_connection.return_value = {"connected": True}
        mock_api_class.return_value = mock_api_instance

        # Mock workflow directory
        workflow_dir = tmp_path / "workflows"
        workflow_dir.mkdir()
        mock_config.get_workflow_dir = Mock(return_value=str(workflow_dir))

        service = KeyframeGenerationService(mock_config, mock_store)

        storyboard = Storyboard(project="Test", shots=[], raw={})
        checkpoint = {"storyboard_file": "test.json", "variants_per_shot": 4, "base_seed": 2000}
        project = {"path": str(tmp_path)}

        # Act
        generator = service.run_generation(
            storyboard=storyboard,
            workflow_file="nonexistent.json",  # Doesn't exist
            checkpoint=checkpoint,
            project=project,
            comfy_url="http://127.0.0.1:8188"
        )

        # Get first yield
        images, status, progress, updated_checkpoint, current_shot = next(generator)

        # Assert
        assert "error" in status.lower() or "❌" in status
        assert "workflow" in status.lower()
        assert images == []


class TestKeyframeGenerationServiceIntegration:
    """Integration tests for KeyframeGenerationService"""

    @pytest.mark.unit
    def test_service_lifecycle(self):
        """Should properly manage is_running and stop_requested flags"""
        # Arrange
        mock_config = Mock(spec=ConfigManager)
        mock_store = Mock(spec=ProjectStore)

        service = KeyframeGenerationService(mock_config, mock_store)

        # Act & Assert - Initial state
        assert service.is_running is False
        assert service.stop_requested is False

        # Simulate running state
        service.is_running = True
        assert service.is_running is True

        # Request stop
        service.stop_generation()
        assert service.stop_requested is True

        # Cleanup
        service.is_running = False
        service.stop_requested = False
        assert service.is_running is False
        assert service.stop_requested is False
