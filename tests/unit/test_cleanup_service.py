"""Unit tests for CleanupService"""
import pytest
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.cleanup_service import CleanupService


class TestCleanupServiceArchiveFiles:
    """Test file archiving functionality"""

    @pytest.mark.unit
    def test_archive_files_creates_archive_dir(self, tmp_path):
        """Should create timestamped archive directory"""
        # Arrange
        source_dir = tmp_path / "keyframes"
        source_dir.mkdir()
        (source_dir / "test.png").write_bytes(b"fake image")

        mock_store = MagicMock()
        service = CleanupService(mock_store)

        # Act
        count, archive_path = service._archive_files(
            str(source_dir), CleanupService.KEYFRAME_EXTENSIONS
        )

        # Assert
        assert count == 1
        assert "_archive" in archive_path
        assert os.path.exists(archive_path)
        assert not (source_dir / "test.png").exists()

    @pytest.mark.unit
    def test_archive_files_empty_directory(self, tmp_path):
        """Should return 0 for empty directory"""
        # Arrange
        source_dir = tmp_path / "empty"
        source_dir.mkdir()

        mock_store = MagicMock()
        service = CleanupService(mock_store)

        # Act
        count, archive_path = service._archive_files(
            str(source_dir), CleanupService.KEYFRAME_EXTENSIONS
        )

        # Assert
        assert count == 0
        assert archive_path == ""

    @pytest.mark.unit
    def test_archive_files_nonexistent_directory(self, tmp_path):
        """Should return 0 for non-existent directory"""
        mock_store = MagicMock()
        service = CleanupService(mock_store)

        count, archive_path = service._archive_files(
            "/nonexistent/path", CleanupService.KEYFRAME_EXTENSIONS
        )

        assert count == 0
        assert archive_path == ""

    @pytest.mark.unit
    def test_archive_files_with_subfolder(self, tmp_path):
        """Should create subfolder in archive"""
        # Arrange
        source_dir = tmp_path / "videos"
        source_dir.mkdir()
        (source_dir / "clip.mp4").write_bytes(b"fake video")

        mock_store = MagicMock()
        service = CleanupService(mock_store)

        # Act
        count, archive_path = service._archive_files(
            str(source_dir), CleanupService.VIDEO_EXTENSIONS, subfolder="clips"
        )

        # Assert
        assert count == 1
        assert "clips" in archive_path

    @pytest.mark.unit
    def test_archive_files_filters_by_extension(self, tmp_path):
        """Should only archive files with matching extensions"""
        # Arrange
        source_dir = tmp_path / "mixed"
        source_dir.mkdir()
        (source_dir / "image.png").write_bytes(b"image")
        (source_dir / "video.mp4").write_bytes(b"video")
        (source_dir / "text.txt").write_bytes(b"text")

        mock_store = MagicMock()
        service = CleanupService(mock_store)

        # Act
        count, _ = service._archive_files(
            str(source_dir), CleanupService.KEYFRAME_EXTENSIONS
        )

        # Assert
        assert count == 1  # Only the PNG
        assert (source_dir / "video.mp4").exists()
        assert (source_dir / "text.txt").exists()


class TestCleanupServiceProjectCleanup:
    """Test project-level cleanup methods"""

    @pytest.mark.unit
    def test_cleanup_project_keyframes(self, tmp_path):
        """Should archive keyframes from project directory"""
        # Arrange
        keyframes_dir = tmp_path / "keyframes"
        keyframes_dir.mkdir()
        (keyframes_dir / "shot_001_v1.png").write_bytes(b"image1")
        (keyframes_dir / "shot_001_v2.jpg").write_bytes(b"image2")

        mock_store = MagicMock()
        mock_store.project_path.return_value = str(keyframes_dir)
        service = CleanupService(mock_store)

        project = {"slug": "test-project"}

        # Act
        count = service.cleanup_project_keyframes(project)

        # Assert
        assert count == 2
        assert not list(keyframes_dir.glob("*.png"))
        assert not list(keyframes_dir.glob("*.jpg"))

    @pytest.mark.unit
    def test_cleanup_project_keyframes_no_dir(self, tmp_path):
        """Should return 0 if keyframes dir doesn't exist"""
        mock_store = MagicMock()
        mock_store.project_path.return_value = "/nonexistent"
        service = CleanupService(mock_store)

        count = service.cleanup_project_keyframes({"slug": "test"})

        assert count == 0

    @pytest.mark.unit
    def test_cleanup_project_videos(self, tmp_path):
        """Should archive videos from project directory"""
        # Arrange
        video_dir = tmp_path / "video"
        video_dir.mkdir()
        (video_dir / "clip_001.mp4").write_bytes(b"video1")
        (video_dir / "clip_002.webm").write_bytes(b"video2")

        mock_store = MagicMock()
        mock_store.project_path.return_value = str(video_dir)
        service = CleanupService(mock_store)

        # Act
        count = service.cleanup_project_videos({"slug": "test"})

        # Assert
        assert count == 2


class TestCleanupServiceComfyOutput:
    """Test ComfyUI output cleanup"""

    @pytest.mark.unit
    def test_cleanup_comfy_output(self, tmp_path):
        """Should archive files from ComfyUI output"""
        # Arrange
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / "keyframe_001.png").write_bytes(b"image")
        (output_dir / "video_001.mp4").write_bytes(b"video")

        mock_store = MagicMock()
        mock_store.comfy_output_dir.return_value = str(output_dir)
        service = CleanupService(mock_store)

        # Act
        count = service.cleanup_comfy_output()

        # Assert
        assert count == 2

    @pytest.mark.unit
    def test_cleanup_comfy_output_with_video_subdir(self, tmp_path):
        """Should also clean video subdirectory"""
        # Arrange
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        video_subdir = output_dir / "video"
        video_subdir.mkdir()
        (output_dir / "image.png").write_bytes(b"image")
        (video_subdir / "clip.mp4").write_bytes(b"video")

        mock_store = MagicMock()
        mock_store.comfy_output_dir.return_value = str(output_dir)
        service = CleanupService(mock_store)

        # Act
        count = service.cleanup_comfy_output()

        # Assert
        assert count == 2


class TestCleanupServicePreGeneration:
    """Test pre-generation cleanup methods"""

    @pytest.mark.unit
    def test_cleanup_before_keyframe_generation(self, tmp_path):
        """Should clean both project keyframes and comfy output"""
        # Arrange
        keyframes_dir = tmp_path / "keyframes"
        keyframes_dir.mkdir()
        (keyframes_dir / "old.png").write_bytes(b"image")

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / "leftover.png").write_bytes(b"image")

        mock_store = MagicMock()
        mock_store.project_path.return_value = str(keyframes_dir)
        mock_store.comfy_output_dir.return_value = str(output_dir)
        service = CleanupService(mock_store)

        # Act
        count = service.cleanup_before_keyframe_generation({"slug": "test"})

        # Assert
        assert count == 2

    @pytest.mark.unit
    def test_cleanup_before_video_generation(self, tmp_path):
        """Should clean both project videos and comfy output"""
        # Arrange
        video_dir = tmp_path / "video"
        video_dir.mkdir()
        (video_dir / "old.mp4").write_bytes(b"video")

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / "leftover.mp4").write_bytes(b"video")

        mock_store = MagicMock()
        mock_store.project_path.return_value = str(video_dir)
        mock_store.comfy_output_dir.return_value = str(output_dir)
        service = CleanupService(mock_store)

        # Act
        count = service.cleanup_before_video_generation({"slug": "test"})

        # Assert
        assert count == 2


class TestCleanupServiceLoraCleanup:
    """Test LoRA file cleanup"""

    @pytest.mark.unit
    def test_cleanup_character_lora(self, tmp_path):
        """Should archive matching LoRA files"""
        # Arrange
        lora_dir = tmp_path / "loras"
        lora_dir.mkdir()
        (lora_dir / "cg_alice_v1.safetensors").write_bytes(b"lora1")
        (lora_dir / "cg_alice_v2.safetensors").write_bytes(b"lora2")
        (lora_dir / "cg_bob_v1.safetensors").write_bytes(b"other")

        mock_store = MagicMock()
        service = CleanupService(mock_store)

        # Act
        count = service.cleanup_character_lora(str(lora_dir), "alice")

        # Assert
        assert count == 2
        assert (lora_dir / "cg_bob_v1.safetensors").exists()

    @pytest.mark.unit
    def test_cleanup_character_lora_no_matches(self, tmp_path):
        """Should return 0 if no matching files"""
        # Arrange
        lora_dir = tmp_path / "loras"
        lora_dir.mkdir()
        (lora_dir / "other_lora.safetensors").write_bytes(b"lora")

        mock_store = MagicMock()
        service = CleanupService(mock_store)

        # Act
        count = service.cleanup_character_lora(str(lora_dir), "alice")

        # Assert
        assert count == 0

    @pytest.mark.unit
    def test_cleanup_character_lora_nonexistent_dir(self, tmp_path):
        """Should return 0 for non-existent directory"""
        mock_store = MagicMock()
        service = CleanupService(mock_store)

        count = service.cleanup_character_lora("/nonexistent", "alice")

        assert count == 0
