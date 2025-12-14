"""Unit tests for SelectionService"""
import pytest
import json
import os
from pathlib import Path
from unittest.mock import Mock

from services.selection_service import SelectionService
from infrastructure.project_store import ProjectStore


class TestSelectionServiceCollectKeyframes:
    """Test SelectionService.collect_keyframes()"""

    @pytest.mark.unit
    def test_collect_keyframes_with_variants(self, temp_project_dir, create_test_image):
        """Should collect all keyframe variants for a filename_base"""
        # Arrange
        keyframes_dir = temp_project_dir / "keyframes"
        keyframes_dir.mkdir(exist_ok=True)

        # Create test keyframes
        filename_base = "cathedral-interior"
        for variant in [1, 2, 3, 4]:
            filename = f"{filename_base}_v{variant}_00001_.png"
            img_path = keyframes_dir / filename
            create_test_image(str(img_path))

        mock_store = Mock(spec=ProjectStore)
        mock_store.ensure_dir.return_value = str(keyframes_dir)

        project = {"path": str(temp_project_dir)}
        service = SelectionService(mock_store)

        # Act
        keyframes = service.collect_keyframes(project, filename_base)

        # Assert
        assert len(keyframes) == 4
        assert keyframes[0]["variant"] == 1
        assert keyframes[1]["variant"] == 2
        assert keyframes[2]["variant"] == 3
        assert keyframes[3]["variant"] == 4

        # Check structure
        for kf in keyframes:
            assert "variant" in kf
            assert "filename" in kf
            assert "path" in kf
            assert "label" in kf
            assert "caption" in kf
            assert filename_base in kf["filename"]

    @pytest.mark.unit
    def test_collect_keyframes_empty_directory(self, temp_project_dir):
        """Should return empty list when no keyframes exist"""
        # Arrange
        keyframes_dir = temp_project_dir / "keyframes"
        keyframes_dir.mkdir(exist_ok=True)

        mock_store = Mock(spec=ProjectStore)
        mock_store.ensure_dir.return_value = str(keyframes_dir)

        project = {"path": str(temp_project_dir)}
        service = SelectionService(mock_store)

        # Act
        keyframes = service.collect_keyframes(project, "nonexistent-shot")

        # Assert
        assert keyframes == []

    @pytest.mark.unit
    def test_collect_keyframes_sorted_order(self, temp_project_dir, create_test_image):
        """Should return keyframes in sorted order"""
        # Arrange
        keyframes_dir = temp_project_dir / "keyframes"
        keyframes_dir.mkdir(exist_ok=True)

        filename_base = "test-shot"
        # Create in random order
        for variant in [3, 1, 4, 2]:
            filename = f"{filename_base}_v{variant}_00001_.png"
            img_path = keyframes_dir / filename
            create_test_image(str(img_path))

        mock_store = Mock(spec=ProjectStore)
        mock_store.ensure_dir.return_value = str(keyframes_dir)

        project = {"path": str(temp_project_dir)}
        service = SelectionService(mock_store)

        # Act
        keyframes = service.collect_keyframes(project, filename_base)

        # Assert - should be sorted by filename
        assert len(keyframes) == 4
        filenames = [kf["filename"] for kf in keyframes]
        assert filenames == sorted(filenames)

    @pytest.mark.unit
    def test_collect_keyframes_label_format(self, temp_project_dir, create_test_image):
        """Should format labels and captions correctly"""
        # Arrange
        keyframes_dir = temp_project_dir / "keyframes"
        keyframes_dir.mkdir(exist_ok=True)

        filename_base = "hand-book"
        filename = f"{filename_base}_v2_00001_.png"
        img_path = keyframes_dir / filename
        create_test_image(str(img_path))

        mock_store = Mock(spec=ProjectStore)
        mock_store.ensure_dir.return_value = str(keyframes_dir)

        project = {"path": str(temp_project_dir)}
        service = SelectionService(mock_store)

        # Act
        keyframes = service.collect_keyframes(project, filename_base)

        # Assert
        assert len(keyframes) == 1
        kf = keyframes[0]
        assert kf["label"] == f"Var 2 – {filename}"
        assert kf["caption"] == f"{filename_base} · Var 2"
        assert kf["variant"] == 2


class TestSelectionServiceExportSelections:
    """Test SelectionService.export_selections()"""

    @pytest.mark.unit
    def test_export_selections_success(self, temp_project_dir, create_test_image, sample_storyboard_data):
        """Should export selections to JSON and copy files"""
        # Arrange
        keyframes_dir = temp_project_dir / "keyframes"
        selected_dir = temp_project_dir / "selected"
        keyframes_dir.mkdir(exist_ok=True)
        selected_dir.mkdir(exist_ok=True)

        # Create test keyframes
        source_file_1 = keyframes_dir / "cathedral-interior_v2_00001_.png"
        source_file_2 = keyframes_dir / "hand-book_v1_00001_.png"
        create_test_image(str(source_file_1))
        create_test_image(str(source_file_2))

        # Build selections state
        selections_state = {
            "001": {
                "shot_id": "001",
                "filename_base": "cathedral-interior",
                "selected_variant": 2,
                "selected_file": "cathedral-interior_v2_00001_.png",
                "source_path": str(source_file_1)
            },
            "002": {
                "shot_id": "002",
                "filename_base": "hand-book",
                "selected_variant": 1,
                "selected_file": "hand-book_v1_00001_.png",
                "source_path": str(source_file_2)
            }
        }

        mock_store = Mock(spec=ProjectStore)
        mock_store.ensure_dir.return_value = str(selected_dir)

        project = {"path": str(temp_project_dir)}
        service = SelectionService(mock_store)

        # Act
        result = service.export_selections(project, sample_storyboard_data, selections_state)

        # Assert - JSON created
        export_path = selected_dir / "selected_keyframes.json"
        assert export_path.exists()

        # Assert - Files copied
        assert (selected_dir / "cathedral-interior_v2_00001_.png").exists()
        assert (selected_dir / "hand-book_v1_00001_.png").exists()

        # Assert - Result structure
        assert result["project"] == "Test Project"
        assert result["total_shots"] == 3
        assert len(result["selections"]) == 2
        assert result["_copied"] == 2
        assert "exported_at" in result
        assert "_path" in result

        # Verify JSON content
        with open(export_path) as f:
            saved_data = json.load(f)
        assert saved_data["project"] == "Test Project"
        assert len(saved_data["selections"]) == 2

    @pytest.mark.unit
    def test_export_selections_missing_source_file(self, temp_project_dir, sample_storyboard_data):
        """Should skip missing source files gracefully"""
        # Arrange
        selected_dir = temp_project_dir / "selected"
        selected_dir.mkdir(exist_ok=True)

        # Selection with non-existent file
        selections_state = {
            "001": {
                "shot_id": "001",
                "filename_base": "missing-shot",
                "selected_variant": 1,
                "selected_file": "missing-shot_v1_00001_.png",
                "source_path": "/nonexistent/path/file.png"
            }
        }

        mock_store = Mock(spec=ProjectStore)
        mock_store.ensure_dir.return_value = str(selected_dir)

        project = {"path": str(temp_project_dir)}
        service = SelectionService(mock_store)

        # Act
        result = service.export_selections(project, sample_storyboard_data, selections_state)

        # Assert - Should not crash, but copied count is 0
        assert result["_copied"] == 0
        assert len(result["selections"]) == 1

        # JSON should still be created
        export_path = selected_dir / "selected_keyframes.json"
        assert export_path.exists()

    @pytest.mark.unit
    def test_export_selections_empty_state(self, temp_project_dir, sample_storyboard_data):
        """Should handle empty selections state"""
        # Arrange
        selected_dir = temp_project_dir / "selected"
        selected_dir.mkdir(exist_ok=True)

        selections_state = {}

        mock_store = Mock(spec=ProjectStore)
        mock_store.ensure_dir.return_value = str(selected_dir)

        project = {"path": str(temp_project_dir)}
        service = SelectionService(mock_store)

        # Act
        result = service.export_selections(project, sample_storyboard_data, selections_state)

        # Assert
        assert result["project"] == "Test Project"
        assert result["total_shots"] == 3
        assert result["selections"] == []
        assert result["_copied"] == 0

        # JSON should be created
        export_path = selected_dir / "selected_keyframes.json"
        assert export_path.exists()

    @pytest.mark.unit
    def test_export_selections_adds_export_path(self, temp_project_dir, create_test_image, sample_storyboard_data):
        """Should add export_path to each selection after copying"""
        # Arrange
        keyframes_dir = temp_project_dir / "keyframes"
        selected_dir = temp_project_dir / "selected"
        keyframes_dir.mkdir(exist_ok=True)
        selected_dir.mkdir(exist_ok=True)

        source_file = keyframes_dir / "test-shot_v1_00001_.png"
        create_test_image(str(source_file))

        selections_state = {
            "001": {
                "shot_id": "001",
                "filename_base": "test-shot",
                "selected_variant": 1,
                "selected_file": "test-shot_v1_00001_.png",
                "source_path": str(source_file)
            }
        }

        mock_store = Mock(spec=ProjectStore)
        mock_store.ensure_dir.return_value = str(selected_dir)

        project = {"path": str(temp_project_dir)}
        service = SelectionService(mock_store)

        # Act
        result = service.export_selections(project, sample_storyboard_data, selections_state)

        # Assert - export_path added
        selection = result["selections"][0]
        assert "export_path" in selection
        assert selection["export_path"] == str(selected_dir / "test-shot_v1_00001_.png")


class TestSelectionServiceBuildPayload:
    """Test SelectionService._build_payload()"""

    @pytest.mark.unit
    def test_build_payload_basic(self, sample_storyboard_data):
        """Should build basic payload structure"""
        # Arrange
        mock_store = Mock(spec=ProjectStore)
        service = SelectionService(mock_store)

        selections_state = {
            "001": {
                "shot_id": "001",
                "filename_base": "test-shot",
                "selected_variant": 2,
                "selected_file": "test-shot_v2_00001_.png",
                "source_path": "/path/to/file.png"
            }
        }

        # Act
        payload = service._build_payload(sample_storyboard_data, selections_state)

        # Assert
        assert payload["project"] == "Test Project"
        assert payload["total_shots"] == 3
        assert len(payload["selections"]) == 1
        assert payload["selections"][0]["shot_id"] == "001"

    @pytest.mark.unit
    def test_build_payload_preserves_selection_data(self, sample_storyboard_data):
        """Should preserve all selection data in payload"""
        # Arrange
        mock_store = Mock(spec=ProjectStore)
        service = SelectionService(mock_store)

        selections_state = {
            "001": {
                "shot_id": "001",
                "filename_base": "cathedral-interior",
                "selected_variant": 3,
                "selected_file": "cathedral-interior_v3_00001_.png",
                "source_path": "/path/to/source.png",
                "custom_field": "custom_value"  # Extra field
            }
        }

        # Act
        payload = service._build_payload(sample_storyboard_data, selections_state)

        # Assert - All fields preserved
        selection = payload["selections"][0]
        assert selection["shot_id"] == "001"
        assert selection["filename_base"] == "cathedral-interior"
        assert selection["selected_variant"] == 3
        assert selection["selected_file"] == "cathedral-interior_v3_00001_.png"
        assert selection["source_path"] == "/path/to/source.png"
        assert selection["custom_field"] == "custom_value"

    @pytest.mark.unit
    def test_build_payload_empty_storyboard(self):
        """Should handle storyboard with no shots"""
        # Arrange
        mock_store = Mock(spec=ProjectStore)
        service = SelectionService(mock_store)

        empty_storyboard = {"project": "Empty Project", "shots": []}
        selections_state = {}

        # Act
        payload = service._build_payload(empty_storyboard, selections_state)

        # Assert
        assert payload["project"] == "Empty Project"
        assert payload["total_shots"] == 0
        assert payload["selections"] == []


class TestSelectionServiceExtractVariant:
    """Test SelectionService._extract_variant()"""

    @pytest.mark.unit
    def test_extract_variant_standard_format(self):
        """Should extract variant number from standard filename"""
        # Act & Assert
        assert SelectionService._extract_variant("cathedral-interior_v2_00001_.png") == 2
        assert SelectionService._extract_variant("hand-book_v1_00001_.png") == 1
        assert SelectionService._extract_variant("test-shot_v10_00001_.png") == 10
        assert SelectionService._extract_variant("scene_v99_00001_.png") == 99

    @pytest.mark.unit
    def test_extract_variant_no_variant(self):
        """Should return None when no variant marker exists"""
        # Act & Assert
        assert SelectionService._extract_variant("cathedral-interior_00001_.png") is None
        assert SelectionService._extract_variant("test.png") is None
        assert SelectionService._extract_variant("no_variant_here.png") is None

    @pytest.mark.unit
    def test_extract_variant_invalid_format(self):
        """Should return None for invalid variant formats"""
        # Act & Assert
        assert SelectionService._extract_variant("test_vabc_00001_.png") is None
        assert SelectionService._extract_variant("test_v_00001_.png") is None
        assert SelectionService._extract_variant("test_v-1_00001_.png") is None

    @pytest.mark.unit
    def test_extract_variant_handles_value_error(self, monkeypatch):
        """Should swallow ValueError when int conversion fails"""

        class FakeMatch:
            def group(self, _idx):
                return "not-a-number"

        monkeypatch.setattr("re.search", lambda *_a, **_k: FakeMatch())

        assert SelectionService._extract_variant("anything_v1.png") is None

    @pytest.mark.unit
    def test_extract_variant_multiple_matches(self):
        """Should extract first variant match"""
        # Act - filename with multiple v patterns
        result = SelectionService._extract_variant("test_v2_preview_v3_00001_.png")

        # Assert - Should get first match
        assert result == 2

    @pytest.mark.unit
    def test_extract_variant_case_sensitivity(self):
        """Should be case sensitive (lowercase v only)"""
        # Act & Assert
        assert SelectionService._extract_variant("test_V2_00001_.png") is None
        assert SelectionService._extract_variant("test_v2_00001_.png") == 2


class TestSelectionServiceIntegration:
    """Integration tests for SelectionService workflows"""

    @pytest.mark.unit
    def test_full_workflow_collect_and_export(self, temp_project_dir, create_test_image, sample_storyboard_data):
        """Should handle complete collect → export workflow"""
        # Arrange
        keyframes_dir = temp_project_dir / "keyframes"
        selected_dir = temp_project_dir / "selected"
        keyframes_dir.mkdir(exist_ok=True)
        selected_dir.mkdir(exist_ok=True)

        # Create keyframes for two shots
        shot1_files = []
        shot2_files = []

        for variant in [1, 2, 3]:
            f1 = keyframes_dir / f"cathedral-interior_v{variant}_00001_.png"
            f2 = keyframes_dir / f"hand-book_v{variant}_00001_.png"
            create_test_image(str(f1))
            create_test_image(str(f2))
            shot1_files.append(f1)
            shot2_files.append(f2)

        mock_store = Mock(spec=ProjectStore)
        mock_store.ensure_dir.side_effect = lambda proj, subdir: str(
            keyframes_dir if subdir == "keyframes" else selected_dir
        )

        project = {"path": str(temp_project_dir)}
        service = SelectionService(mock_store)

        # Act - Collect keyframes
        kf_shot1 = service.collect_keyframes(project, "cathedral-interior")
        kf_shot2 = service.collect_keyframes(project, "hand-book")

        assert len(kf_shot1) == 3
        assert len(kf_shot2) == 3

        # Build selections (select variant 2 for shot1, variant 1 for shot2)
        selections_state = {
            "001": {
                "shot_id": "001",
                "filename_base": "cathedral-interior",
                "selected_variant": 2,
                "selected_file": kf_shot1[1]["filename"],  # variant 2
                "source_path": kf_shot1[1]["path"]
            },
            "002": {
                "shot_id": "002",
                "filename_base": "hand-book",
                "selected_variant": 1,
                "selected_file": kf_shot2[0]["filename"],  # variant 1
                "source_path": kf_shot2[0]["path"]
            }
        }

        # Act - Export selections
        result = service.export_selections(project, sample_storyboard_data, selections_state)

        # Assert - Export successful
        assert result["_copied"] == 2
        assert result["total_shots"] == 3
        assert len(result["selections"]) == 2

        # Verify files copied
        assert (selected_dir / "cathedral-interior_v2_00001_.png").exists()
        assert (selected_dir / "hand-book_v1_00001_.png").exists()

        # Verify JSON
        json_path = selected_dir / "selected_keyframes.json"
        assert json_path.exists()

        with open(json_path) as f:
            saved = json.load(f)
        assert saved["project"] == "Test Project"
        assert len(saved["selections"]) == 2
