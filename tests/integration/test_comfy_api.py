"""Integration tests for ComfyUIAPI"""
import json
from unittest.mock import Mock, patch, MagicMock

import pytest

from infrastructure.comfy_api import ComfyUIAPI
from domain.exceptions import WorkflowLoadError, WorkflowExecutionError


class TestComfyAPIConnection:
    """Test ComfyUIAPI connection methods"""

    def test_connection_success(self):
        """Should successfully connect to ComfyUI"""
        api = ComfyUIAPI("http://127.0.0.1:8188")

        with patch.object(ComfyUIAPI, "_get_request", return_value={"system": {"ram_used": 1000, "ram_total": 16000}}):
            result = api.test_connection()

        # Assert
        assert result["connected"] is True
        assert result["system"]["system"]["ram_used"] == 1000

    def test_connection_failure(self):
        """Should handle connection failure"""
        api = ComfyUIAPI("http://127.0.0.1:8188")

        with patch.object(ComfyUIAPI, "_get_request", side_effect=Exception("Connection refused")):
            result = api.test_connection()

        # Assert
        assert result["connected"] is False
        assert result["error"]

    def test_connection_timeout(self):
        """Should handle connection timeout"""
        api = ComfyUIAPI("http://127.0.0.1:8188")

        with patch.object(ComfyUIAPI, "_get_request", side_effect=Exception("Timeout")):
            result = api.test_connection()

        # Assert
        assert result["connected"] is False


class TestComfyAPIWorkflowOperations:
    """Test workflow loading and manipulation"""

    @pytest.mark.integration
    def test_load_workflow_success(self, tmp_path, sample_flux_workflow):
        """Should load workflow from JSON file"""
        # Arrange
        workflow_file = tmp_path / "test_workflow.json"
        with open(workflow_file, "w") as f:
            json.dump(sample_flux_workflow, f)
        api = ComfyUIAPI("http://127.0.0.1:8188")

        # Act
        workflow = api.load_workflow(str(workflow_file))

        # Assert
        assert "1" in workflow
        assert workflow["1"]["class_type"] == "CLIPTextEncode"

    @pytest.mark.integration
    def test_load_workflow_file_not_found(self):
        """Should raise error if workflow file not found"""
        # Arrange
        api = ComfyUIAPI("http://127.0.0.1:8188")

        # Act & Assert
        with pytest.raises(WorkflowLoadError):
            api.load_workflow("/nonexistent/workflow.json")

    @pytest.mark.integration
    def test_load_workflow_invalid_json(self, tmp_path):
        """Should raise error for invalid JSON"""
        # Arrange
        workflow_file = tmp_path / "invalid.json"
        workflow_file.write_text("{broken json")
        api = ComfyUIAPI("http://127.0.0.1:8188")

        # Act & Assert
        with pytest.raises(WorkflowLoadError):
            api.load_workflow(str(workflow_file))


class TestComfyAPIWorkflowUpdates:
    """Test workflow parameter updates"""

    @pytest.mark.integration
    def test_update_prompt(self, sample_flux_workflow):
        """Should update prompt in CLIPTextEncode node"""
        # Arrange
        api = ComfyUIAPI("http://127.0.0.1:8188")

        # Act
        updated = api.update_workflow_params(
            sample_flux_workflow,
            prompt="new test prompt"
        )

        # Assert
        assert updated["1"]["inputs"]["text"] == "new test prompt"

    @pytest.mark.integration
    def test_update_seed(self, sample_flux_workflow):
        """Should update seed in KSampler node"""
        # Arrange
        api = ComfyUIAPI("http://127.0.0.1:8188")

        # Act
        updated = api.update_workflow_params(
            sample_flux_workflow,
            seed=9999
        )

        # Assert
        assert updated["4"]["inputs"]["seed"] == 9999

    @pytest.mark.integration
    def test_update_resolution(self, sample_flux_workflow):
        """Should update width/height in EmptyLatentImage node"""
        # Arrange
        api = ComfyUIAPI("http://127.0.0.1:8188")

        # Act
        updated = api.update_workflow_params(
            sample_flux_workflow,
            width=1920,
            height=1080
        )

        # Assert
        assert updated["3"]["inputs"]["width"] == 1920
        assert updated["3"]["inputs"]["height"] == 1080

    @pytest.mark.integration
    def test_update_filename_prefix(self, sample_flux_workflow):
        """Should update filename_prefix in SaveImage node"""
        # Arrange
        api = ComfyUIAPI("http://127.0.0.1:8188")

        # Act
        updated = api.update_workflow_params(
            sample_flux_workflow,
            filename_prefix="custom_output"
        )

        # Assert
        assert updated["6"]["inputs"]["filename_prefix"] == "custom_output"

    @pytest.mark.integration
    def test_update_multiple_params(self, sample_flux_workflow):
        """Should update multiple parameters at once"""
        # Arrange
        api = ComfyUIAPI("http://127.0.0.1:8188")

        # Act
        updated = api.update_workflow_params(
            sample_flux_workflow,
            prompt="multi test",
            seed=5555,
            width=1280,
            height=720,
            filename_prefix="multi_output"
        )

        # Assert
        assert updated["1"]["inputs"]["text"] == "multi test"
        assert updated["4"]["inputs"]["seed"] == 5555
        assert updated["3"]["inputs"]["width"] == 1280
        assert updated["3"]["inputs"]["height"] == 720
        assert updated["6"]["inputs"]["filename_prefix"] == "multi_output"

    @pytest.mark.integration
    def test_update_preserves_original_workflow(self, sample_flux_workflow):
        """Should not modify original workflow dict"""
        # Arrange
        api = ComfyUIAPI("http://127.0.0.1:8188")
        original_prompt = sample_flux_workflow["1"]["inputs"]["text"]

        # Act
        updated = api.update_workflow_params(
            sample_flux_workflow,
            prompt="modified prompt"
        )

        # Assert
        assert sample_flux_workflow["1"]["inputs"]["text"] == original_prompt
        assert updated["1"]["inputs"]["text"] == "modified prompt"


class TestComfyAPIWanWorkflows:
    """Test Wan-specific workflow updates"""

    @pytest.mark.integration
    def test_update_startframe(self, sample_wan_workflow):
        """Should update startframe in LoadImage node"""
        # Arrange
        api = ComfyUIAPI("http://127.0.0.1:8188")

        # Act
        updated = api.update_workflow_params(
            sample_wan_workflow,
            startframe_path="/path/to/startframe.png"
        )

        # Assert
        assert updated["1"]["inputs"]["image"] == "/path/to/startframe.png"

    @pytest.mark.integration
    def test_update_num_frames(self, sample_wan_workflow):
        """Should update num_frames in HunyuanVideoSampler"""
        # Arrange
        api = ComfyUIAPI("http://127.0.0.1:8188")

        # Act
        updated = api.update_workflow_params(
            sample_wan_workflow,
            num_frames=120
        )

        # Assert
        assert updated["3"]["inputs"]["num_frames"] == 120


class TestComfyAPIPromptQueue:
    """Test prompt queuing functionality"""

    def test_queue_prompt_success(self, sample_flux_workflow):
        """Should successfully queue prompt"""
        api = ComfyUIAPI("http://127.0.0.1:8188")

        with patch.object(ComfyUIAPI, "_post_request", return_value={"prompt_id": "test-prompt-123"}):
            prompt_id = api.queue_prompt(sample_flux_workflow)

        # Assert
        assert prompt_id == "test-prompt-123"

    def test_queue_prompt_failure(self, sample_flux_workflow):
        """Should handle queue failure"""
        api = ComfyUIAPI("http://127.0.0.1:8188")

        # Act & Assert
        with patch.object(ComfyUIAPI, "_post_request", side_effect=Exception("Invalid workflow")):
            with pytest.raises(WorkflowExecutionError):
                api.queue_prompt(sample_flux_workflow)


class TestComfyAPIOutputImages:
    """Test output image retrieval"""

    def test_get_output_images_success(self):
        """Should retrieve output images for prompt"""
        api = ComfyUIAPI("http://127.0.0.1:8188")

        with patch.object(ComfyUIAPI, "_get_image", return_value=b"fake-bytes"), \
             patch.object(
                 ComfyUIAPI,
                 "get_history",
                 return_value={
                     "outputs": {
                         "6": {
                             "images": [
                                 {"filename": "output_00001_.png", "subfolder": "", "type": "output"}
                             ]
                         }
                     }
                 },
             ):
            images = api.get_output_images("test-prompt-123")

        # Assert
        assert len(images) > 0
        assert "output_00001_.png" in images[0]

    def test_get_output_images_no_outputs(self):
        """Should handle case with no output images"""
        api = ComfyUIAPI("http://127.0.0.1:8188")

        with patch.object(ComfyUIAPI, "get_history", return_value={"outputs": {}}):
            images = api.get_output_images("test-prompt-123")

        # Assert
        assert images == []


class TestComfyAPIProgressMonitoring:
    """Test WebSocket progress monitoring"""

    def test_monitor_progress_callback(self, sample_flux_workflow):
        """Should call progress callback during monitoring"""
        # Arrange
        api = ComfyUIAPI("http://127.0.0.1:8188")
        callback_calls = []

        def mock_callback(progress, status):
            callback_calls.append((progress, status))

        mock_ws = MagicMock()
        mock_ws.recv.side_effect = ['{"type": "execution_success"}']

        with patch("infrastructure.comfy_api.client.websocket.create_connection", return_value=mock_ws), \
             patch.object(ComfyUIAPI, "get_output_images", return_value=[]):
            result = api.monitor_progress("prompt-123", callback=mock_callback, timeout=1)

        assert result["status"] == "success"
        assert callback_calls  # callback was invoked


class TestComfyAPIErrorHandling:
    """Test error handling"""

    @pytest.mark.integration
    def test_handles_malformed_workflow(self):
        """Should handle malformed workflow gracefully"""
        # Arrange
        api = ComfyUIAPI("http://127.0.0.1:8188")
        malformed = {"not": "a valid workflow"}

        # Act
        result = api.update_workflow_params(malformed, prompt="test")

        # Assert - should not crash, just return modified dict
        assert "not" in result

    def test_handles_server_error(self, sample_flux_workflow):
        """Should handle server errors gracefully"""
        api = ComfyUIAPI("http://127.0.0.1:8188")

        # Act & Assert
        with patch.object(ComfyUIAPI, "_post_request", side_effect=Exception("Internal Server Error")):
            with pytest.raises(WorkflowExecutionError):
                api.queue_prompt(sample_flux_workflow)


class TestComfyAPIIntegrationWorkflow:
    """End-to-end integration tests"""

    def test_full_workflow_generation(self, tmp_path, sample_flux_workflow):
        """Test complete workflow: load -> update -> queue"""
        # Arrange - Save workflow to file
        workflow_file = tmp_path / "workflow.json"
        with open(workflow_file, "w") as f:
            json.dump(sample_flux_workflow, f)

        api = ComfyUIAPI("http://127.0.0.1:8188")

        # Act - Load workflow
        workflow = api.load_workflow(str(workflow_file))

        # Act - Update parameters
        updated = api.update_workflow_params(
            workflow,
            prompt="integration test prompt",
            seed=12345,
            width=1920,
            height=1080
        )

        with patch.object(ComfyUIAPI, "_post_request", return_value={"prompt_id": "integration-test-123"}):
            prompt_id = api.queue_prompt(updated)

        # Assert
        assert prompt_id == "integration-test-123"
        assert updated["1"]["inputs"]["text"] == "integration test prompt"
        assert updated["4"]["inputs"]["seed"] == 12345
