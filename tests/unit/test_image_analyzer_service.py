"""Tests for ImageAnalyzerService - AI-powered image analysis via ComfyUI Florence-2."""
import os
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, PropertyMock
from dataclasses import asdict

from services.image_analyzer_service import ImageAnalyzerService, AnalysisResult


@pytest.fixture
def mock_config(tmp_path):
    """Create mock ConfigManager."""
    config = MagicMock()
    config.get_comfy_url.return_value = "http://127.0.0.1:8188"
    config.get_comfy_root.return_value = str(tmp_path / "comfyui")
    # Create the comfyui directory
    (tmp_path / "comfyui").mkdir()
    (tmp_path / "comfyui" / "input").mkdir()
    (tmp_path / "comfyui" / "output").mkdir()
    return config


@pytest.fixture
def mock_api():
    """Create mock ComfyUIAPI."""
    api = MagicMock()
    api.test_connection.return_value = {"connected": True}
    api.load_workflow.return_value = {"1": {"class_type": "LoadImage", "inputs": {"image": ""}}}
    api.queue_prompt.return_value = "prompt-123"
    api.monitor_progress.return_value = {"status": "success"}
    api.get_history.return_value = {
        "outputs": {
            "4": {"text": "A short caption"},
            "12": {"text": "A more detailed caption describing the image"}
        }
    }
    return api


@pytest.fixture
def service(mock_config, mock_api):
    """Create ImageAnalyzerService with mocks."""
    with patch("services.image_analyzer_service.ComfyUIAPI", return_value=mock_api):
        svc = ImageAnalyzerService(config=mock_config)
        svc.api = mock_api
        return svc


@pytest.fixture
def sample_image(tmp_path):
    """Create a sample image file."""
    image_path = tmp_path / "test_image.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    return str(image_path)


class TestAnalysisResult:
    """Tests for AnalysisResult dataclass."""

    def test_analysis_result_success(self):
        """Create successful analysis result."""
        result = AnalysisResult(
            success=True,
            caption="A beautiful sunset",
            description="Sunset scene"
        )
        assert result.success is True
        assert result.caption == "A beautiful sunset"
        assert result.description == "Sunset scene"
        assert result.error is None

    def test_analysis_result_failure(self):
        """Create failed analysis result."""
        result = AnalysisResult(
            success=False,
            caption="",
            error="Connection failed"
        )
        assert result.success is False
        assert result.caption == ""
        assert result.error == "Connection failed"

    def test_analysis_result_default_description(self):
        """Default description is empty string."""
        result = AnalysisResult(success=True, caption="test")
        assert result.description == ""

    def test_analysis_result_to_dict(self):
        """Can convert to dictionary."""
        result = AnalysisResult(
            success=True,
            caption="caption",
            description="desc",
            error=None
        )
        d = asdict(result)
        assert d["success"] is True
        assert d["caption"] == "caption"
        assert d["description"] == "desc"


class TestImageAnalyzerServiceInit:
    """Tests for ImageAnalyzerService initialization."""

    def test_init_with_config(self, mock_config):
        """Initialize with provided config."""
        with patch("services.image_analyzer_service.ComfyUIAPI"):
            service = ImageAnalyzerService(config=mock_config)
            assert service.config == mock_config

    def test_init_creates_api(self, mock_config):
        """Initialize creates ComfyUIAPI."""
        with patch("services.image_analyzer_service.ComfyUIAPI") as MockAPI:
            service = ImageAnalyzerService(config=mock_config)
            MockAPI.assert_called_once_with("http://127.0.0.1:8188")

    def test_init_default_config(self):
        """Initialize creates default ConfigManager if not provided."""
        with patch("services.image_analyzer_service.ComfyUIAPI"):
            with patch("services.image_analyzer_service.ConfigManager") as MockConfig:
                MockConfig.return_value.get_comfy_url.return_value = "http://localhost:8188"
                service = ImageAnalyzerService()
                MockConfig.assert_called_once()

    def test_workflow_file_path(self):
        """WORKFLOW_FILE constant is set."""
        assert ImageAnalyzerService.WORKFLOW_FILE == "config/workflow_templates/gca_florence2_caption.json"


class TestIsAvailable:
    """Tests for is_available method."""

    def test_is_available_when_connected(self, service, mock_api):
        """Returns True when ComfyUI is connected."""
        mock_api.test_connection.return_value = {"connected": True}
        assert service.is_available() is True

    def test_is_not_available_when_disconnected(self, service, mock_api):
        """Returns False when ComfyUI is not connected."""
        mock_api.test_connection.return_value = {"connected": False}
        assert service.is_available() is False

    def test_is_not_available_on_exception(self, service, mock_api):
        """Returns False when connection check raises exception."""
        mock_api.test_connection.side_effect = Exception("Connection error")
        assert service.is_available() is False

    def test_is_not_available_when_key_missing(self, service, mock_api):
        """Returns False when 'connected' key is missing."""
        mock_api.test_connection.return_value = {}
        assert service.is_available() is False


class TestLoadWorkflow:
    """Tests for _load_workflow method."""

    def test_load_workflow_returns_copy(self, service, mock_api):
        """Returns a copy of the workflow."""
        workflow = {"1": {"class_type": "LoadImage"}}
        mock_api.load_workflow.return_value = workflow

        result = service._load_workflow()

        # Should be equal but not the same object
        assert result == workflow
        assert result is not workflow

    def test_load_workflow_caches_result(self, service, mock_api):
        """Workflow is cached after first load."""
        workflow = {"1": {"class_type": "LoadImage"}}
        mock_api.load_workflow.return_value = workflow

        result1 = service._load_workflow()
        result2 = service._load_workflow()

        # Should only load once
        mock_api.load_workflow.assert_called_once()
        assert result1 == result2

    def test_load_workflow_returns_deep_copy(self, service, mock_api):
        """Returns deep copy so modifications don't affect cache."""
        workflow = {"1": {"inputs": {"image": "original.png"}}}
        mock_api.load_workflow.return_value = workflow

        result1 = service._load_workflow()
        result1["1"]["inputs"]["image"] = "modified.png"

        result2 = service._load_workflow()

        # Second copy should still have original value
        assert result2["1"]["inputs"]["image"] == "original.png"


class TestUploadImage:
    """Tests for _upload_image method."""

    def test_upload_image_copies_to_input_dir(self, service, mock_config, sample_image):
        """Image is copied to ComfyUI input directory."""
        comfy_root = mock_config.get_comfy_root()
        input_dir = Path(comfy_root) / "input"

        filename = service._upload_image(sample_image)

        # Check file was copied
        assert (input_dir / filename).exists()
        assert filename.startswith("analyze_")
        assert filename.endswith("_test_image.png")

    def test_upload_image_creates_input_dir(self, mock_config, sample_image):
        """Creates input directory if it doesn't exist."""
        # Remove the input directory
        comfy_root = mock_config.get_comfy_root()
        input_dir = Path(comfy_root) / "input"
        input_dir.rmdir()

        with patch("services.image_analyzer_service.ComfyUIAPI"):
            service = ImageAnalyzerService(config=mock_config)

        filename = service._upload_image(sample_image)

        assert input_dir.exists()
        assert (input_dir / filename).exists()

    def test_upload_image_unique_filename(self, service, mock_config, sample_image):
        """Uploaded filename includes timestamp for uniqueness."""
        filename = service._upload_image(sample_image)

        # Format: analyze_{timestamp}_{original_name}
        parts = filename.split("_")
        assert parts[0] == "analyze"
        assert parts[1].isdigit()  # timestamp


class TestCleanupImage:
    """Tests for _cleanup_image method."""

    def test_cleanup_removes_file(self, service, mock_config, sample_image):
        """Cleanup removes file from input directory."""
        # First upload the image
        filename = service._upload_image(sample_image)
        comfy_root = mock_config.get_comfy_root()
        input_path = Path(comfy_root) / "input" / filename

        assert input_path.exists()

        # Clean up
        service._cleanup_image(filename)

        assert not input_path.exists()

    def test_cleanup_nonexistent_file(self, service, mock_config):
        """Cleanup handles non-existent file gracefully."""
        # Should not raise exception
        service._cleanup_image("nonexistent_file.png")

    def test_cleanup_handles_exception(self, service, mock_config):
        """Cleanup handles permission errors gracefully."""
        with patch("os.path.exists", return_value=True):
            with patch("os.remove", side_effect=PermissionError("Access denied")):
                # Should not raise exception
                service._cleanup_image("test.png")


class TestExtractTextValue:
    """Tests for _extract_text_value method."""

    def test_extract_from_string(self, service):
        """Extract text from string value."""
        result = service._extract_text_value("hello world")
        assert result == "hello world"

    def test_extract_from_list_of_strings(self, service):
        """Extract text from list with string items."""
        result = service._extract_text_value(["first item", "second item"])
        assert result == "first item"

    def test_extract_from_list_of_dicts(self, service):
        """Extract text from list with dict items."""
        result = service._extract_text_value([{"text": "extracted text"}])
        assert result == "extracted text"

    def test_extract_from_dict_with_text(self, service):
        """Extract text from dict with text key."""
        result = service._extract_text_value({"text": "dict text"})
        assert result == "dict text"

    def test_extract_from_dict_with_filename(self, service, mock_config, tmp_path):
        """Extract text from dict with filename reference."""
        # Create a text file in ComfyUI output
        comfy_root = mock_config.get_comfy_root()
        output_dir = Path(comfy_root) / "output"
        text_file = output_dir / "caption.txt"
        text_file.write_text("Caption from file")

        result = service._extract_text_value({
            "filename": "caption.txt",
            "type": "output"
        })

        assert result == "Caption from file"

    def test_extract_empty_list(self, service):
        """Extract from empty list returns None."""
        result = service._extract_text_value([])
        assert result is None

    def test_extract_none(self, service):
        """Extract from None returns None."""
        result = service._extract_text_value(None)
        assert result is None

    def test_extract_number(self, service):
        """Extract from number returns None."""
        result = service._extract_text_value(123)
        assert result is None


class TestExtractCaptionsFromHistory:
    """Tests for _extract_captions_from_history method."""

    def test_extract_from_node_ids(self, service):
        """Extract captions from known node IDs (4=description, 12=prompt)."""
        history = {
            "outputs": {
                "4": {"text": "Short description"},
                "12": {"text": "Detailed prompt caption"}
            }
        }

        description, prompt = service._extract_captions_from_history(history)

        assert description == "Short description"
        assert prompt == "Detailed prompt caption"

    def test_extract_fallback_by_length(self, service):
        """Falls back to sorting by length when node IDs don't match."""
        history = {
            "outputs": {
                "99": {"text": "Short"},
                "100": {"text": "This is a much longer detailed caption for the image"}
            }
        }

        description, prompt = service._extract_captions_from_history(history)

        # Shorter text should be description, longer should be prompt
        assert description == "Short"
        assert prompt == "This is a much longer detailed caption for the image"

    def test_extract_single_output(self, service):
        """Single output is used for both description and prompt."""
        history = {
            "outputs": {
                "99": {"text": "Only one caption"}
            }
        }

        description, prompt = service._extract_captions_from_history(history)

        assert description == "Only one caption"
        assert prompt == "Only one caption"

    def test_extract_empty_history(self, service):
        """Empty history returns None for both."""
        description, prompt = service._extract_captions_from_history({})
        assert description is None
        assert prompt is None

    def test_extract_none_history(self, service):
        """None history returns None for both."""
        description, prompt = service._extract_captions_from_history(None)
        assert description is None
        assert prompt is None

    def test_extract_no_outputs(self, service):
        """History without outputs returns None for both."""
        history = {"status": "complete"}
        description, prompt = service._extract_captions_from_history(history)
        assert description is None
        assert prompt is None

    def test_extract_list_text_format(self, service):
        """Handle text as list of strings."""
        history = {
            "outputs": {
                "4": {"text": ["Description text"]},
                "12": {"text": ["Prompt text"]}
            }
        }

        description, prompt = service._extract_captions_from_history(history)

        assert description == "Description text"
        assert prompt == "Prompt text"


class TestReadTextFileFromComfy:
    """Tests for _read_text_file_from_comfy method."""

    def test_read_from_output_folder(self, service, mock_config):
        """Read text file from output folder."""
        comfy_root = mock_config.get_comfy_root()
        output_dir = Path(comfy_root) / "output"
        text_file = output_dir / "caption.txt"
        text_file.write_text("Caption content")

        result = service._read_text_file_from_comfy({
            "filename": "caption.txt",
            "type": "output"
        })

        assert result == "Caption content"

    def test_read_from_input_folder(self, service, mock_config):
        """Read text file from input folder."""
        comfy_root = mock_config.get_comfy_root()
        input_dir = Path(comfy_root) / "input"
        text_file = input_dir / "prompt.txt"
        text_file.write_text("Input prompt")

        result = service._read_text_file_from_comfy({
            "filename": "prompt.txt",
            "type": "input"
        })

        assert result == "Input prompt"

    def test_read_from_subfolder(self, service, mock_config):
        """Read text file from subfolder."""
        comfy_root = mock_config.get_comfy_root()
        subfolder = Path(comfy_root) / "output" / "captions"
        subfolder.mkdir()
        text_file = subfolder / "caption.txt"
        text_file.write_text("Subfolder content")

        result = service._read_text_file_from_comfy({
            "filename": "caption.txt",
            "subfolder": "captions",
            "type": "output"
        })

        assert result == "Subfolder content"

    def test_read_nonexistent_file(self, service, mock_config):
        """Return None for non-existent file."""
        result = service._read_text_file_from_comfy({
            "filename": "nonexistent.txt",
            "type": "output"
        })

        assert result is None

    def test_read_handles_exception(self, service, mock_config):
        """Return None on read error."""
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            result = service._read_text_file_from_comfy({
                "filename": "test.txt",
                "type": "output"
            })
            # Should return None, not raise
            assert result is None


class TestAnalyzeImage:
    """Tests for analyze_image method."""

    def test_analyze_image_not_found(self, service):
        """Return error for non-existent image."""
        result = service.analyze_image("/nonexistent/image.png")

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_analyze_image_success(self, service, mock_api, sample_image, mock_config):
        """Successful image analysis."""
        mock_api.get_history.return_value = {
            "outputs": {
                "4": {"text": "Short caption"},
                "12": {"text": "Detailed prompt caption for the image"}
            }
        }

        result = service.analyze_image(sample_image)

        assert result.success is True
        assert result.caption == "Detailed prompt caption for the image"
        assert result.description == "Short caption"
        assert result.error is None

    def test_analyze_image_calls_callback(self, service, mock_api, sample_image, mock_config):
        """Progress callback is called during analysis."""
        mock_api.get_history.return_value = {
            "outputs": {
                "4": {"text": "caption"}
            }
        }

        callback = MagicMock()
        service.analyze_image(sample_image, callback=callback)

        # Callback should be called multiple times with progress
        assert callback.call_count >= 2

    def test_analyze_image_workflow_failure(self, service, mock_api, sample_image, mock_config):
        """Handle workflow execution failure."""
        mock_api.monitor_progress.return_value = {
            "status": "error",
            "error": "Out of VRAM"
        }

        result = service.analyze_image(sample_image)

        assert result.success is False
        assert "VRAM" in result.error or "error" in result.error.lower()

    def test_analyze_image_no_caption_extracted(self, service, mock_api, sample_image, mock_config):
        """Handle case where no caption is extracted."""
        mock_api.get_history.return_value = {"outputs": {}}

        result = service.analyze_image(sample_image)

        assert result.success is False
        assert "extract" in result.error.lower() or "caption" in result.error.lower()

    def test_analyze_image_exception(self, service, mock_api, sample_image, mock_config):
        """Handle exception during analysis."""
        mock_api.queue_prompt.side_effect = Exception("API error")

        result = service.analyze_image(sample_image)

        assert result.success is False
        assert "API error" in result.error

    def test_analyze_image_cleanup_on_success(self, service, mock_api, sample_image, mock_config):
        """Uploaded image is cleaned up after success."""
        mock_api.get_history.return_value = {
            "outputs": {"4": {"text": "caption"}}
        }

        with patch.object(service, "_cleanup_image") as mock_cleanup:
            service.analyze_image(sample_image)
            mock_cleanup.assert_called_once()

    def test_analyze_image_cleanup_on_failure(self, service, mock_api, sample_image, mock_config):
        """Uploaded image is cleaned up even on failure."""
        mock_api.queue_prompt.side_effect = Exception("Error")

        with patch.object(service, "_cleanup_image") as mock_cleanup:
            service.analyze_image(sample_image)
            mock_cleanup.assert_called_once()

    def test_analyze_image_updates_workflow(self, service, mock_api, sample_image, mock_config):
        """Workflow is updated with uploaded image filename."""
        mock_api.load_workflow.return_value = {
            "1": {
                "class_type": "LoadImage",
                "inputs": {"image": "placeholder.png"}
            }
        }
        mock_api.get_history.return_value = {
            "outputs": {"4": {"text": "caption"}}
        }

        service.analyze_image(sample_image)

        # Check that queue_prompt was called with modified workflow
        call_args = mock_api.queue_prompt.call_args[0][0]
        assert call_args["1"]["inputs"]["image"].startswith("analyze_")


class TestAnalyzeBatch:
    """Tests for analyze_batch method."""

    def test_analyze_batch_empty_list(self, service):
        """Analyze empty list returns empty results."""
        results = service.analyze_batch([])
        assert results == []

    def test_analyze_batch_single_image(self, service, mock_api, sample_image, mock_config):
        """Analyze single image in batch."""
        mock_api.get_history.return_value = {
            "outputs": {"4": {"text": "Caption"}}
        }

        results = service.analyze_batch([sample_image])

        assert len(results) == 1
        assert results[0].success is True

    def test_analyze_batch_multiple_images(self, service, mock_api, tmp_path, mock_config):
        """Analyze multiple images in batch."""
        # Create multiple images
        images = []
        for i in range(3):
            img_path = tmp_path / f"image{i}.png"
            img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
            images.append(str(img_path))

        mock_api.get_history.return_value = {
            "outputs": {"4": {"text": "Caption"}}
        }

        results = service.analyze_batch(images)

        assert len(results) == 3
        assert all(r.success for r in results)

    def test_analyze_batch_with_callback(self, service, mock_api, sample_image, mock_config):
        """Batch analysis calls callback for each image."""
        mock_api.get_history.return_value = {
            "outputs": {"4": {"text": "Caption"}}
        }

        callback = MagicMock()
        service.analyze_batch([sample_image], callback=callback)

        # Callback should be called with progress info
        assert callback.call_count >= 2

    def test_analyze_batch_mixed_results(self, service, mock_api, tmp_path, mock_config):
        """Batch with some failures returns mixed results."""
        # Create one valid image
        valid_image = tmp_path / "valid.png"
        valid_image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        # One non-existent image
        images = [str(valid_image), "/nonexistent/image.png"]

        mock_api.get_history.return_value = {
            "outputs": {"4": {"text": "Caption"}}
        }

        results = service.analyze_batch(images)

        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is False

    def test_analyze_batch_callback_shows_progress(self, service, mock_api, tmp_path, mock_config):
        """Callback receives correct progress information."""
        images = []
        for i in range(2):
            img_path = tmp_path / f"img{i}.png"
            img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
            images.append(str(img_path))

        mock_api.get_history.return_value = {
            "outputs": {"4": {"text": "Caption"}}
        }

        callback = MagicMock()
        service.analyze_batch(images, callback=callback)

        # Check that callback was called with index and total
        calls = callback.call_args_list
        # Should have calls for each image (start and end)
        assert any(call[0][0] == 0 and call[0][1] == 2 for call in calls)  # First image
        assert any(call[0][0] == 1 and call[0][1] == 2 for call in calls)  # Second image
