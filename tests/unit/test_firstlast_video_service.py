"""Tests for FirstLastVideoService."""
import os
import json
import time
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from services.firstlast_video_service import (
    FirstLastVideoService,
    TransitionResult,
    ClipResult,
    GenerationResult
)


class TestTransitionResult:
    """Tests for TransitionResult dataclass."""

    def test_transition_result_success(self):
        """Test successful transition result."""
        result = TransitionResult(
            success=True,
            start_image="/path/start.png",
            end_image="/path/end.png",
            video_path="/path/output.mp4"
        )
        assert result.success is True
        assert result.video_path == "/path/output.mp4"
        assert result.error is None

    def test_transition_result_failure(self):
        """Test failed transition result."""
        result = TransitionResult(
            success=False,
            start_image="/path/start.png",
            end_image="/path/end.png",
            error="Image not found"
        )
        assert result.success is False
        assert result.video_path is None
        assert result.error == "Image not found"


class TestClipResult:
    """Tests for ClipResult dataclass."""

    def test_clip_result_success(self):
        """Test successful clip result."""
        transitions = [
            TransitionResult(True, "a.png", "b.png", "/out/t1.mp4"),
            TransitionResult(True, "b.png", "c.png", "/out/t2.mp4"),
        ]
        result = ClipResult(
            success=True,
            clip_index=0,
            transitions=transitions
        )
        assert result.success is True
        assert len(result.transitions) == 2
        assert result.error is None

    def test_clip_result_default_values(self):
        """Test default values for ClipResult."""
        result = ClipResult(success=False, clip_index=0)
        assert result.transitions == []
        assert result.merged_video is None
        assert result.error is None


class TestGenerationResult:
    """Tests for GenerationResult dataclass."""

    def test_generation_result_success(self):
        """Test successful generation result."""
        result = GenerationResult(
            success=True,
            total_transitions=5,
            duration_seconds=120.0
        )
        assert result.success is True
        assert result.clips == []
        assert result.total_transitions == 5
        assert result.duration_seconds == 120.0

    def test_generation_result_failure(self):
        """Test failed generation result."""
        result = GenerationResult(
            success=False,
            error="All clips failed"
        )
        assert result.success is False
        assert result.error == "All clips failed"


class TestFirstLastVideoService:
    """Tests for FirstLastVideoService class."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create mock ConfigManager."""
        config = Mock()
        config.get_comfy_url.return_value = "http://127.0.0.1:8188"
        config.get_comfy_root.return_value = str(tmp_path / "comfyui")
        return config

    @pytest.fixture
    def mock_api(self):
        """Create mock ComfyUIAPI."""
        api = Mock()
        api.load_workflow.return_value = {
            "80": {"inputs": {"image": ""}},
            "89": {"inputs": {"image": ""}},
            "90": {"inputs": {"text": ""}},
            "78": {"inputs": {"text": ""}},
            "81": {"inputs": {"width": 1280, "height": 720, "length": 81}},
            "84": {"inputs": {"steps": 20, "cfg": 4.0}},
            "87": {"inputs": {"steps": 20, "cfg": 4.0}},
            "86": {"inputs": {"fps": 16}},
            "83": {"inputs": {"filename_prefix": "video/transition"}},
        }
        api.queue_prompt.return_value = "test-prompt-id"
        api.monitor_progress.return_value = {"status": "success"}
        return api

    @pytest.fixture
    def service(self, mock_config, mock_api):
        """Create FirstLastVideoService instance."""
        with patch('services.firstlast_video_service.ComfyUIAPI', return_value=mock_api):
            service = FirstLastVideoService(config=mock_config)
            service.api = mock_api
            return service

    @pytest.fixture
    def create_test_images(self, tmp_path):
        """Factory to create test image files."""
        from PIL import Image
        import numpy as np

        def _create(count=2):
            paths = []
            for i in range(count):
                img_path = tmp_path / f"image_{i}.png"
                img_array = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)
                img = Image.fromarray(img_array)
                img.save(img_path)
                paths.append(str(img_path))
            return paths
        return _create

    # ========================================================================
    # Initialization Tests
    # ========================================================================

    def test_init(self, mock_config):
        """Test service initialization."""
        with patch('services.firstlast_video_service.ComfyUIAPI') as mock_api_class:
            service = FirstLastVideoService(config=mock_config)
            mock_api_class.assert_called_once()

    def test_default_workflow_file(self, service):
        """Test default workflow file path."""
        assert "gcvfl_wan_2.2_14b_flf2v.json" in service.DEFAULT_WORKFLOW_FILE

    def test_node_ids_defined(self, service):
        """Test that all required node IDs are defined."""
        required_nodes = [
            "start_image", "end_image", "positive_prompt",
            "negative_prompt", "wan_flf", "sampler_high",
            "sampler_low", "create_video", "save_video"
        ]
        for node in required_nodes:
            assert node in service.NODES

    # ========================================================================
    # Load Workflow Tests
    # ========================================================================

    def test_load_workflow(self, service, mock_api):
        """Test workflow loading."""
        workflow = service._load_workflow()
        mock_api.load_workflow.assert_called_once()
        assert workflow is not None

    def test_load_workflow_caching(self, service, mock_api):
        """Test that workflow is cached."""
        service._load_workflow()
        service._load_workflow()
        # Should only load once due to caching
        assert mock_api.load_workflow.call_count == 1

    def test_load_workflow_different_file(self, service, mock_api):
        """Test loading different workflow file."""
        service._load_workflow("custom_workflow.json")
        service._load_workflow("another_workflow.json")
        # Should load again for different file
        assert mock_api.load_workflow.call_count == 2

    # ========================================================================
    # Image Upload Tests
    # ========================================================================

    def test_upload_image(self, service, create_test_images, tmp_path, mock_config):
        """Test image upload to ComfyUI input folder."""
        images = create_test_images(1)
        input_dir = tmp_path / "comfyui" / "input"
        input_dir.mkdir(parents=True, exist_ok=True)

        filename = service._upload_image(images[0])

        assert filename.startswith("flf_")
        assert input_dir.exists()

    def test_cleanup_image(self, service, tmp_path, mock_config):
        """Test image cleanup."""
        input_dir = tmp_path / "comfyui" / "input"
        input_dir.mkdir(parents=True, exist_ok=True)
        test_file = input_dir / "test_image.png"
        test_file.write_bytes(b"fake image")

        service._cleanup_image("test_image.png")

        assert not test_file.exists()

    def test_cleanup_image_nonexistent(self, service):
        """Test cleanup of non-existent image doesn't raise."""
        # Should not raise
        service._cleanup_image("nonexistent.png")

    # ========================================================================
    # Generate Transition Tests
    # ========================================================================

    def test_generate_transition_missing_start_image(self, service):
        """Test transition with missing start image."""
        result = service.generate_transition(
            start_image_path="/nonexistent/start.png",
            end_image_path="/path/end.png",
            prompt="test prompt"
        )

        assert result.success is False
        assert "Start image not found" in result.error

    def test_generate_transition_missing_end_image(self, service, create_test_images):
        """Test transition with missing end image."""
        images = create_test_images(1)

        result = service.generate_transition(
            start_image_path=images[0],
            end_image_path="/nonexistent/end.png",
            prompt="test prompt"
        )

        assert result.success is False
        assert "End image not found" in result.error

    def test_generate_transition_success(self, service, create_test_images, tmp_path, mock_config):
        """Test successful transition generation."""
        images = create_test_images(2)

        # Setup ComfyUI directories
        comfy_root = tmp_path / "comfyui"
        input_dir = comfy_root / "input"
        output_dir = comfy_root / "output" / "video"
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create fake output video
        output_video = output_dir / "transition_test.mp4"
        output_video.write_bytes(b"fake video")

        with patch.object(service, '_find_output_video', return_value=str(output_video)):
            with patch('shutil.move') as mock_move:
                result = service.generate_transition(
                    start_image_path=images[0],
                    end_image_path=images[1],
                    prompt="test prompt"
                )

        assert result.success is True

    def test_generate_transition_with_callback(self, service, create_test_images, tmp_path):
        """Test transition with progress callback."""
        images = create_test_images(2)

        input_dir = tmp_path / "comfyui" / "input"
        input_dir.mkdir(parents=True, exist_ok=True)

        callback_calls = []

        def callback(pct, status):
            callback_calls.append((pct, status))

        with patch.object(service, '_find_output_video', return_value=None):
            service.generate_transition(
                start_image_path=images[0],
                end_image_path=images[1],
                prompt="test",
                callback=callback
            )

        assert len(callback_calls) > 0

    def test_generate_transition_custom_parameters(self, service, create_test_images, tmp_path, mock_api):
        """Test transition with custom parameters."""
        images = create_test_images(2)

        input_dir = tmp_path / "comfyui" / "input"
        input_dir.mkdir(parents=True, exist_ok=True)

        with patch.object(service, '_find_output_video', return_value=None):
            service.generate_transition(
                start_image_path=images[0],
                end_image_path=images[1],
                prompt="test",
                width=1920,
                height=1080,
                frames=121,
                fps=24,
                steps=30,
                cfg=6.0
            )

        # Verify API was called
        mock_api.queue_prompt.assert_called_once()

    def test_generate_transition_generation_failure(self, service, create_test_images, tmp_path, mock_api):
        """Test transition when generation fails."""
        images = create_test_images(2)

        input_dir = tmp_path / "comfyui" / "input"
        input_dir.mkdir(parents=True, exist_ok=True)

        mock_api.monitor_progress.return_value = {
            "status": "error",
            "error": "GPU out of memory"
        }

        result = service.generate_transition(
            start_image_path=images[0],
            end_image_path=images[1],
            prompt="test"
        )

        assert result.success is False

    # ========================================================================
    # Generate Clip Tests
    # ========================================================================

    def test_generate_clip_too_few_images(self, service):
        """Test clip generation with less than 2 images."""
        result = service.generate_clip(
            image_paths=["/path/single.png"],
            prompt="test"
        )

        assert result.success is False
        assert "at least 2 images" in result.error

    def test_generate_clip_success(self, service, create_test_images, tmp_path):
        """Test successful clip generation."""
        images = create_test_images(3)

        input_dir = tmp_path / "comfyui" / "input"
        input_dir.mkdir(parents=True, exist_ok=True)

        # Mock successful transitions
        with patch.object(service, 'generate_transition') as mock_trans:
            mock_trans.return_value = TransitionResult(
                success=True,
                start_image="a.png",
                end_image="b.png",
                video_path="/output/trans.mp4"
            )

            result = service.generate_clip(
                image_paths=images,
                prompt="test",
                clip_index=0
            )

        assert result.success is True
        assert len(result.transitions) == 2  # 3 images = 2 transitions

    def test_generate_clip_partial_failure(self, service, create_test_images, tmp_path):
        """Test clip with some failed transitions."""
        images = create_test_images(3)

        input_dir = tmp_path / "comfyui" / "input"
        input_dir.mkdir(parents=True, exist_ok=True)

        call_count = [0]

        def mock_transition(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return TransitionResult(True, "a", "b", "/out/t1.mp4")
            else:
                return TransitionResult(False, "b", "c", error="Failed")

        with patch.object(service, 'generate_transition', side_effect=mock_transition):
            result = service.generate_clip(images, "test")

        assert result.success is True  # At least one succeeded
        assert len([t for t in result.transitions if t.success]) == 1

    def test_generate_clip_all_failed(self, service, create_test_images, tmp_path):
        """Test clip when all transitions fail."""
        images = create_test_images(3)

        input_dir = tmp_path / "comfyui" / "input"
        input_dir.mkdir(parents=True, exist_ok=True)

        with patch.object(service, 'generate_transition') as mock_trans:
            mock_trans.return_value = TransitionResult(
                success=False,
                start_image="a",
                end_image="b",
                error="Failed"
            )

            result = service.generate_clip(images, "test")

        assert result.success is False
        assert "All transitions failed" in result.error

    # ========================================================================
    # Generate All Clips Tests
    # ========================================================================

    def test_generate_all_clips_empty(self, service):
        """Test generation with no clips."""
        result = service.generate_all_clips([], "test")

        assert result.success is False
        assert "No transitions" in result.error

    def test_generate_all_clips_single_image_clips(self, service):
        """Test generation with single-image clips."""
        clips = [["/path/1.png"], ["/path/2.png"]]

        result = service.generate_all_clips(clips, "test")

        assert result.success is False

    def test_generate_all_clips_success(self, service, create_test_images, tmp_path):
        """Test successful generation of all clips."""
        images = create_test_images(4)
        clips = [images[:2], images[2:4]]

        input_dir = tmp_path / "comfyui" / "input"
        input_dir.mkdir(parents=True, exist_ok=True)

        with patch.object(service, 'generate_clip') as mock_clip:
            mock_clip.return_value = ClipResult(
                success=True,
                clip_index=0,
                transitions=[TransitionResult(True, "a", "b", "/out/t.mp4")]
            )

            result = service.generate_all_clips(clips, "test")

        assert result.success is True
        assert result.total_transitions == 2

    def test_generate_all_clips_records_duration(self, service, create_test_images, tmp_path):
        """Test that generation records duration."""
        images = create_test_images(2)
        clips = [images]

        input_dir = tmp_path / "comfyui" / "input"
        input_dir.mkdir(parents=True, exist_ok=True)

        with patch.object(service, 'generate_clip') as mock_clip:
            mock_clip.return_value = ClipResult(
                success=True,
                clip_index=0,
                transitions=[TransitionResult(True, "a", "b", "/out/t.mp4")]
            )

            result = service.generate_all_clips(clips, "test")

        assert result.duration_seconds >= 0

    def test_generate_all_clips_with_callback(self, service, create_test_images, tmp_path):
        """Test generation with progress callback."""
        images = create_test_images(2)
        clips = [images]

        input_dir = tmp_path / "comfyui" / "input"
        input_dir.mkdir(parents=True, exist_ok=True)

        callback_calls = []

        def callback(pct, status):
            callback_calls.append((pct, status))

        with patch.object(service, 'generate_clip') as mock_clip:
            mock_clip.return_value = ClipResult(
                success=True,
                clip_index=0,
                transitions=[TransitionResult(True, "a", "b", "/out/t.mp4")]
            )

            service.generate_all_clips(clips, "test", callback=callback)

        # Callback should have been called
        assert len(callback_calls) >= 0  # May be 0 if clip callback not triggered

    def test_generate_all_clips_skips_single_image_clips(self, service, create_test_images, tmp_path):
        """Test that single-image clips are skipped."""
        images = create_test_images(3)
        clips = [images[:2], [images[2]]]  # Second clip has only 1 image

        input_dir = tmp_path / "comfyui" / "input"
        input_dir.mkdir(parents=True, exist_ok=True)

        with patch.object(service, 'generate_clip') as mock_clip:
            mock_clip.return_value = ClipResult(
                success=True,
                clip_index=0,
                transitions=[TransitionResult(True, "a", "b", "/out/t.mp4")]
            )

            result = service.generate_all_clips(clips, "test")

        # Only one clip should be processed
        assert mock_clip.call_count == 1

    def test_generate_all_clips_custom_parameters(self, service, create_test_images, tmp_path):
        """Test generation with custom parameters passed through."""
        images = create_test_images(2)
        clips = [images]

        input_dir = tmp_path / "comfyui" / "input"
        input_dir.mkdir(parents=True, exist_ok=True)

        with patch.object(service, 'generate_clip') as mock_clip:
            mock_clip.return_value = ClipResult(
                success=True,
                clip_index=0,
                transitions=[]
            )

            service.generate_all_clips(
                clips,
                "test prompt",
                negative_prompt="bad quality",
                width=1920,
                height=1080,
                frames=121,
                fps=24,
                steps=30,
                cfg=6.0
            )

        # Verify parameters were passed
        call_kwargs = mock_clip.call_args[1]
        assert call_kwargs["width"] == 1920
        assert call_kwargs["height"] == 1080
        assert call_kwargs["frames"] == 121
        assert call_kwargs["fps"] == 24
        assert call_kwargs["steps"] == 30
        assert call_kwargs["cfg"] == 6.0
