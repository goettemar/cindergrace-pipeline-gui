"""Unit tests for StoryboardService"""
import pytest
import json
import os
from pathlib import Path

from domain.storyboard_service import StoryboardService, load_storyboard, load_selection
from domain.models import Storyboard, SelectionSet
from domain.exceptions import ValidationError


class TestStoryboardServiceLoadFromFile:
    """Test StoryboardService.load_from_file()"""

    @pytest.mark.unit
    def test_load_valid_storyboard(self, sample_storyboard_file):
        """Should load valid storyboard file successfully"""
        # Act
        storyboard = StoryboardService.load_from_file(str(sample_storyboard_file))

        # Assert
        assert isinstance(storyboard, Storyboard)
        assert storyboard.project == "Test Project"
        assert len(storyboard.shots) == 3
        assert storyboard.shots[0].shot_id == "001"
        assert storyboard.shots[0].filename_base == "cathedral-interior"

    @pytest.mark.unit
    def test_load_nonexistent_file(self, tmp_path):
        """Should raise FileNotFoundError for missing file"""
        # Arrange
        nonexistent_file = tmp_path / "does_not_exist.json"

        # Act & Assert
        with pytest.raises(FileNotFoundError) as exc_info:
            StoryboardService.load_from_file(str(nonexistent_file))

        assert "Storyboard nicht gefunden" in str(exc_info.value)

    @pytest.mark.unit
    def test_load_invalid_json(self, tmp_path):
        """Should raise ValidationError for invalid JSON"""
        # Arrange
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("{invalid json content")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            StoryboardService.load_from_file(str(invalid_file))

        assert "Ungültiges JSON" in str(exc_info.value)

    @pytest.mark.unit
    def test_load_minimal_storyboard(self, tmp_path, sample_storyboard_minimal):
        """Should load minimal valid storyboard"""
        # Arrange
        storyboard_file = tmp_path / "minimal.json"
        with open(storyboard_file, "w") as f:
            json.dump(sample_storyboard_minimal, f)

        # Act
        storyboard = StoryboardService.load_from_file(str(storyboard_file))

        # Assert
        assert storyboard.project == "Minimal Test"
        assert len(storyboard.shots) == 1

    @pytest.mark.unit
    def test_load_preserves_wan_motion(self, sample_storyboard_file):
        """Should preserve wan_motion metadata"""
        # Act
        storyboard = StoryboardService.load_from_file(str(sample_storyboard_file))

        # Assert
        first_shot = storyboard.shots[0]
        assert "wan_motion" in first_shot.raw
        assert first_shot.raw["wan_motion"]["type"] == "macro_dolly"
        assert first_shot.raw["wan_motion"]["strength"] == 0.6


class TestStoryboardServiceLoadFromConfig:
    """Test StoryboardService.load_from_config()"""

    @pytest.mark.unit
    def test_load_with_explicit_filename(self, mock_config_manager, sample_storyboard_file):
        """Should load storyboard when filename is explicitly provided"""
        # Arrange
        mock_config_manager.config_dir = str(sample_storyboard_file.parent)

        # Act
        storyboard = StoryboardService.load_from_config(
            mock_config_manager,
            filename=str(sample_storyboard_file)
        )

        # Assert
        assert storyboard.project == "Test Project"
        assert len(storyboard.shots) == 3

    @pytest.mark.unit
    def test_load_without_filename_raises_error(self, mock_config_manager):
        """Should raise ValidationError if no filename provided and none set"""
        # Arrange
        mock_config_manager.get_current_storyboard.return_value = None

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            StoryboardService.load_from_config(mock_config_manager)

        assert "Kein Storyboard gesetzt" in str(exc_info.value)

    @pytest.mark.unit
    def test_load_with_relative_path(self, mock_config_manager, sample_storyboard_file):
        """Should resolve relative paths using config_dir"""
        # Arrange
        mock_config_manager.config_dir = str(sample_storyboard_file.parent)
        mock_config_manager.get_current_storyboard.return_value = sample_storyboard_file.name

        # Act
        storyboard = StoryboardService.load_from_config(mock_config_manager)

        # Assert
        assert storyboard.project == "Test Project"


class TestStoryboardServiceApplyGlobalResolution:
    """Test StoryboardService.apply_global_resolution()"""

    @pytest.mark.unit
    def test_apply_resolution_to_all_shots(self, sample_storyboard_file):
        """Should override resolution for all shots"""
        # Arrange
        storyboard = StoryboardService.load_from_file(str(sample_storyboard_file))
        assert storyboard.shots[0].width == 1024
        assert storyboard.shots[0].height == 576

        # Act
        modified = StoryboardService.apply_global_resolution(storyboard, 1920, 1080)

        # Assert
        for shot in modified.shots:
            assert shot.width == 1920
            assert shot.height == 1080
            assert shot.raw["width"] == 1920
            assert shot.raw["height"] == 1080

    @pytest.mark.unit
    def test_apply_resolution_returns_storyboard(self, sample_storyboard_file):
        """Should return modified storyboard for chaining"""
        # Arrange
        storyboard = StoryboardService.load_from_file(str(sample_storyboard_file))

        # Act
        result = StoryboardService.apply_global_resolution(storyboard, 1280, 720)

        # Assert
        assert result is storyboard  # Same object (in-place modification)
        assert result.shots[0].width == 1280

    @pytest.mark.unit
    def test_apply_resolution_modifies_in_place(self, sample_storyboard_file):
        """Should modify storyboard in-place"""
        # Arrange
        storyboard = StoryboardService.load_from_file(str(sample_storyboard_file))
        original_id = id(storyboard)

        # Act
        StoryboardService.apply_global_resolution(storyboard, 1920, 1080)

        # Assert
        assert id(storyboard) == original_id
        assert storyboard.shots[0].width == 1920


class TestStoryboardServiceApplyResolutionFromConfig:
    """Test StoryboardService.apply_resolution_from_config()"""

    @pytest.mark.unit
    def test_apply_resolution_from_config(self, mock_config_manager, sample_storyboard_file):
        """Should apply resolution from config manager"""
        # Arrange
        storyboard = StoryboardService.load_from_file(str(sample_storyboard_file))
        mock_config_manager.get_resolution_tuple.return_value = (1920, 1080)

        # Act
        modified = StoryboardService.apply_resolution_from_config(storyboard, mock_config_manager)

        # Assert
        assert modified.shots[0].width == 1920
        assert modified.shots[0].height == 1080


class TestLoadStoryboardLegacy:
    """Test legacy load_storyboard() function"""

    @pytest.mark.unit
    def test_legacy_function_works(self, sample_storyboard_file):
        """Legacy function should still work for backwards compatibility"""
        # Act
        storyboard = load_storyboard(str(sample_storyboard_file))

        # Assert
        assert isinstance(storyboard, Storyboard)
        assert storyboard.project == "Test Project"


class TestLoadSelection:
    """Test load_selection() function"""

    @pytest.mark.unit
    def test_load_valid_selection(self, sample_selection_file):
        """Should load valid selection file"""
        # Act
        selection = load_selection(str(sample_selection_file))

        # Assert
        assert isinstance(selection, SelectionSet)
        assert selection.project == "Test Project"
        assert selection.total_shots == 3
        assert len(selection.selections) == 2

    @pytest.mark.unit
    def test_load_nonexistent_selection(self, tmp_path):
        """Should raise FileNotFoundError for missing file"""
        # Arrange
        nonexistent_file = tmp_path / "missing.json"

        # Act & Assert
        with pytest.raises(FileNotFoundError) as exc_info:
            load_selection(str(nonexistent_file))

        assert "Selection nicht gefunden" in str(exc_info.value)

    @pytest.mark.unit
    def test_load_invalid_selection_json(self, tmp_path):
        """Should raise ValidationError for invalid JSON"""
        # Arrange
        invalid_file = tmp_path / "invalid_selection.json"
        invalid_file.write_text("{broken json")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            load_selection(str(invalid_file))

        assert "Ungültiges JSON" in str(exc_info.value)

    @pytest.mark.unit
    def test_selection_preserves_metadata(self, sample_selection_file):
        """Should preserve all selection metadata"""
        # Act
        selection = load_selection(str(sample_selection_file))

        # Assert
        assert selection.exported_at == "2024-12-12T10:15:01"
        first_sel = selection.selections[0]
        assert first_sel.shot_id == "001"
        assert first_sel.filename_base == "cathedral-interior"
        assert first_sel.selected_variant == 2


class TestStoryboardServiceIntegration:
    """Integration tests for StoryboardService workflow"""

    @pytest.mark.unit
    def test_load_and_modify_workflow(self, sample_storyboard_file):
        """Test complete load -> modify -> validate workflow"""
        # Load
        storyboard = StoryboardService.load_from_file(str(sample_storyboard_file))
        assert storyboard.shots[0].width == 1024

        # Modify
        StoryboardService.apply_global_resolution(storyboard, 1920, 1080)
        assert storyboard.shots[0].width == 1920

        # Validate all shots updated
        for shot in storyboard.shots:
            assert shot.width == 1920
            assert shot.height == 1080

    @pytest.mark.unit
    def test_chained_operations(self, sample_storyboard_file, mock_config_manager):
        """Test method chaining"""
        # Arrange
        mock_config_manager.get_resolution_tuple.return_value = (1280, 720)

        # Act - Chained operations
        storyboard = (
            StoryboardService
            .load_from_file(str(sample_storyboard_file))
        )
        StoryboardService.apply_resolution_from_config(storyboard, mock_config_manager)

        # Assert
        assert storyboard.shots[0].width == 1280
        assert storyboard.shots[0].height == 720
