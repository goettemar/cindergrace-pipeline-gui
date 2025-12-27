"""Tests for LipsyncService - Audio processing and Wan i2v workflow control."""
import os
import json
import pytest
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, call
from dataclasses import asdict

from services.lipsync_service import (
    LipsyncService,
    LipsyncJob,
    AudioInfo,
    BatchSegment,
    BatchResult,
    RESOLUTION_PRESETS,
)


@pytest.fixture
def mock_config(tmp_path):
    """Create mock ConfigManager."""
    config = MagicMock()
    config.get_comfy_root.return_value = str(tmp_path / "comfyui")
    config.get.side_effect = lambda key, default=None: {
        "comfy_url": "http://127.0.0.1:8188",
        "workflow_dir": str(tmp_path / "workflows"),
    }.get(key, default)

    # Create directories
    (tmp_path / "comfyui").mkdir()
    (tmp_path / "comfyui" / "input").mkdir()
    (tmp_path / "comfyui" / "output").mkdir()
    (tmp_path / "comfyui" / "output" / "lipsync").mkdir()
    (tmp_path / "workflows").mkdir()

    return config


@pytest.fixture
def mock_api():
    """Create mock ComfyUIAPI."""
    api = MagicMock()
    api.load_workflow.return_value = {
        "52": {"inputs": {"image": ""}},
        "58": {"inputs": {"audio": ""}},
        "6": {"inputs": {"text": ""}},
        "7": {"inputs": {"text": ""}},
        "93": {"inputs": {"width": 1280, "height": 720}},
        "103": {"inputs": {"value": 4}},
        "105": {"inputs": {"value": 1.0}},
        "113": {"inputs": {"filename_prefix": ""}},
        "82": {"inputs": {"fps": 16}},
    }
    api.queue_prompt.return_value = "prompt-123"
    api.monitor_progress.return_value = {"status": "success"}
    return api


@pytest.fixture
def service(mock_config):
    """Create LipsyncService with mock config."""
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
        svc = LipsyncService(config=mock_config)
        return svc


@pytest.fixture
def sample_audio(tmp_path):
    """Create a sample audio file."""
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"RIFF" + b"\x00" * 100)
    return str(audio_path)


@pytest.fixture
def sample_image(tmp_path):
    """Create a sample image file."""
    image_path = tmp_path / "image.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    return str(image_path)


class TestDataclasses:
    """Tests for data classes."""

    def test_audio_info(self):
        """AudioInfo dataclass."""
        info = AudioInfo(
            path="/path/to/audio.wav",
            duration=10.5,
            sample_rate=44100,
            channels=2,
            format="wav"
        )
        assert info.path == "/path/to/audio.wav"
        assert info.duration == 10.5
        assert info.sample_rate == 44100
        assert info.channels == 2
        assert info.format == "wav"

    def test_lipsync_job(self):
        """LipsyncJob dataclass with defaults."""
        job = LipsyncJob(
            image_path="/image.png",
            audio_path="/audio.wav",
            prompt="character speaking",
            negative_prompt="blurry",
            width=1280,
            height=720,
            output_name="test_output"
        )
        assert job.steps == 4  # default
        assert job.cfg == 1.0  # default
        assert job.fps == 16  # default
        assert job.chunk_length == 77  # default

    def test_batch_segment(self):
        """BatchSegment dataclass."""
        segment = BatchSegment(
            audio_path="/segment.wav",
            start_time=0.0,
            end_time=5.0,
            segment_index=0
        )
        assert segment.use_last_frame is False  # default

    def test_batch_result(self):
        """BatchResult dataclass."""
        result = BatchResult(success=True)
        assert result.videos == []  # default
        assert result.errors == []  # default
        assert result.total_segments == 0  # default
        assert result.completed_segments == 0  # default


class TestResolutionPresets:
    """Tests for resolution presets."""

    def test_480p_preset(self):
        """480p resolution preset."""
        assert RESOLUTION_PRESETS["480p"] == (832, 480)

    def test_720p_preset(self):
        """720p resolution preset."""
        assert RESOLUTION_PRESETS["720p"] == (1280, 720)

    def test_1080p_preset(self):
        """1080p resolution preset."""
        assert RESOLUTION_PRESETS["1080p"] == (1920, 1080)

    def test_portrait_presets(self):
        """Portrait resolution presets."""
        assert RESOLUTION_PRESETS["480p_portrait"] == (480, 832)
        assert RESOLUTION_PRESETS["720p_portrait"] == (720, 1280)

    def test_square_preset(self):
        """Square resolution preset."""
        assert RESOLUTION_PRESETS["640x640"] == (640, 640)


class TestLipsyncServiceInit:
    """Tests for LipsyncService initialization."""

    def test_init_with_config(self, mock_config):
        """Initialize with provided config."""
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            service = LipsyncService(config=mock_config)
            assert service.config == mock_config

    def test_init_default_config(self):
        """Initialize creates default ConfigManager."""
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("services.lipsync_service.ConfigManager") as MockConfig:
                service = LipsyncService()
                MockConfig.assert_called_once()

    def test_init_finds_ffmpeg(self, mock_config):
        """Initialize finds ffmpeg executable."""
        with patch("shutil.which", return_value="/custom/path/ffmpeg"):
            service = LipsyncService(config=mock_config)
            assert service._ffmpeg_path == "/custom/path/ffmpeg"

    def test_init_ffmpeg_not_found(self, mock_config):
        """Fallback when ffmpeg not in PATH."""
        with patch("shutil.which", return_value=None):
            with patch("os.path.isfile", return_value=False):
                service = LipsyncService(config=mock_config)
                assert service._ffmpeg_path == "ffmpeg"

    def test_init_ffmpeg_common_location(self, mock_config):
        """Find ffmpeg in common locations."""
        with patch("shutil.which", return_value=None):
            with patch("os.path.isfile", side_effect=lambda p: p == "/usr/bin/ffmpeg"):
                service = LipsyncService(config=mock_config)
                assert service._ffmpeg_path == "/usr/bin/ffmpeg"

    def test_api_is_none_initially(self, service):
        """API is None until first use."""
        assert service.api is None

    def test_max_duration_constant(self):
        """MAX_DURATION_SECONDS constant."""
        assert LipsyncService.MAX_DURATION_SECONDS == 14.0

    def test_default_workflow_constant(self):
        """DEFAULT_WORKFLOW constant."""
        assert LipsyncService.DEFAULT_WORKFLOW == "gcl_wan_2.2_is2v.json"


class TestGetApi:
    """Tests for _get_api method."""

    def test_get_api_creates_api(self, service, mock_config):
        """Creates ComfyUIAPI on first call."""
        with patch("services.lipsync_service.ComfyUIAPI") as MockAPI:
            api = service._get_api()
            MockAPI.assert_called_once_with(server_url="http://127.0.0.1:8188")

    def test_get_api_reuses_api(self, service, mock_config):
        """Reuses existing API on subsequent calls."""
        with patch("services.lipsync_service.ComfyUIAPI") as MockAPI:
            api1 = service._get_api()
            api2 = service._get_api()
            MockAPI.assert_called_once()  # Only created once
            assert api1 is api2


class TestGetAudioInfo:
    """Tests for get_audio_info method."""

    def test_audio_info_file_not_found(self, service):
        """Return None for non-existent file."""
        result = service.get_audio_info("/nonexistent/audio.wav")
        assert result is None

    def test_audio_info_success(self, service, sample_audio):
        """Successfully get audio info."""
        mock_result = Mock()
        mock_result.returncode = 0
        # ffprobe returns: sample_rate,channels on first line, duration on last
        # The code parses all lines and the last parseable float becomes duration
        mock_result.stdout = "44100,2\n10.5"

        with patch("subprocess.run", return_value=mock_result):
            result = service.get_audio_info(sample_audio)

            assert result is not None
            assert result.path == sample_audio
            assert result.duration == 10.5
            assert result.sample_rate == 44100
            assert result.channels == 2
            assert result.format == "wav"

    def test_audio_info_ffprobe_failure(self, service, sample_audio):
        """Return None when ffprobe fails."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Error"

        with patch("subprocess.run", return_value=mock_result):
            result = service.get_audio_info(sample_audio)
            assert result is None

    def test_audio_info_timeout(self, service, sample_audio):
        """Return None on timeout."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ffprobe", 10)):
            result = service.get_audio_info(sample_audio)
            assert result is None

    def test_audio_info_exception(self, service, sample_audio):
        """Return None on exception."""
        with patch("subprocess.run", side_effect=Exception("Error")):
            result = service.get_audio_info(sample_audio)
            assert result is None


class TestTrimAudio:
    """Tests for trim_audio method."""

    def test_trim_file_not_found(self, service):
        """Return failure for non-existent input."""
        success, msg = service.trim_audio("/nonexistent.wav", "/output.wav")
        assert success is False
        assert "not found" in msg.lower()

    def test_trim_success(self, service, sample_audio, tmp_path):
        """Successfully trim audio."""
        output_path = str(tmp_path / "output.wav")
        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            success, msg = service.trim_audio(
                sample_audio, output_path,
                start_time=1.0, end_time=5.0
            )
            assert success is True

    def test_trim_with_max_duration(self, service, sample_audio, tmp_path):
        """Trim with max_duration limit."""
        output_path = str(tmp_path / "output.wav")
        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            success, _ = service.trim_audio(
                sample_audio, output_path,
                start_time=0.0, max_duration=10.0
            )
            assert success is True
            # Check that -t flag was included
            call_args = mock_run.call_args[0][0]
            assert "-t" in call_args
            assert "10.0" in call_args

    def test_trim_ffmpeg_failure(self, service, sample_audio, tmp_path):
        """Return failure when ffmpeg fails."""
        output_path = str(tmp_path / "output.wav")
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Error during trim"

        with patch("subprocess.run", return_value=mock_result):
            success, msg = service.trim_audio(sample_audio, output_path)
            assert success is False
            assert "fail" in msg.lower()

    def test_trim_timeout(self, service, sample_audio, tmp_path):
        """Return failure on timeout."""
        output_path = str(tmp_path / "output.wav")

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ffmpeg", 60)):
            success, msg = service.trim_audio(sample_audio, output_path)
            assert success is False
            # The message is "Trim operation timed out"
            assert "timed out" in msg


class TestCopyToComfyInput:
    """Tests for copy_to_comfy_input method."""

    def test_copy_no_comfy_root(self, service, sample_image, mock_config):
        """Return failure when ComfyUI root not configured."""
        mock_config.get_comfy_root.return_value = None
        success, msg = service.copy_to_comfy_input(sample_image, "image.png")
        assert success is False
        assert "not configured" in msg.lower()

    def test_copy_success(self, service, sample_image, mock_config):
        """Successfully copy file to ComfyUI input."""
        success, result = service.copy_to_comfy_input(sample_image, "test_image.png")
        assert success is True
        assert "test_image.png" in result
        assert os.path.exists(result)

    def test_copy_creates_input_dir(self, service, sample_image, mock_config, tmp_path):
        """Creates input directory if it doesn't exist."""
        # Remove input directory
        input_dir = Path(mock_config.get_comfy_root()) / "input"
        input_dir.rmdir()

        success, result = service.copy_to_comfy_input(sample_image, "test.png")
        assert success is True
        assert input_dir.exists()

    def test_copy_failure(self, service, sample_image, mock_config):
        """Return failure on copy error."""
        with patch("shutil.copy2", side_effect=PermissionError("Access denied")):
            success, msg = service.copy_to_comfy_input(sample_image, "test.png")
            assert success is False


class TestPrepareWorkflow:
    """Tests for prepare_workflow method."""

    def test_prepare_updates_image(self, service):
        """Updates LoadImage node with image filename."""
        workflow = {"52": {"inputs": {"image": "old.png"}}}
        job = LipsyncJob(
            image_path="new_image.png",
            audio_path="audio.wav",
            prompt="test",
            negative_prompt="",
            width=1280,
            height=720,
            output_name="output"
        )

        result = service.prepare_workflow(job, workflow)

        assert result["52"]["inputs"]["image"] == "new_image.png"

    def test_prepare_updates_audio(self, service):
        """Updates LoadAudio node with audio filename."""
        workflow = {"58": {"inputs": {"audio": "old.wav"}}}
        job = LipsyncJob(
            image_path="image.png",
            audio_path="new_audio.wav",
            prompt="test",
            negative_prompt="",
            width=1280,
            height=720,
            output_name="output"
        )

        result = service.prepare_workflow(job, workflow)

        assert result["58"]["inputs"]["audio"] == "new_audio.wav"

    def test_prepare_updates_prompts(self, service):
        """Updates positive and negative prompts."""
        workflow = {
            "6": {"inputs": {"text": ""}},
            "7": {"inputs": {"text": ""}}
        }
        job = LipsyncJob(
            image_path="image.png",
            audio_path="audio.wav",
            prompt="character speaking",
            negative_prompt="blurry, bad quality",
            width=1280,
            height=720,
            output_name="output"
        )

        result = service.prepare_workflow(job, workflow)

        assert result["6"]["inputs"]["text"] == "character speaking"
        assert result["7"]["inputs"]["text"] == "blurry, bad quality"

    def test_prepare_updates_resolution(self, service):
        """Updates resolution settings."""
        workflow = {"93": {"inputs": {"width": 640, "height": 480}}}
        job = LipsyncJob(
            image_path="image.png",
            audio_path="audio.wav",
            prompt="test",
            negative_prompt="",
            width=1920,
            height=1080,
            output_name="output"
        )

        result = service.prepare_workflow(job, workflow)

        assert result["93"]["inputs"]["width"] == 1920
        assert result["93"]["inputs"]["height"] == 1080

    def test_prepare_updates_steps_and_cfg(self, service):
        """Updates steps and CFG values."""
        workflow = {
            "103": {"inputs": {"value": 4}},
            "105": {"inputs": {"value": 1.0}}
        }
        job = LipsyncJob(
            image_path="image.png",
            audio_path="audio.wav",
            prompt="test",
            negative_prompt="",
            width=1280,
            height=720,
            output_name="output",
            steps=8,
            cfg=2.0
        )

        result = service.prepare_workflow(job, workflow)

        assert result["103"]["inputs"]["value"] == 8
        assert result["105"]["inputs"]["value"] == 2.0

    def test_prepare_updates_output_filename(self, service):
        """Updates output filename prefix."""
        workflow = {"113": {"inputs": {"filename_prefix": ""}}}
        job = LipsyncJob(
            image_path="image.png",
            audio_path="audio.wav",
            prompt="test",
            negative_prompt="",
            width=1280,
            height=720,
            output_name="my_video"
        )

        result = service.prepare_workflow(job, workflow)

        assert result["113"]["inputs"]["filename_prefix"] == "lipsync/my_video"

    def test_prepare_updates_fps(self, service):
        """Updates FPS setting."""
        workflow = {"82": {"inputs": {"fps": 16}}}
        job = LipsyncJob(
            image_path="image.png",
            audio_path="audio.wav",
            prompt="test",
            negative_prompt="",
            width=1280,
            height=720,
            output_name="output",
            fps=24
        )

        result = service.prepare_workflow(job, workflow)

        assert result["82"]["inputs"]["fps"] == 24


class TestGetResolution:
    """Tests for get_resolution method."""

    def test_get_720p(self, service):
        """Get 720p resolution."""
        assert service.get_resolution("720p") == (1280, 720)

    def test_get_1080p(self, service):
        """Get 1080p resolution."""
        assert service.get_resolution("1080p") == (1920, 1080)

    def test_get_480p(self, service):
        """Get 480p resolution."""
        assert service.get_resolution("480p") == (832, 480)

    def test_get_unknown_preset(self, service):
        """Unknown preset returns default 720p."""
        assert service.get_resolution("unknown") == (1280, 720)


class TestGenerateLipsync:
    """Tests for generate_lipsync method."""

    def test_generate_workflow_not_found(self, service, mock_config):
        """Return failure when workflow file not found."""
        job = LipsyncJob(
            image_path="image.png",
            audio_path="audio.wav",
            prompt="test",
            negative_prompt="",
            width=1280,
            height=720,
            output_name="output"
        )

        success, msg = service.generate_lipsync(job)

        assert success is False
        assert "not found" in msg.lower()

    def test_generate_success(self, service, mock_config, mock_api, sample_image, sample_audio, tmp_path):
        """Successfully generate lipsync video."""
        # Create workflow file
        workflow_dir = tmp_path / "workflows"
        workflow_file = workflow_dir / "gcl_wan_2.2_is2v.json"
        workflow_file.write_text(json.dumps({
            "52": {"inputs": {"image": ""}},
            "58": {"inputs": {"audio": ""}}
        }))

        # Create output video
        output_dir = Path(mock_config.get_comfy_root()) / "output" / "lipsync"
        output_video = output_dir / "output_00001.mp4"
        output_video.write_bytes(b"video data")

        job = LipsyncJob(
            image_path=sample_image,
            audio_path=sample_audio,
            prompt="test",
            negative_prompt="",
            width=1280,
            height=720,
            output_name="output"
        )

        with patch.object(service, "_get_api", return_value=mock_api):
            success, result = service.generate_lipsync(job)

        assert success is True

    def test_generate_with_callback(self, service, mock_config, mock_api, sample_image, sample_audio, tmp_path):
        """Progress callback is called during generation."""
        # Create workflow file
        workflow_dir = tmp_path / "workflows"
        workflow_file = workflow_dir / "gcl_wan_2.2_is2v.json"
        workflow_file.write_text(json.dumps({}))

        # Create output video
        output_dir = Path(mock_config.get_comfy_root()) / "output" / "lipsync"
        output_video = output_dir / "output_00001.mp4"
        output_video.write_bytes(b"video data")

        job = LipsyncJob(
            image_path=sample_image,
            audio_path=sample_audio,
            prompt="test",
            negative_prompt="",
            width=1280,
            height=720,
            output_name="output"
        )

        callback = MagicMock()

        with patch.object(service, "_get_api", return_value=mock_api):
            service.generate_lipsync(job, progress_callback=callback)

        assert callback.call_count >= 2

    def test_generate_copy_image_failure(self, service, mock_config, mock_api, tmp_path):
        """Return failure when image copy fails."""
        # Create workflow file
        workflow_dir = tmp_path / "workflows"
        workflow_file = workflow_dir / "gcl_wan_2.2_is2v.json"
        workflow_file.write_text(json.dumps({}))

        job = LipsyncJob(
            image_path="/nonexistent/image.png",
            audio_path="/nonexistent/audio.wav",
            prompt="test",
            negative_prompt="",
            width=1280,
            height=720,
            output_name="output"
        )

        with patch.object(service, "_get_api", return_value=mock_api):
            success, msg = service.generate_lipsync(job)

        assert success is False


class TestConcatenateVideos:
    """Tests for concatenate_videos method."""

    def test_concatenate_empty_list(self, service):
        """Return failure for empty video list."""
        success, msg = service.concatenate_videos([], "/output.mp4")
        assert success is False
        assert "no videos" in msg.lower()

    def test_concatenate_single_video(self, service, tmp_path):
        """Single video is just copied."""
        input_video = tmp_path / "input.mp4"
        input_video.write_bytes(b"video data")
        output_path = str(tmp_path / "output.mp4")

        success, result = service.concatenate_videos([str(input_video)], output_path)

        assert success is True
        assert result == output_path
        assert os.path.exists(output_path)

    def test_concatenate_multiple_videos(self, service, tmp_path):
        """Concatenate multiple videos."""
        videos = []
        for i in range(3):
            video = tmp_path / f"video{i}.mp4"
            video.write_bytes(b"video data")
            videos.append(str(video))

        output_path = str(tmp_path / "output.mp4")
        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            success, result = service.concatenate_videos(videos, output_path)

        assert success is True
        assert result == output_path

    def test_concatenate_ffmpeg_failure(self, service, tmp_path):
        """Return failure when ffmpeg fails."""
        videos = []
        for i in range(2):
            video = tmp_path / f"video{i}.mp4"
            video.write_bytes(b"video data")
            videos.append(str(video))

        output_path = str(tmp_path / "output.mp4")
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Error during concat"

        with patch("subprocess.run", return_value=mock_result):
            success, msg = service.concatenate_videos(videos, output_path)

        assert success is False

    def test_concatenate_exception(self, service, tmp_path):
        """Return failure on exception."""
        videos = []
        for i in range(2):
            video = tmp_path / f"video{i}.mp4"
            video.write_bytes(b"video data")
            videos.append(str(video))

        output_path = str(tmp_path / "output.mp4")

        with patch("subprocess.run", side_effect=Exception("Error")):
            success, msg = service.concatenate_videos(videos, output_path)

        assert success is False


class TestGenerateBatchLipsync:
    """Tests for generate_batch_lipsync method."""

    def test_batch_empty_segments(self, service, sample_image):
        """Return failure for empty segments list."""
        result = service.generate_batch_lipsync(
            base_image_path=sample_image,
            segments=[],
            prompt="test",
            negative_prompt="",
            width=1280,
            height=720,
            workflow_file="workflow.json"
        )

        assert result.success is False
        assert "no segments" in result.errors[0].lower()

    def test_batch_single_segment(self, service, mock_config, mock_api, sample_image, sample_audio, tmp_path):
        """Process single segment."""
        # Create workflow file
        workflow_dir = tmp_path / "workflows"
        workflow_file = workflow_dir / "workflow.json"
        workflow_file.write_text(json.dumps({}))

        # Create output video
        output_dir = Path(mock_config.get_comfy_root()) / "output" / "lipsync"
        output_video = output_dir / "output_00001.mp4"
        output_video.write_bytes(b"video data")

        segments = [
            BatchSegment(
                audio_path=sample_audio,
                start_time=0.0,
                end_time=5.0,
                segment_index=0
            )
        ]

        with patch.object(service, "_get_api", return_value=mock_api):
            with patch.object(service, "generate_lipsync", return_value=(True, str(output_video))):
                result = service.generate_batch_lipsync(
                    base_image_path=sample_image,
                    segments=segments,
                    prompt="test",
                    negative_prompt="",
                    width=1280,
                    height=720,
                    workflow_file="workflow.json"
                )

        assert result.total_segments == 1
        assert result.completed_segments == 1

    def test_batch_with_callback(self, service, mock_config, mock_api, sample_image, sample_audio, tmp_path):
        """Batch calls progress callback."""
        output_dir = Path(mock_config.get_comfy_root()) / "output" / "lipsync"
        output_video = output_dir / "output_00001.mp4"
        output_video.write_bytes(b"video data")

        segments = [
            BatchSegment(audio_path=sample_audio, start_time=0, end_time=5, segment_index=0)
        ]

        callback = MagicMock()

        with patch.object(service, "_get_api", return_value=mock_api):
            with patch.object(service, "generate_lipsync", return_value=(True, str(output_video))):
                service.generate_batch_lipsync(
                    base_image_path=sample_image,
                    segments=segments,
                    prompt="test",
                    negative_prompt="",
                    width=1280,
                    height=720,
                    workflow_file="workflow.json",
                    progress_callback=callback
                )

        assert callback.call_count >= 2


class TestGenerateCharacterImage:
    """Tests for generate_character_image method."""

    def test_generate_image_workflow_not_found(self, service, mock_config):
        """Return failure when workflow not found."""
        success, msg = service.generate_character_image(
            prompt="test",
            negative_prompt="",
            width=1280,
            height=720,
            workflow_file="nonexistent.json"
        )

        assert success is False
        assert "not found" in msg.lower()

    def test_generate_image_success(self, service, mock_config, mock_api, tmp_path):
        """Successfully generate character image."""
        # Create workflow file
        workflow_dir = tmp_path / "workflows"
        workflow_file = workflow_dir / "flux_workflow.json"
        workflow_file.write_text(json.dumps({
            "1": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}, "_meta": {"title": "positive"}},
            "2": {"class_type": "KSampler", "inputs": {"steps": 20, "cfg": 7, "seed": 0}},
            "3": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512}},
        }))

        # Create output image
        output_dir = Path(mock_config.get_comfy_root()) / "output"
        output_image = output_dir / "image_00001.png"
        output_image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        with patch.object(service, "_get_api", return_value=mock_api):
            success, result = service.generate_character_image(
                prompt="test character",
                negative_prompt="blurry",
                width=1280,
                height=720,
                workflow_file="flux_workflow.json"
            )

        assert success is True

    def test_generate_image_with_lora(self, service, mock_config, mock_api, tmp_path):
        """Generate with LoRA applied."""
        # Create workflow file
        workflow_dir = tmp_path / "workflows"
        workflow_file = workflow_dir / "flux_workflow.json"
        workflow_file.write_text(json.dumps({
            "1": {"class_type": "LoraLoader", "inputs": {"lora_name": ""}},
        }))

        # Create output image
        output_dir = Path(mock_config.get_comfy_root()) / "output"
        output_image = output_dir / "image_00001.png"
        output_image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        with patch.object(service, "_get_api", return_value=mock_api):
            success, result = service.generate_character_image(
                prompt="test",
                negative_prompt="",
                width=1280,
                height=720,
                workflow_file="flux_workflow.json",
                lora_name="my_character"
            )

        assert success is True

    def test_generate_image_queue_failure(self, service, mock_config, mock_api, tmp_path):
        """Return failure when queue fails."""
        workflow_dir = tmp_path / "workflows"
        workflow_file = workflow_dir / "workflow.json"
        workflow_file.write_text(json.dumps({}))

        mock_api.queue_prompt.side_effect = Exception("Queue failed")

        with patch.object(service, "_get_api", return_value=mock_api):
            success, msg = service.generate_character_image(
                prompt="test",
                negative_prompt="",
                width=1280,
                height=720,
                workflow_file="workflow.json"
            )

        assert success is False
        assert "queue" in msg.lower()
