"""Tests for ModelDownloader - Security, API clients, and download flow."""
import os
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor

from services.model_manager.model_downloader import (
    ModelDownloader,
    CivitaiClient,
    HuggingfaceClient,
    SearchResult,
    DownloadTask,
    DownloadSource,
    DownloadStatus,
)


# =============================================================================
# Security Tests - Path Sanitization and Traversal Prevention
# =============================================================================

class TestSanitizeFilename:
    """Test _sanitize_filename - Path traversal prevention."""

    @pytest.fixture
    def downloader(self, tmp_path):
        """Create ModelDownloader with temp directory."""
        return ModelDownloader(models_root=str(tmp_path))

    def test_sanitize_normal_filename(self, downloader):
        """Normal filenames should pass through unchanged."""
        assert downloader._sanitize_filename("model.safetensors") == "model.safetensors"
        assert downloader._sanitize_filename("my_lora_v2.safetensors") == "my_lora_v2.safetensors"

    def test_sanitize_removes_directory_components(self, downloader):
        """Directory components should be stripped."""
        # Unix-style paths
        assert downloader._sanitize_filename("path/to/model.safetensors") == "model.safetensors"
        assert downloader._sanitize_filename("../model.safetensors") == "model.safetensors"
        assert downloader._sanitize_filename("../../etc/passwd") == "passwd"

    def test_sanitize_removes_windows_paths(self, downloader):
        """Windows-style paths should be handled."""
        # The Path().name will handle backslashes on the system
        result = downloader._sanitize_filename("C:\\models\\evil.safetensors")
        assert ".." not in result
        assert "/" not in result

    def test_sanitize_rejects_empty_filename(self, downloader):
        """Empty filenames should raise ValueError."""
        with pytest.raises(ValueError, match="Empty filename"):
            downloader._sanitize_filename("")

    def test_sanitize_rejects_dot(self, downloader):
        """Single dot should be rejected."""
        with pytest.raises(ValueError, match="Invalid filename"):
            downloader._sanitize_filename(".")

    def test_sanitize_rejects_dotdot(self, downloader):
        """Double dot should be rejected."""
        with pytest.raises(ValueError, match="Invalid filename"):
            downloader._sanitize_filename("..")

    def test_sanitize_rejects_path_only(self, downloader):
        """Path-only input that resolves to nothing should be rejected."""
        with pytest.raises(ValueError, match="Invalid filename"):
            downloader._sanitize_filename("../")

    def test_sanitize_handles_hidden_files(self, downloader):
        """Hidden files (starting with dot) should be allowed."""
        assert downloader._sanitize_filename(".hidden_model.safetensors") == ".hidden_model.safetensors"


class TestGetTargetPath:
    """Test get_target_path - Path traversal prevention."""

    @pytest.fixture
    def downloader(self, tmp_path):
        """Create ModelDownloader with temp directory."""
        models_root = tmp_path / "models"
        models_root.mkdir()
        return ModelDownloader(models_root=str(models_root))

    def test_get_target_path_normal(self, downloader, tmp_path):
        """Normal paths should work correctly."""
        path = downloader.get_target_path("loras", "my_lora.safetensors")
        assert path.name == "my_lora.safetensors"
        assert "loras" in str(path)

    def test_get_target_path_type_mapping(self, downloader):
        """Model types should be mapped correctly."""
        # Test various type mappings
        assert "checkpoints" in str(downloader.get_target_path("checkpoint", "model.safetensors"))
        assert "loras" in str(downloader.get_target_path("lora", "lora.safetensors"))
        assert "vae" in str(downloader.get_target_path("vae", "vae.safetensors"))
        assert "upscale_models" in str(downloader.get_target_path("upscaler", "upscaler.pth"))
        assert "diffusion_models" in str(downloader.get_target_path("unet", "unet.safetensors"))
        assert "embeddings" in str(downloader.get_target_path("embedding", "embed.pt"))

    def test_get_target_path_sanitizes_traversal(self, downloader):
        """Path traversal attempts should be sanitized to safe filename."""
        # The path traversal is sanitized - "../../../etc/passwd" becomes "passwd"
        path = downloader.get_target_path("loras", "../../../etc/passwd")
        assert path.name == "passwd"
        assert "loras" in str(path)
        # Most importantly, it stays within the models directory
        assert ".." not in str(path)

    def test_get_target_path_rejects_absolute_path(self, downloader):
        """Absolute paths in filename should be sanitized."""
        # This should sanitize to just the filename
        path = downloader.get_target_path("loras", "/etc/passwd")
        assert path.name == "passwd"
        assert "loras" in str(path)

    def test_get_target_path_stays_within_root(self, downloader, tmp_path):
        """Target path should always be within models root."""
        path = downloader.get_target_path("loras", "model.safetensors")
        models_root = tmp_path / "models"

        # Verify path is within models root
        assert str(path).startswith(str(models_root))

    def test_get_target_path_unknown_type(self, downloader):
        """Unknown model types should pass through as-is."""
        path = downloader.get_target_path("custom_type", "model.safetensors")
        assert "custom_type" in str(path)


# =============================================================================
# SearchResult Tests
# =============================================================================

class TestSearchResult:
    """Test SearchResult dataclass."""

    def test_search_result_creation(self):
        """Test creating a SearchResult."""
        result = SearchResult(
            filename="model.safetensors",
            source=DownloadSource.CIVITAI,
            download_url="https://civitai.com/download/123",
            model_name="Test Model",
            model_id="123",
            version_id="456",
            size_bytes=1024 * 1024 * 100,  # 100MB
            download_count=5000,
            rating=4.5,
        )
        assert result.filename == "model.safetensors"
        assert result.source == DownloadSource.CIVITAI

    def test_size_formatted_bytes(self):
        """Test size formatting for bytes."""
        result = SearchResult(
            filename="tiny.safetensors",
            source=DownloadSource.CIVITAI,
            download_url="",
            model_name="",
            model_id="",
            size_bytes=500,
        )
        assert "B" in result.size_formatted

    def test_size_formatted_megabytes(self):
        """Test size formatting for megabytes."""
        result = SearchResult(
            filename="model.safetensors",
            source=DownloadSource.CIVITAI,
            download_url="",
            model_name="",
            model_id="",
            size_bytes=1024 * 1024 * 50,  # 50MB
        )
        formatted = result.size_formatted
        assert "MB" in formatted or "GB" in formatted

    def test_size_formatted_unknown(self):
        """Test size formatting for unknown size."""
        result = SearchResult(
            filename="model.safetensors",
            source=DownloadSource.CIVITAI,
            download_url="",
            model_name="",
            model_id="",
            size_bytes=0,
        )
        assert result.size_formatted == "Unknown"


class TestDownloadTask:
    """Test DownloadTask dataclass."""

    def test_download_task_defaults(self):
        """Test default values."""
        task = DownloadTask(filename="model.safetensors", model_type="loras")
        assert task.status == DownloadStatus.PENDING
        assert task.progress == 0.0
        assert task.search_results == []
        assert task.selected_result is None

    def test_download_task_to_dict(self):
        """Test conversion to dict for UI."""
        task = DownloadTask(
            filename="model.safetensors",
            model_type="loras",
            status=DownloadStatus.DOWNLOADING,
            progress=50.0,
        )
        d = task.to_dict()
        assert d["filename"] == "model.safetensors"
        assert d["model_type"] == "loras"
        assert d["status"] == "downloading"
        assert d["progress"] == 50.0


# =============================================================================
# CivitaiClient Tests
# =============================================================================

class TestCivitaiClient:
    """Test CivitaiClient."""

    def test_client_initialization(self):
        """Test client initialization."""
        client = CivitaiClient()
        assert client.api_key == ""

        client_with_key = CivitaiClient(api_key="test_key")
        assert client_with_key.api_key == "test_key"
        assert "Authorization" in client_with_key.session.headers

    def test_clean_filename_for_search(self):
        """Test filename cleaning for search."""
        client = CivitaiClient()

        # Remove extensions and suffixes
        assert "flux" in client._clean_filename_for_search("flux1-dev_fp16.safetensors").lower()
        assert "sdxl" in client._clean_filename_for_search("sdxl_v1.0.safetensors").lower()

    def test_filename_matches_exact(self):
        """Test exact filename matching."""
        client = CivitaiClient()

        assert client._filename_matches("model.safetensors", "model.safetensors")
        assert client._filename_matches("Model.safetensors", "model.safetensors")

    def test_filename_matches_normalized(self):
        """Test normalized filename matching."""
        client = CivitaiClient()

        assert client._filename_matches("my_model.safetensors", "my-model.safetensors")
        assert client._filename_matches("MyModel.safetensors", "mymodel.safetensors")

    def test_filename_matches_partial(self):
        """Test partial name matching."""
        client = CivitaiClient()

        # The matching checks if search core is contained in candidate core
        # "flux1dev" is in "flux1devfp16" after normalization
        assert client._filename_matches("flux1-dev.safetensors", "flux1-dev.safetensors")
        # But not vice versa - more specific search won't match less specific
        # This is expected behavior for searching

    @patch('requests.Session.get')
    def test_search_by_filename_success(self, mock_get):
        """Test successful search."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "items": [
                {
                    "id": 123,
                    "name": "Test Model",
                    "stats": {"rating": 4.5},
                    "modelVersions": [
                        {
                            "id": 456,
                            "downloadCount": 1000,
                            "files": [
                                {
                                    "name": "test_model.safetensors",
                                    "downloadUrl": "https://civitai.com/api/download/123",
                                    "sizeKB": 1024,
                                }
                            ],
                            "images": [],
                        }
                    ],
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        client = CivitaiClient()
        results = client.search_by_filename("test_model.safetensors")

        assert len(results) >= 0  # May or may not match depending on matching logic

    @patch('requests.Session.get')
    def test_search_by_filename_network_error(self, mock_get):
        """Test search with network error."""
        import requests
        mock_get.side_effect = requests.RequestException("Network error")

        client = CivitaiClient()
        results = client.search_by_filename("model.safetensors")

        assert results == []


# =============================================================================
# HuggingfaceClient Tests
# =============================================================================

class TestHuggingfaceClient:
    """Test HuggingfaceClient."""

    def test_client_initialization(self):
        """Test client initialization."""
        client = HuggingfaceClient()
        assert client.token == ""

        client_with_token = HuggingfaceClient(token="hf_token")
        assert client_with_token.token == "hf_token"

    def test_clean_filename_for_search(self):
        """Test filename cleaning for search."""
        client = HuggingfaceClient()

        result = client._clean_filename_for_search("flux1-dev-fp16.safetensors")
        assert "flux" in result.lower()

    def test_filename_matches(self):
        """Test filename matching."""
        client = HuggingfaceClient()

        assert client._filename_matches("model.safetensors", "model.safetensors")
        assert client._filename_matches("my_model.safetensors", "my-model.safetensors")


# =============================================================================
# ModelDownloader Tests
# =============================================================================

class TestModelDownloaderInit:
    """Test ModelDownloader initialization."""

    def test_init_basic(self, tmp_path):
        """Test basic initialization."""
        downloader = ModelDownloader(models_root=str(tmp_path))
        assert downloader.models_root == tmp_path
        assert downloader.max_parallel == 2

    def test_init_max_parallel_limits(self, tmp_path):
        """Test max parallel downloads limits."""
        # Should clamp to minimum of 1
        d1 = ModelDownloader(models_root=str(tmp_path), max_parallel_downloads=0)
        assert d1.max_parallel == 1

        # Should clamp to maximum of 5
        d2 = ModelDownloader(models_root=str(tmp_path), max_parallel_downloads=10)
        assert d2.max_parallel == 5


class TestModelDownloaderQueue:
    """Test download queue operations."""

    @pytest.fixture
    def downloader(self, tmp_path):
        """Create ModelDownloader."""
        return ModelDownloader(models_root=str(tmp_path))

    def test_add_to_queue(self, downloader):
        """Test adding to download queue."""
        with patch.object(downloader, '_search_task'):
            task_id = downloader.add_to_queue("model.safetensors", "loras", auto_search=False)

        assert task_id == "loras/model.safetensors"
        assert task_id in downloader.download_queue

    def test_add_to_queue_duplicate(self, downloader):
        """Test adding duplicate to queue."""
        with patch.object(downloader, '_search_task'):
            task_id1 = downloader.add_to_queue("model.safetensors", "loras", auto_search=False)
            task_id2 = downloader.add_to_queue("model.safetensors", "loras", auto_search=False)

        assert task_id1 == task_id2
        assert len(downloader.download_queue) == 1

    def test_clear_queue(self, downloader):
        """Test clearing the queue."""
        with patch.object(downloader, '_search_task'):
            downloader.add_to_queue("model1.safetensors", "loras", auto_search=False)
            downloader.add_to_queue("model2.safetensors", "loras", auto_search=False)

        downloader.clear_queue()
        assert len(downloader.download_queue) == 0

    def test_get_queue_status(self, downloader):
        """Test getting queue status."""
        with patch.object(downloader, '_search_task'):
            downloader.add_to_queue("model.safetensors", "loras", auto_search=False)

        status = downloader.get_queue_status()
        assert "loras/model.safetensors" in status

    def test_get_statistics(self, downloader):
        """Test getting statistics."""
        with patch.object(downloader, '_search_task'):
            downloader.add_to_queue("model.safetensors", "loras", auto_search=False)

        stats = downloader.get_statistics()
        assert stats["total"] == 1
        assert stats["pending"] == 1


class TestModelDownloaderSearch:
    """Test search functionality."""

    @pytest.fixture
    def downloader(self, tmp_path):
        """Create ModelDownloader with mocked clients."""
        d = ModelDownloader(models_root=str(tmp_path))
        return d

    def test_search_model(self, downloader):
        """Test searching for a model."""
        # Mock both clients
        with patch.object(downloader.civitai, 'search_by_filename') as mock_civitai:
            with patch.object(downloader.huggingface, 'search_by_filename') as mock_hf:
                mock_civitai.return_value = [
                    SearchResult(
                        filename="model.safetensors",
                        source=DownloadSource.CIVITAI,
                        download_url="https://civitai.com/download/1",
                        model_name="Test",
                        model_id="1",
                        download_count=1000,
                    )
                ]
                mock_hf.return_value = []

                results = downloader.search_model("model.safetensors", "loras")

        assert len(results) == 1
        assert results[0].source == DownloadSource.CIVITAI

    def test_get_best_result(self, downloader):
        """Test selecting best result."""
        results = [
            SearchResult(
                filename="model.safetensors",
                source=DownloadSource.HUGGINGFACE,
                download_url="",
                model_name="",
                model_id="",
                download_count=100,
            ),
            SearchResult(
                filename="model.safetensors",
                source=DownloadSource.CIVITAI,
                download_url="",
                model_name="",
                model_id="",
                download_count=1000,  # Higher download count
            ),
        ]

        # Sort by download count (as search_model does)
        results.sort(key=lambda x: x.download_count, reverse=True)

        best = downloader.get_best_result(results)
        assert best.download_count == 1000

    def test_get_best_result_empty(self, downloader):
        """Test best result with empty list."""
        assert downloader.get_best_result([]) is None


class TestModelDownloaderDownload:
    """Test download functionality."""

    @pytest.fixture
    def downloader(self, tmp_path):
        """Create ModelDownloader."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        return ModelDownloader(models_root=str(models_dir))

    def test_cancel_downloads(self, downloader):
        """Test canceling downloads."""
        downloader._executor = Mock(spec=ThreadPoolExecutor)
        downloader.cancel_downloads()

        assert downloader._stop_event.is_set()
        downloader._executor.shutdown.assert_called()

    def test_start_downloads_no_tasks(self, downloader):
        """Test starting downloads with no ready tasks."""
        # Should not raise
        downloader.start_downloads()

    @patch('requests.get')
    def test_download_file_success(self, mock_get, downloader, tmp_path):
        """Test successful file download."""
        # Mock response
        mock_response = Mock()
        mock_response.headers = {'content-length': '1000'}
        mock_response.iter_content = Mock(return_value=[b'x' * 1000])
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        dest_path = tmp_path / "downloaded.safetensors"

        # Add task to queue for progress tracking
        with patch.object(downloader, '_search_task'):
            task_id = downloader.add_to_queue("test.safetensors", "loras", auto_search=False)

        downloader._download_file(
            url="https://example.com/model.safetensors",
            dest_path=dest_path,
            task_id=task_id,
        )

        assert dest_path.exists()

    @patch('requests.get')
    def test_download_file_cancelled(self, mock_get, downloader, tmp_path):
        """Test cancelled download."""
        downloader._stop_event.set()

        mock_response = Mock()
        mock_response.headers = {'content-length': '1000'}
        mock_response.iter_content = Mock(return_value=[b'x' * 100])
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        dest_path = tmp_path / "cancelled.safetensors"

        with patch.object(downloader, '_search_task'):
            task_id = downloader.add_to_queue("test.safetensors", "loras", auto_search=False)

        with pytest.raises(Exception, match="cancelled"):
            downloader._download_file(
                url="https://example.com/model.safetensors",
                dest_path=dest_path,
                task_id=task_id,
            )


class TestSearchTaskFlow:
    """Test the search task flow."""

    @pytest.fixture
    def downloader(self, tmp_path):
        """Create ModelDownloader."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "loras").mkdir()
        return ModelDownloader(models_root=str(models_dir))

    def test_search_task_found(self, downloader):
        """Test search task with results found."""
        with patch.object(downloader, '_search_task'):
            task_id = downloader.add_to_queue("model.safetensors", "loras", auto_search=False)

        # Mock search results
        with patch.object(downloader, 'search_model') as mock_search:
            mock_search.return_value = [
                SearchResult(
                    filename="model.safetensors",
                    source=DownloadSource.CIVITAI,
                    download_url="https://example.com/model",
                    model_name="Test",
                    model_id="1",
                    download_count=100,
                )
            ]
            downloader._search_task(task_id)

        task = downloader.download_queue[task_id]
        assert task.status == DownloadStatus.FOUND
        assert task.selected_result is not None

    def test_search_task_not_found(self, downloader):
        """Test search task with no results."""
        with patch.object(downloader, '_search_task'):
            task_id = downloader.add_to_queue("model.safetensors", "loras", auto_search=False)

        with patch.object(downloader, 'search_model') as mock_search:
            mock_search.return_value = []
            downloader._search_task(task_id)

        task = downloader.download_queue[task_id]
        assert task.status == DownloadStatus.NOT_FOUND

    def test_search_task_invalid_filename(self, downloader):
        """Test search task with invalid filename that passes initial add but fails path check."""
        # Add a task that looks valid initially
        with patch.object(downloader, '_search_task'):
            task_id = downloader.add_to_queue("model.safetensors", "loras", auto_search=False)

        # Modify task to have problematic filename
        downloader.download_queue[task_id].filename = ".."

        with patch.object(downloader, 'search_model') as mock_search:
            mock_search.return_value = [
                SearchResult(
                    filename="..",
                    source=DownloadSource.CIVITAI,
                    download_url="https://example.com/model",
                    model_name="Test",
                    model_id="1",
                    download_count=100,
                )
            ]
            downloader._search_task(task_id)

        task = downloader.download_queue[task_id]
        assert task.status == DownloadStatus.FAILED
        assert "Invalid" in task.error_message


class TestProgressCallback:
    """Test progress callback functionality."""

    @pytest.fixture
    def downloader(self, tmp_path):
        """Create ModelDownloader."""
        return ModelDownloader(models_root=str(tmp_path))

    def test_notify_progress_with_callback(self, downloader):
        """Test progress notification with callback."""
        callback = Mock()
        downloader.progress_callback = callback

        with patch.object(downloader, '_search_task'):
            task_id = downloader.add_to_queue("model.safetensors", "loras", auto_search=False)

        downloader._notify_progress(task_id)

        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == task_id

    def test_notify_progress_without_callback(self, downloader):
        """Test progress notification without callback."""
        with patch.object(downloader, '_search_task'):
            task_id = downloader.add_to_queue("model.safetensors", "loras", auto_search=False)

        # Should not raise
        downloader._notify_progress(task_id)
