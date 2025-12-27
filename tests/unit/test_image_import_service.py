"""Tests for ImageImportService."""
import os
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from pathlib import Path

from PIL import Image
import numpy as np

from services.image_import_service import (
    ImageImportService,
    ImageAnalyzer,
    ImportedImage
)


class TestImportedImage:
    """Tests for ImportedImage dataclass."""

    def test_default_values(self):
        """Test default values."""
        img = ImportedImage(
            original_path="/path/to/image.png",
            filename="image.png",
            width=1024,
            height=768,
            suggested_filename_base="image"
        )
        assert img.original_path == "/path/to/image.png"
        assert img.filename == "image.png"
        assert img.width == 1024
        assert img.height == 768
        assert img.suggested_filename_base == "image"
        assert img.suggested_prompt == ""
        assert img.suggested_description == ""
        assert img.order == 0

    def test_all_values(self):
        """Test with all values set."""
        img = ImportedImage(
            original_path="/path/to/image.png",
            filename="image.png",
            width=1024,
            height=768,
            suggested_filename_base="image",
            suggested_prompt="a beautiful scene",
            suggested_description="Test image",
            order=5
        )
        assert img.suggested_prompt == "a beautiful scene"
        assert img.suggested_description == "Test image"
        assert img.order == 5


class TestImageImportService:
    """Tests for ImageImportService class."""

    @pytest.fixture
    def service(self):
        """Create ImageImportService instance."""
        return ImageImportService()

    @pytest.fixture
    def temp_image_folder(self, tmp_path):
        """Create folder with test images."""
        folder = tmp_path / "images"
        folder.mkdir()

        # Create test images
        for i in range(3):
            img_array = np.random.randint(0, 255, (576, 1024, 3), dtype=np.uint8)
            img = Image.fromarray(img_array)
            img.save(folder / f"test_image_{i+1:02d}.png")

        return folder

    @pytest.fixture
    def create_test_image_file(self, tmp_path):
        """Factory to create test image files."""
        def _create(filename, width=1024, height=576):
            img_path = tmp_path / filename
            img_array = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
            img = Image.fromarray(img_array)
            img.save(img_path)
            return img_path
        return _create

    # ========================================================================
    # Scan Folder Tests
    # ========================================================================

    def test_scan_folder_empty(self, service, tmp_path):
        """Test scanning empty folder."""
        empty_folder = tmp_path / "empty"
        empty_folder.mkdir()

        result = service.scan_folder(str(empty_folder))
        assert result == []

    def test_scan_folder_nonexistent(self, service):
        """Test scanning non-existent folder."""
        result = service.scan_folder("/nonexistent/path")
        assert result == []

    def test_scan_folder_with_images(self, service, temp_image_folder):
        """Test scanning folder with images."""
        result = service.scan_folder(str(temp_image_folder))

        assert len(result) == 3
        for img in result:
            assert isinstance(img, ImportedImage)
            assert img.width == 1024
            assert img.height == 576

    def test_scan_folder_sorted_by_name(self, service, temp_image_folder):
        """Test that images are sorted by filename."""
        result = service.scan_folder(str(temp_image_folder))

        filenames = [img.filename for img in result]
        assert filenames == sorted(filenames)

    def test_scan_folder_ignores_non_images(self, service, tmp_path):
        """Test that non-image files are ignored."""
        folder = tmp_path / "mixed"
        folder.mkdir()

        # Create image
        img_array = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        img = Image.fromarray(img_array)
        img.save(folder / "image.png")

        # Create non-image files
        (folder / "text.txt").write_text("hello")
        (folder / "data.json").write_text("{}")

        result = service.scan_folder(str(folder))
        assert len(result) == 1
        assert result[0].filename == "image.png"

    def test_scan_folder_supports_multiple_formats(self, service, tmp_path):
        """Test that multiple image formats are supported."""
        folder = tmp_path / "formats"
        folder.mkdir()

        img_array = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        img = Image.fromarray(img_array)

        img.save(folder / "image.png")
        img.save(folder / "image.jpg")
        img.save(folder / "image.jpeg")
        img.save(folder / "image.bmp")

        result = service.scan_folder(str(folder))
        assert len(result) == 4

    def test_scan_folder_sets_order(self, service, temp_image_folder):
        """Test that order is set correctly."""
        result = service.scan_folder(str(temp_image_folder))

        for i, img in enumerate(result):
            assert img.order == i

    def test_scan_folder_handles_corrupt_image(self, service, tmp_path):
        """Test handling of corrupt image files."""
        folder = tmp_path / "corrupt"
        folder.mkdir()

        # Create valid image
        img_array = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        img = Image.fromarray(img_array)
        img.save(folder / "valid.png")

        # Create corrupt "image" file
        (folder / "corrupt.png").write_bytes(b"not an image")

        result = service.scan_folder(str(folder))
        assert len(result) == 1
        assert result[0].filename == "valid.png"

    # ========================================================================
    # Sanitize Filename Tests
    # ========================================================================

    def test_sanitize_filename_basic(self, service):
        """Test basic filename sanitization."""
        result = service._sanitize_filename("My Image File")
        assert result == "my-image-file"

    def test_sanitize_filename_special_chars(self, service):
        """Test sanitization of special characters."""
        result = service._sanitize_filename("image@#$%^&*()!.test")
        assert result == "imagetest"

    def test_sanitize_filename_underscores(self, service):
        """Test that underscores are converted to dashes."""
        result = service._sanitize_filename("my_image_file")
        assert result == "my-image-file"

    def test_sanitize_filename_multiple_dashes(self, service):
        """Test that multiple dashes are collapsed."""
        result = service._sanitize_filename("my---image---file")
        assert result == "my-image-file"

    def test_sanitize_filename_empty(self, service):
        """Test sanitization of empty/invalid names."""
        result = service._sanitize_filename("@#$%^&*()")
        assert result == "imported-image"

    def test_sanitize_filename_leading_trailing(self, service):
        """Test removal of leading/trailing dashes."""
        result = service._sanitize_filename("---my-image---")
        assert result == "my-image"

    # ========================================================================
    # Import Images Tests
    # ========================================================================

    def test_import_images_basic(self, service, temp_image_folder, tmp_path):
        """Test basic image import."""
        images = service.scan_folder(str(temp_image_folder))
        target_dir = tmp_path / "imported"

        results = service.import_images(images, str(target_dir))

        assert len(results) == 3
        assert target_dir.exists()
        for img, new_path in results:
            assert os.path.exists(new_path)

    def test_import_images_rename(self, service, temp_image_folder, tmp_path):
        """Test image import with renaming."""
        images = service.scan_folder(str(temp_image_folder))
        target_dir = tmp_path / "imported"

        results = service.import_images(images, str(target_dir), rename=True)

        for img, new_path in results:
            filename = os.path.basename(new_path)
            assert "_v1_00001_" in filename or "_v" in filename

    def test_import_images_no_rename(self, service, temp_image_folder, tmp_path):
        """Test image import without renaming."""
        images = service.scan_folder(str(temp_image_folder))
        target_dir = tmp_path / "imported"

        results = service.import_images(images, str(target_dir), rename=False)

        for img, new_path in results:
            assert img.filename in new_path or "_" in os.path.basename(new_path)

    def test_import_images_avoids_overwrite(self, service, temp_image_folder, tmp_path):
        """Test that existing files are not overwritten."""
        images = service.scan_folder(str(temp_image_folder))
        target_dir = tmp_path / "imported"

        # Import twice
        results1 = service.import_images(images, str(target_dir))
        results2 = service.import_images(images, str(target_dir))

        # All files should be unique
        paths1 = {new_path for _, new_path in results1}
        paths2 = {new_path for _, new_path in results2}
        assert paths1.isdisjoint(paths2)

    def test_import_images_creates_target_dir(self, service, temp_image_folder, tmp_path):
        """Test that target directory is created if needed."""
        images = service.scan_folder(str(temp_image_folder))
        target_dir = tmp_path / "new" / "nested" / "dir"

        service.import_images(images, str(target_dir))
        assert target_dir.exists()

    # ========================================================================
    # Create Storyboard Tests
    # ========================================================================

    def test_create_storyboard_from_images(self, service, temp_image_folder):
        """Test creating storyboard from images."""
        images = service.scan_folder(str(temp_image_folder))

        storyboard = service.create_storyboard_from_images(
            images, "Test Project"
        )

        assert storyboard.project == "Test Project"
        assert len(storyboard.shots) == 3

    def test_create_storyboard_shot_ids(self, service, temp_image_folder):
        """Test that shot IDs are sequential."""
        images = service.scan_folder(str(temp_image_folder))

        storyboard = service.create_storyboard_from_images(
            images, "Test Project"
        )

        shot_ids = [shot.shot_id for shot in storyboard.shots]
        assert shot_ids == ["001", "002", "003"]

    def test_create_storyboard_with_image_resolution(self, service, temp_image_folder):
        """Test using image resolution for shots."""
        images = service.scan_folder(str(temp_image_folder))

        storyboard = service.create_storyboard_from_images(
            images, "Test", use_image_resolution=True
        )

        for shot in storyboard.shots:
            assert shot.raw["width"] == 1024
            assert shot.raw["height"] == 576

    def test_create_storyboard_with_default_resolution(self, service, temp_image_folder):
        """Test using default resolution for shots."""
        images = service.scan_folder(str(temp_image_folder))

        storyboard = service.create_storyboard_from_images(
            images, "Test",
            use_image_resolution=False,
            default_width=1920,
            default_height=1080
        )

        for shot in storyboard.shots:
            assert shot.raw["width"] == 1920
            assert shot.raw["height"] == 1080

    def test_create_storyboard_custom_duration(self, service, temp_image_folder):
        """Test custom default duration."""
        images = service.scan_folder(str(temp_image_folder))

        storyboard = service.create_storyboard_from_images(
            images, "Test", default_duration=5.0
        )

        for shot in storyboard.shots:
            assert shot.duration == 5.0

    def test_create_storyboard_default_presets(self, service, temp_image_folder):
        """Test that default presets are set."""
        images = service.scan_folder(str(temp_image_folder))

        storyboard = service.create_storyboard_from_images(
            images, "Test"
        )

        for shot in storyboard.shots:
            assert "presets" in shot.raw
            assert shot.raw["presets"]["style"] == "cinematic"

    def test_create_storyboard_default_wan_settings(self, service, temp_image_folder):
        """Test that default Wan settings are set."""
        images = service.scan_folder(str(temp_image_folder))

        storyboard = service.create_storyboard_from_images(
            images, "Test"
        )

        for shot in storyboard.shots:
            assert "wan" in shot.raw
            assert shot.raw["wan"]["seed"] == -1

    # ========================================================================
    # Create Selection JSON Tests
    # ========================================================================

    def test_create_selection_json_structure(self, service, temp_image_folder, tmp_path):
        """Test selection JSON structure."""
        images = service.scan_folder(str(temp_image_folder))
        target_dir = tmp_path / "imported"
        imported = service.import_images(images, str(target_dir))

        selection = service.create_selection_json(imported, "Test Project")

        assert "project" in selection
        assert "total_shots" in selection
        assert "exported_at" in selection
        assert "selections" in selection

    def test_create_selection_json_content(self, service, temp_image_folder, tmp_path):
        """Test selection JSON content."""
        images = service.scan_folder(str(temp_image_folder))
        target_dir = tmp_path / "imported"
        imported = service.import_images(images, str(target_dir))

        selection = service.create_selection_json(imported, "Test Project")

        assert selection["project"] == "Test Project"
        assert selection["total_shots"] == 3
        assert len(selection["selections"]) == 3

    def test_create_selection_json_shot_data(self, service, temp_image_folder, tmp_path):
        """Test selection JSON shot data."""
        images = service.scan_folder(str(temp_image_folder))
        target_dir = tmp_path / "imported"
        imported = service.import_images(images, str(target_dir))

        selection = service.create_selection_json(imported, "Test Project")

        for sel in selection["selections"]:
            assert "shot_id" in sel
            assert "filename_base" in sel
            assert "selected_variant" in sel
            assert "selected_file" in sel
            assert "source_path" in sel
            assert "export_path" in sel

    def test_create_selection_json_sequential_ids(self, service, temp_image_folder, tmp_path):
        """Test that selection IDs are sequential."""
        images = service.scan_folder(str(temp_image_folder))
        target_dir = tmp_path / "imported"
        imported = service.import_images(images, str(target_dir))

        selection = service.create_selection_json(imported, "Test Project")

        shot_ids = [sel["shot_id"] for sel in selection["selections"]]
        assert shot_ids == ["001", "002", "003"]


class TestImageAnalyzer:
    """Tests for ImageAnalyzer class."""

    def test_init_without_comfy_api(self):
        """Test initialization without ComfyUI API."""
        analyzer = ImageAnalyzer()
        assert analyzer.comfy_api is None
        assert analyzer._analyzer_available is False

    def test_init_with_comfy_api(self):
        """Test initialization with ComfyUI API."""
        mock_api = Mock()
        analyzer = ImageAnalyzer(comfy_api=mock_api)
        assert analyzer.comfy_api is mock_api

    def test_is_available_default(self):
        """Test is_available returns False by default."""
        analyzer = ImageAnalyzer()
        assert analyzer.is_available() is False

    def test_analyze_image_placeholder(self):
        """Test analyze_image returns placeholder dict."""
        analyzer = ImageAnalyzer()
        result = analyzer.analyze_image("/path/to/image.png")

        assert "prompt" in result
        assert "description" in result
        assert "detected_objects" in result
        assert "mood" in result

    def test_analyze_batch(self):
        """Test analyze_batch analyzes multiple images."""
        analyzer = ImageAnalyzer()
        paths = ["/path/1.png", "/path/2.png", "/path/3.png"]

        results = analyzer.analyze_batch(paths)

        assert len(results) == 3
        for result in results:
            assert "prompt" in result
