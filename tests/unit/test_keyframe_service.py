"""Unit tests for KeyframeService"""
import glob
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

    @pytest.mark.unit
    def test_copy_generated_images_skips_duplicate_destinations(self, tmp_path, create_test_image):
        """Should skip files with duplicate destination paths"""
        # Arrange
        mock_config = Mock(spec=ConfigManager)
        mock_store = Mock(spec=ProjectStore)

        # Create source directory structure with subdirectory
        comfy_output_dir = tmp_path / "comfyui" / "output"
        comfy_output_dir.mkdir(parents=True)
        subdir = comfy_output_dir / "subdir"
        subdir.mkdir()

        # Create destination directory (project keyframes)
        project_keyframes_dir = tmp_path / "project" / "keyframes"
        project_keyframes_dir.mkdir(parents=True)

        mock_store.comfy_output_dir = Mock(return_value=str(comfy_output_dir))

        service = KeyframeGenerationService(mock_config, mock_store)

        # Create images with same basename in different directories
        # These would both try to move to "test-shot_v1_00001_.png" in dest
        image_in_root = comfy_output_dir / "test-shot_v1_00001_.png"
        image_in_subdir = subdir / "test-shot_v1_00001_.png"
        create_test_image(str(image_in_root))
        create_test_image(str(image_in_subdir))

        # Act
        result = service._copy_generated_images(
            variant_name="test-shot_v1",
            output_dir=str(project_keyframes_dir),
            api_result={}
        )

        # Assert
        # Only one image should be moved (the first one found)
        assert len(result) == 1
        assert (project_keyframes_dir / "test-shot_v1_00001_.png").exists()
        # The second source should still exist because it was skipped
        assert image_in_subdir.exists()


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
        # Generator should stop after failure branch
        with pytest.raises(StopIteration):
            next(generator)

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
        with pytest.raises(StopIteration):
            next(generator)

    @pytest.mark.unit
    @patch('services.keyframe_service.ComfyUIAPI')
    def test_run_generation_handles_exception(self, mock_api_class, tmp_path):
        """Should yield error when unexpected exception occurs"""
        mock_api_instance = Mock()
        mock_api_instance.test_connection.return_value = {"connected": True}
        mock_api_instance.load_workflow.return_value = {}
        mock_api_class.return_value = mock_api_instance

        mock_config = Mock(spec=ConfigManager)
        workflow_dir = tmp_path / "workflows"
        workflow_dir.mkdir()
        workflow_path = workflow_dir / "wf.json"
        workflow_path.write_text("{}")
        mock_config.get_workflow_dir.return_value = str(workflow_dir)
        mock_store = Mock(spec=ProjectStore)
        mock_store.ensure_dir.side_effect = RuntimeError("ensure-dir failed")

        service = KeyframeGenerationService(mock_config, mock_store)
        storyboard = Storyboard(project="Test", shots=[], raw={})
        checkpoint = {
            "storyboard_file": "sb.json",
            "variants_per_shot": 1,
            "base_seed": 0,
            "completed_shots": [],
            "total_images_generated": 0,
            "status": "running",
        }
        project = {"path": str(tmp_path)}

        gen = service.run_generation(
            storyboard=storyboard,
            workflow_file=str(workflow_path.name),
            checkpoint=checkpoint,
            project=project,
            comfy_url="http://127.0.0.1:8188",
        )

        images, status, *_ = next(gen)
        assert images == []
        assert "Fehler" in status or "error" in status.lower()
        assert checkpoint["status"] == "error"

    @pytest.mark.unit
    @patch('services.keyframe_service.ComfyUIAPI')
    def test_run_generation_success_flow(self, mock_api_class, tmp_path):
        """Should complete generation loop and mark checkpoint finished"""
        mock_api_instance = Mock()
        mock_api_instance.test_connection.return_value = {"connected": True}
        mock_api_instance.load_workflow.return_value = {}
        mock_api_class.return_value = mock_api_instance

        # Prepare workflow file on disk
        workflow_dir = tmp_path / "workflows"
        workflow_dir.mkdir()
        workflow_path = workflow_dir / "wf.json"
        workflow_path.write_text("{}")

        mock_config = Mock(spec=ConfigManager)
        mock_config.get_workflow_dir.return_value = str(workflow_dir)
        mock_config.get_resolution_tuple.return_value = (1024, 576)

        mock_store = Mock(spec=ProjectStore)
        mock_store.ensure_dir.side_effect = lambda project, name=None: str(tmp_path / "out")

        service = KeyframeGenerationService(mock_config, mock_store)
        service._generate_shot = Mock(
            return_value=iter([
                (
                    ["img1"],
                    "shot-status",
                    "progress",
                    {
                        "storyboard_file": "sb.json",
                        "completed_shots": ["001"],
                        "total_images_generated": 1,
                        "status": "running",
                    },
                    "current",
                ),
            ])
        )

        storyboard = Storyboard.from_dict({"project": "Test", "shots": [{"shot_id": "001", "prompt": "p", "filename_base": "shot"}]})
        checkpoint = {
            "storyboard_file": "sb.json",
            "variants_per_shot": 1,
            "base_seed": 0,
            "completed_shots": [],
            "total_images_generated": 0,
            "status": "running",
        }
        project = {"path": str(tmp_path)}

        gen = service.run_generation(
            storyboard=storyboard,
            workflow_file="wf.json",
            checkpoint=checkpoint,
            project=project,
            comfy_url="http://127.0.0.1:8188",
        )

        results = list(gen)
        # Last yield should mark completed status
        final = results[-1]
        assert final[3]["status"] == "completed"
        assert "Complete" in final[1]

    @pytest.mark.unit
    @patch('services.keyframe_service.ComfyUIAPI')
    def test_run_generation_skips_completed_shot(self, mock_api_class, tmp_path):
        """Should skip shots already marked as completed"""
        mock_config = Mock(spec=ConfigManager)
        workflow_dir = tmp_path / "workflows"
        workflow_dir.mkdir()
        workflow_path = workflow_dir / "wf.json"
        workflow_path.write_text("{}")
        mock_config.get_workflow_dir.return_value = str(workflow_dir)
        mock_config.get_resolution_tuple.return_value = (640, 480)

        mock_store = Mock(spec=ProjectStore)
        mock_store.ensure_dir.return_value = str(tmp_path / "out")

        service = KeyframeGenerationService(mock_config, mock_store)
        mock_api = Mock()
        mock_api.test_connection.return_value = {"connected": True}
        mock_api.load_workflow.return_value = {}
        mock_api_class.return_value = mock_api
        service.api = mock_api
        service.api.test_connection.return_value = {"connected": True}
        service.api.load_workflow.return_value = {}
        service._generate_shot = Mock(return_value=iter([]))

        storyboard = Storyboard.from_dict(
            {"project": "Test", "shots": [{"shot_id": "001", "prompt": "p", "filename_base": "shot"}]}
        )
        checkpoint = {
            "storyboard_file": "sb.json",
            "variants_per_shot": 1,
            "base_seed": 0,
            "completed_shots": ["001"],
            "total_images_generated": 0,
            "status": "running",
        }

        gen = service.run_generation(
            storyboard=storyboard,
            workflow_file=workflow_path.name,
            checkpoint=checkpoint,
            project={"path": str(tmp_path)},
            comfy_url="http://127.0.0.1:8188",
        )

        results = list(gen)
        assert service._generate_shot.call_count == 0
        assert results[-1][3]["status"] == "completed"

    @pytest.mark.unit
    @patch('services.keyframe_service.ComfyUIAPI')
    def test_run_generation_honors_stop_requested(self, mock_api_class, tmp_path):
        """Should delegate to _handle_stop when stop_requested is True"""
        mock_config = Mock(spec=ConfigManager)
        workflow_dir = tmp_path / "workflows"
        workflow_dir.mkdir()
        workflow_path = workflow_dir / "wf.json"
        workflow_path.write_text("{}")
        mock_config.get_workflow_dir.return_value = str(workflow_dir)
        mock_config.get_resolution_tuple.return_value = (640, 480)

        mock_store = Mock(spec=ProjectStore)
        mock_store.ensure_dir.return_value = str(tmp_path / "out")

        service = KeyframeGenerationService(mock_config, mock_store)
        service.stop_requested = True
        service.api = Mock()
        service.api.test_connection.return_value = {"connected": True}
        service.api.load_workflow.return_value = {}
        service._handle_stop = Mock(return_value=iter([([], "stopped", "progress", {}, "stop")]))
        mock_api_class.return_value = service.api

        storyboard = Storyboard.from_dict(
            {"project": "Test", "shots": [{"shot_id": "001", "prompt": "p", "filename_base": "shot"}]}
        )
        checkpoint = {
            "storyboard_file": "sb.json",
            "variants_per_shot": 1,
            "base_seed": 0,
            "completed_shots": [],
            "total_images_generated": 0,
            "status": "running",
        }

        gen = service.run_generation(
            storyboard=storyboard,
            workflow_file=workflow_path.name,
            checkpoint=checkpoint,
            project={"path": str(tmp_path)},
            comfy_url="http://127.0.0.1:8188",
        )

        results = list(gen)
        assert any("stopped" in status.lower() for *_imgs, status, _progress, _cp, _curr in results)

    @pytest.mark.unit
    def test_generate_shot_invokes_progress_callback(self):
        """Should call progress_callback before yielding"""
        mock_config = Mock(spec=ConfigManager)
        mock_config.get_resolution_tuple.return_value = (640, 480)
        mock_store = Mock(spec=ProjectStore)

        service = KeyframeGenerationService(mock_config, mock_store)
        service.stop_requested = False
        service._generate_variant = Mock(return_value=iter([]))
        service._save_checkpoint = Mock()
        service.config = mock_config

        checkpoint = {
            "completed_shots": [],
            "total_images_generated": 0,
            "status": "running",
            "variants_per_shot": 1,
            "storyboard_file": "sb.json",
        }

        calls = []
        gen = service._generate_shot(
            shot={"prompt": "p", "filename_base": "shot"},
            shot_idx=0,
            shot_id="001",
            workflow={},
            variants_per_shot=1,
            base_seed=0,
            output_dir="/tmp",
            checkpoint=checkpoint,
            total_shots=1,
            project={"path": "/tmp"},
            images_done=0,
            total_images_est=1,
            progress_callback=lambda pct, desc=None: calls.append((pct, desc)),
        )

        list(gen)
        assert calls
        assert "001" in calls[0][1]


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


class TestKeyframeGenerationServiceInternals:
    """Unit tests for internal generation helpers"""

    @pytest.mark.unit
    def test_generate_variant_success_path(self, tmp_path):
        """Should increment counters and save checkpoints on success"""
        mock_config = Mock(spec=ConfigManager)
        mock_config.get_resolution_tuple.return_value = (1280, 720)
        mock_store = Mock(spec=ProjectStore)

        service = KeyframeGenerationService(mock_config, mock_store)
        service.api = Mock()
        service.api.update_workflow_params.return_value = {"workflow": {}}
        service.api.queue_prompt.return_value = "pid-1"
        service.api.monitor_progress.return_value = {"status": "success"}
        service._copy_generated_images = Mock(return_value=[str(tmp_path / "img.png")])
        service._save_checkpoint = Mock()
        progress_calls = []

        checkpoint = {
            "storyboard_file": "sb.json",
            "variants_per_shot": 1,
            "base_seed": 42,
            "completed_shots": [],
            "total_images_generated": 0,
            "status": "running",
        }

        generator = service._generate_variant(
            shot={"prompt": "p"},
            shot_id="001",
            shot_idx=0,
            variant_idx=0,
            variants_per_shot=1,
            filename_base="shot",
            workflow={},
            base_seed=100,
            res_width=640,
            res_height=360,
            output_dir=str(tmp_path),
            checkpoint=checkpoint,
            total_shots=1,
            project={"path": str(tmp_path)},
            images_done=0,
            total_images_est=1,
            progress_callback=lambda pct, desc=None: progress_calls.append((pct, desc)),
        )

        results = list(generator)
        assert results  # One yield
        images, status, _progress, updated_cp, _display = results[0]
        assert images == [str(tmp_path / "img.png")]
        assert "Variant 1" in status
        assert updated_cp["total_images_generated"] == 1
        service._save_checkpoint.assert_called_once()
        assert progress_calls  # progress callback invoked

    @pytest.mark.unit
    def test_generate_variant_failure_status(self):
        """Should yield failure status when monitor_progress reports error"""
        mock_config = Mock(spec=ConfigManager)
        mock_config.get_resolution_tuple.return_value = (1280, 720)
        mock_store = Mock(spec=ProjectStore)

        service = KeyframeGenerationService(mock_config, mock_store)
        service.api = Mock()
        service.api.update_workflow_params.return_value = {}
        service.api.queue_prompt.return_value = "pid-err"
        service.api.monitor_progress.return_value = {"status": "error", "error": "boom"}
        service._copy_generated_images = Mock(return_value=[])
        service._save_checkpoint = Mock()

        checkpoint = {"completed_shots": [], "total_images_generated": 0, "status": "running", "variants_per_shot": 1}

        generator = service._generate_variant(
            shot={"prompt": "p"},
            shot_id="001",
            shot_idx=0,
            variant_idx=0,
            variants_per_shot=1,
            filename_base="shot",
            workflow={},
            base_seed=100,
            res_width=640,
            res_height=360,
            output_dir="/tmp",
            checkpoint=checkpoint,
            total_shots=1,
            project={"path": "/tmp"},
            images_done=0,
            total_images_est=1,
        )

        images, status, _progress, updated_cp, _display = next(generator)
        assert images == []
        assert "failed" in status.lower() or "✗" in status
        assert updated_cp["total_images_generated"] == 0

    @pytest.mark.unit
    def test_generate_variant_copy_failure(self):
        """Should warn and yield copy-failed status if no images copied"""
        mock_config = Mock(spec=ConfigManager)
        mock_config.get_resolution_tuple.return_value = (1280, 720)
        mock_store = Mock(spec=ProjectStore)

        service = KeyframeGenerationService(mock_config, mock_store)
        service.api = Mock()
        service.api.update_workflow_params.return_value = {}
        service.api.queue_prompt.return_value = "pid-ok"
        service.api.monitor_progress.return_value = {"status": "success"}
        service._copy_generated_images = Mock(return_value=[])

        checkpoint = {"completed_shots": [], "total_images_generated": 0, "status": "running", "variants_per_shot": 1}

        gen = service._generate_variant(
            shot={"prompt": "p"},
            shot_id="001",
            shot_idx=0,
            variant_idx=0,
            variants_per_shot=1,
            filename_base="shot",
            workflow={},
            base_seed=100,
            res_width=640,
            res_height=360,
            output_dir="/tmp",
            checkpoint=checkpoint,
            total_shots=1,
            project={"path": "/tmp"},
            images_done=0,
            total_images_est=1,
        )

        images, status, _progress, _cp, _display = next(gen)
        assert images == []
        assert "copy failed" in status.lower() or "⚠️" in status

    @pytest.mark.unit
    def test_generate_variant_handles_exception(self):
        """Should yield error status when generation throws"""
        mock_config = Mock(spec=ConfigManager)
        mock_config.get_resolution_tuple.return_value = (640, 480)
        mock_store = Mock(spec=ProjectStore)

        service = KeyframeGenerationService(mock_config, mock_store)
        service.api = Mock()
        service.api.update_workflow_params.return_value = {}
        service.api.queue_prompt.side_effect = RuntimeError("api down")

        checkpoint = {
            "storyboard_file": "sb.json",
            "completed_shots": [],
            "total_images_generated": 0,
        }

        gen = service._generate_variant(
            shot={"prompt": "p", "filename_base": "shot"},
            shot_id="001",
            shot_idx=0,
            variant_idx=0,
            variants_per_shot=1,
            filename_base="shot",
            workflow={},
            base_seed=0,
            res_width=640,
            res_height=480,
            output_dir="out",
            checkpoint=checkpoint,
            total_shots=1,
            project={},
            images_done=0,
            total_images_est=1,
            progress_callback=None,
            current_shot_display="display",
        )

        images, status, *_ = next(gen)
        assert images == []
        assert "error" in status.lower()

    @pytest.mark.unit
    def test_copy_generated_images_handles_errors(self, tmp_path, monkeypatch):
        """_copy_generated_images should swallow unexpected errors"""
        mock_config = Mock(spec=ConfigManager)
        mock_store = Mock(spec=ProjectStore)
        mock_store.comfy_output_dir.return_value = str(tmp_path)

        service = KeyframeGenerationService(mock_config, mock_store)
        monkeypatch.setattr("glob.glob", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("glob failed")))

        copied = service._copy_generated_images("var", str(tmp_path), {"output_images": []})
        assert copied == []

    @pytest.mark.unit
    def test_save_checkpoint_handles_io_error(self, tmp_path, monkeypatch):
        """_save_checkpoint should log and continue on failure"""
        mock_config = Mock(spec=ConfigManager)
        mock_store = Mock(spec=ProjectStore)
        mock_store.ensure_dir.return_value = str(tmp_path)

        service = KeyframeGenerationService(mock_config, mock_store)
        monkeypatch.setattr("builtins.open", lambda *_a, **_k: (_ for _ in ()).throw(IOError("disk full")))

        # Should not raise
        service._save_checkpoint({"status": "running"}, "sb.json", {"path": str(tmp_path)})

    @pytest.mark.unit
    def test_generate_shot_stops_on_flag(self):
        """Should stop early when stop_requested is True"""
        mock_config = Mock(spec=ConfigManager)
        mock_config.get_resolution_tuple.return_value = (1024, 576)
        mock_store = Mock(spec=ProjectStore)

        service = KeyframeGenerationService(mock_config, mock_store)
        service.stop_requested = True
        service._save_checkpoint = Mock()
        service._generate_variant = Mock()

        checkpoint = {
            "completed_shots": [],
            "total_images_generated": 0,
            "status": "running",
            "variants_per_shot": 1,
            "storyboard_file": "sb.json",
        }

        gen = service._generate_shot(
            shot={"prompt": "p", "filename_base": "shot"},
            shot_idx=0,
            shot_id="001",
            workflow={},
            variants_per_shot=1,
            base_seed=0,
            output_dir="/tmp",
            checkpoint=checkpoint,
            total_shots=1,
            project={"path": "/tmp"},
            images_done=0,
            total_images_est=1,
        )

        results = list(gen)
        # Only initial yield, no completion checkpoint
        assert len(results) == 1
        assert checkpoint["completed_shots"] == []
        service._save_checkpoint.assert_not_called()

    @pytest.mark.unit
    def test_generate_shot_marks_completed(self):
        """Should append shot to completed_shots after variants"""
        mock_config = Mock(spec=ConfigManager)
        mock_config.get_resolution_tuple.return_value = (1024, 576)
        mock_store = Mock(spec=ProjectStore)

        service = KeyframeGenerationService(mock_config, mock_store)
        service.stop_requested = False

        def fake_variant(**_kwargs):
            yield ["img"], "status", "progress", _kwargs["checkpoint"], "display"

        service._generate_variant = Mock(side_effect=fake_variant)
        service._save_checkpoint = Mock()

        checkpoint = {
            "completed_shots": [],
            "total_images_generated": 0,
            "status": "running",
            "variants_per_shot": 1,
            "storyboard_file": "sb.json",
        }

        gen = service._generate_shot(
            shot={"prompt": "p", "filename_base": "shot"},
            shot_idx=0,
            shot_id="001",
            workflow={},
            variants_per_shot=1,
            base_seed=0,
            output_dir="/tmp",
            checkpoint=checkpoint,
            total_shots=1,
            project={"path": "/tmp"},
            images_done=0,
            total_images_est=1,
        )

        results = list(gen)
        assert checkpoint["completed_shots"] == ["001"]
        service._save_checkpoint.assert_called()
        assert any("abgeschlossen" in r[1].lower() or "status" in r[1].lower() for r in results)

    @pytest.mark.unit
    def test_handle_stop_sets_status_and_returns_progress(self):
        """Should mark checkpoint stopped and return progress info"""
        mock_config = Mock(spec=ConfigManager)
        mock_store = Mock(spec=ProjectStore)
        service = KeyframeGenerationService(mock_config, mock_store)
        service._save_checkpoint = Mock()

        checkpoint = {"status": "running", "storyboard_file": "sb.json"}
        gen = service._handle_stop(checkpoint, ["img"], total_shots=2, project={"path": "/tmp"})
        images, status, progress, updated_cp, current = next(gen)

        assert updated_cp["status"] == "stopped"
        assert "gestoppt" in status.lower()
        assert "Progress" in progress
        assert "Stopped" in current
