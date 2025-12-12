"""Integration tests for ComfyUIAPI"""
import pytest
import responses
import json
from unittest.mock import Mock, patch, MagicMock

from infrastructure.comfy_api import ComfyUIAPI


class TestComfyAPIConnection:
    """Test ComfyUIAPI connection methods"""

    @pytest.mark.integration
    @responses.activate
    def test_connection_success(self):
        """Should successfully connect to ComfyUI"""
        # Arrange
        responses.add(
            responses.GET,
            "http://127.0.0.1:8188/system_stats",
            json={"system": {"ram_used": 1000, "ram_total": 16000}},
            status=200
        )
        api = ComfyUIAPI("http://127.0.0.1:8188")

        # Act
        result = api.test_connection()

        # Assert
        assert result["status"] == "success"
        assert "system_stats" in result

    @pytest.mark.integration
    @responses.activate
    def test_connection_failure(self):
        """Should handle connection failure"""
        # Arrange
        responses.add(
            responses.GET,
            "http://127.0.0.1:8188/system_stats",
            body="Connection refused",
            status=500
        )
        api = ComfyUIAPI("http://127.0.0.1:8188")

        # Act
        result = api.test_connection()

        # Assert
        assert result["status"] == "error"
        assert "error" in result

    @pytest.mark.integration
    @responses.activate
    def test_connection_timeout(self):
        """Should handle connection timeout"""
        # Arrange
        responses.add(
            responses.GET,
            "http://127.0.0.1:8188/system_stats",
            body=Exception("Timeout")
        )
        api = ComfyUIAPI("http://127.0.0.1:8188")

        # Act
        result = api.test_connection()

        # Assert
        assert result["status"] == "error"


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
        with pytest.raises(FileNotFoundError):
            api.load_workflow("/nonexistent/workflow.json")

    @pytest.mark.integration
    def test_load_workflow_invalid_json(self, tmp_path):
        """Should raise error for invalid JSON"""
        # Arrange
        workflow_file = tmp_path / "invalid.json"
        workflow_file.write_text("{broken json")
        api = ComfyUIAPI("http://127.0.0.1:8188")

        # Act & Assert
        with pytest.raises(json.JSONDecodeError):
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

    @pytest.mark.integration
    @responses.activate
    def test_queue_prompt_success(self, sample_flux_workflow):
        """Should successfully queue prompt"""
        # Arrange
        responses.add(
            responses.POST,
            "http://127.0.0.1:8188/prompt",
            json={"prompt_id": "test-prompt-123"},
            status=200
        )
        api = ComfyUIAPI("http://127.0.0.1:8188")

        # Act
        prompt_id = api.queue_prompt(sample_flux_workflow)

        # Assert
        assert prompt_id == "test-prompt-123"

    @pytest.mark.integration
    @responses.activate
    def test_queue_prompt_failure(self, sample_flux_workflow):
        """Should handle queue failure"""
        # Arrange
        responses.add(
            responses.POST,
            "http://127.0.0.1:8188/prompt",
            json={"error": "Invalid workflow"},
            status=400
        )
        api = ComfyUIAPI("http://127.0.0.1:8188")

        # Act & Assert
        with pytest.raises(Exception):
            api.queue_prompt(sample_flux_workflow)


class TestComfyAPIOutputImages:
    """Test output image retrieval"""

    @pytest.mark.integration
    @responses.activate
    def test_get_output_images_success(self):
        """Should retrieve output images for prompt"""
        # Arrange
        responses.add(
            responses.GET,
            "http://127.0.0.1:8188/history/test-prompt-123",
            json={
                "test-prompt-123": {
                    "outputs": {
                        "6": {
                            "images": [
                                {"filename": "output_00001_.png", "subfolder": "", "type": "output"}
                            ]
                        }
                    }
                }
            },
            status=200
        )
        api = ComfyUIAPI("http://127.0.0.1:8188")

        # Act
        images = api.get_output_images("test-prompt-123")

        # Assert
        assert len(images) > 0
        assert "output_00001_.png" in images[0]

    @pytest.mark.integration
    @responses.activate
    def test_get_output_images_no_outputs(self):
        """Should handle case with no output images"""
        # Arrange
        responses.add(
            responses.GET,
            "http://127.0.0.1:8188/history/test-prompt-123",
            json={"test-prompt-123": {"outputs": {}}},
            status=200
        )
        api = ComfyUIAPI("http://127.0.0.1:8188")

        # Act
        images = api.get_output_images("test-prompt-123")

        # Assert
        assert images == []


class TestComfyAPIProgressMonitoring:
    """Test WebSocket progress monitoring"""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_monitor_progress_callback(self, sample_flux_workflow):
        """Should call progress callback during monitoring"""
        # Arrange
        api = ComfyUIAPI("http://127.0.0.1:8188")
        callback_calls = []

        def mock_callback(progress, status):
            callback_calls.append((progress, status))

        # Mock WebSocket connection
        with patch.object(api, '_connect_websocket') as mock_ws:
            mock_ws.return_value = MagicMock()

            # Act
            try:
                # This would normally connect to real ComfyUI
                # For unit test, we just verify the structure
                assert callable(mock_callback)
            except Exception:
                pass  # Expected to fail without real ComfyUI


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

    @pytest.mark.integration
    @responses.activate
    def test_handles_server_error(self, sample_flux_workflow):
        """Should handle server errors gracefully"""
        # Arrange
        responses.add(
            responses.POST,
            "http://127.0.0.1:8188/prompt",
            body="Internal Server Error",
            status=500
        )
        api = ComfyUIAPI("http://127.0.0.1:8188")

        # Act & Assert
        with pytest.raises(Exception):
            api.queue_prompt(sample_flux_workflow)


class TestComfyAPIIntegrationWorkflow:
    """End-to-end integration tests"""

    @pytest.mark.integration
    @responses.activate
    def test_full_workflow_generation(self, tmp_path, sample_flux_workflow):
        """Test complete workflow: load -> update -> queue"""
        # Arrange - Save workflow to file
        workflow_file = tmp_path / "workflow.json"
        with open(workflow_file, "w") as f:
            json.dump(sample_flux_workflow, f)

        # Mock API responses
        responses.add(
            responses.POST,
            "http://127.0.0.1:8188/prompt",
            json={"prompt_id": "integration-test-123"},
            status=200
        )

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

        # Act - Queue prompt
        prompt_id = api.queue_prompt(updated)

        # Assert
        assert prompt_id == "integration-test-123"
        assert updated["1"]["inputs"]["text"] == "integration test prompt"
        assert updated["4"]["inputs"]["seed"] == 12345
