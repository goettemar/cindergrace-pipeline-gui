"""Tests for StoryboardEditorService."""
import pytest
from unittest.mock import Mock, patch

from services.storyboard_editor_service import StoryboardEditorService
from domain.models import Storyboard, Shot


class TestStoryboardEditorService:
    """Tests for StoryboardEditorService class."""

    @pytest.fixture
    def service(self):
        """Create StoryboardEditorService instance."""
        return StoryboardEditorService()

    @pytest.fixture
    def empty_storyboard(self, service):
        """Create empty storyboard."""
        return service.create_new_storyboard("Test Project")

    @pytest.fixture
    def storyboard_with_shots(self, service, empty_storyboard):
        """Create storyboard with some shots."""
        service.add_shot(
            empty_storyboard,
            shot_id="001",
            filename_base="test-shot-1",
            description="First shot",
            prompt="a beautiful scene",
            duration=3.0
        )
        service.add_shot(
            empty_storyboard,
            shot_id="002",
            filename_base="test-shot-2",
            description="Second shot",
            prompt="another scene",
            duration=2.5
        )
        return empty_storyboard

    # ========================================================================
    # Create Storyboard Tests
    # ========================================================================

    def test_create_new_storyboard(self, service):
        """Test creating a new storyboard."""
        storyboard = service.create_new_storyboard("My Project")

        assert isinstance(storyboard, Storyboard)
        assert storyboard.project == "My Project"
        assert storyboard.shots == []
        assert storyboard.raw["project"] == "My Project"

    def test_create_new_storyboard_empty_name(self, service):
        """Test creating storyboard with empty name."""
        storyboard = service.create_new_storyboard("")

        assert storyboard.project == "Untitled Project"

    def test_create_new_storyboard_none_name(self, service):
        """Test creating storyboard with None name."""
        storyboard = service.create_new_storyboard(None)

        assert storyboard.project == "Untitled Project"

    # ========================================================================
    # Add Shot Tests
    # ========================================================================

    def test_add_shot_basic(self, service, empty_storyboard):
        """Test adding a basic shot."""
        result = service.add_shot(
            empty_storyboard,
            shot_id="001",
            filename_base="test-shot",
            description="Test description",
            prompt="a beautiful sunset",
            duration=3.0
        )

        assert len(result.shots) == 1
        assert result.shots[0].shot_id == "001"
        assert result.shots[0].filename_base == "test-shot"
        assert result.shots[0].prompt == "a beautiful sunset"
        assert result.shots[0].duration == 3.0

    def test_add_shot_with_resolution(self, service, empty_storyboard):
        """Test adding shot with custom resolution."""
        service.add_shot(
            empty_storyboard,
            shot_id="001",
            filename_base="test",
            description="desc",
            prompt="prompt",
            duration=3.0,
            width=1920,
            height=1080
        )

        shot = empty_storyboard.shots[0]
        assert shot.raw.get("width") == 1920
        assert shot.raw.get("height") == 1080

    def test_add_shot_default_resolution(self, service, empty_storyboard):
        """Test default resolution when not specified."""
        service.add_shot(
            empty_storyboard,
            shot_id="001",
            filename_base="test",
            description="desc",
            prompt="prompt",
            duration=3.0
        )

        shot = empty_storyboard.shots[0]
        assert shot.raw.get("width") == 1024
        assert shot.raw.get("height") == 576

    def test_add_shot_with_character_lora(self, service, empty_storyboard):
        """Test adding shot with character LoRA."""
        service.add_shot(
            empty_storyboard,
            shot_id="001",
            filename_base="test",
            description="desc",
            prompt="prompt",
            duration=3.0,
            character_lora="cg_elena"
        )

        shot = empty_storyboard.shots[0]
        assert shot.raw.get("character_lora") == "cg_elena"

    def test_add_shot_with_characters_list(self, service, empty_storyboard):
        """Test adding shot with multiple characters (legacy format)."""
        service.add_shot(
            empty_storyboard,
            shot_id="001",
            filename_base="test",
            description="desc",
            prompt="prompt",
            duration=3.0,
            characters=["elena", "marcus"]
        )

        shot = empty_storyboard.shots[0]
        assert shot.raw.get("characters") == ["elena", "marcus"]

    def test_add_shot_with_negative_prompt(self, service, empty_storyboard):
        """Test adding shot with negative prompt."""
        service.add_shot(
            empty_storyboard,
            shot_id="001",
            filename_base="test",
            description="desc",
            prompt="prompt",
            duration=3.0,
            negative_prompt="blurry, low quality"
        )

        shot = empty_storyboard.shots[0]
        assert shot.raw.get("negative_prompt") == "blurry, low quality"

    def test_add_shot_with_presets(self, service, empty_storyboard):
        """Test adding shot with presets."""
        presets = {
            "style": "cinematic",
            "lighting": "dramatic",
            "mood": "dark"
        }
        service.add_shot(
            empty_storyboard,
            shot_id="001",
            filename_base="test",
            description="desc",
            prompt="prompt",
            duration=3.0,
            presets=presets
        )

        shot = empty_storyboard.shots[0]
        assert shot.raw.get("presets") == presets

    def test_add_shot_with_flux_settings(self, service, empty_storyboard):
        """Test adding shot with Flux render settings."""
        flux = {"seed": 42, "cfg": 7.0, "steps": 30}
        service.add_shot(
            empty_storyboard,
            shot_id="001",
            filename_base="test",
            description="desc",
            prompt="prompt",
            duration=3.0,
            flux=flux
        )

        shot = empty_storyboard.shots[0]
        assert shot.raw.get("flux") == flux

    def test_add_shot_with_wan_settings(self, service, empty_storyboard):
        """Test adding shot with Wan render settings."""
        wan = {"seed": 123, "cfg": 6.0, "steps": 20, "motion_strength": 0.8}
        service.add_shot(
            empty_storyboard,
            shot_id="001",
            filename_base="test",
            description="desc",
            prompt="prompt",
            duration=3.0,
            wan=wan
        )

        shot = empty_storyboard.shots[0]
        assert shot.raw.get("wan") == wan

    def test_add_multiple_shots(self, service, empty_storyboard):
        """Test adding multiple shots."""
        service.add_shot(
            empty_storyboard,
            shot_id="001",
            filename_base="shot-1",
            description="First",
            prompt="first prompt",
            duration=3.0
        )
        service.add_shot(
            empty_storyboard,
            shot_id="002",
            filename_base="shot-2",
            description="Second",
            prompt="second prompt",
            duration=2.0
        )

        assert len(empty_storyboard.shots) == 2
        assert empty_storyboard.shots[0].shot_id == "001"
        assert empty_storyboard.shots[1].shot_id == "002"

    def test_add_shot_updates_raw(self, service, empty_storyboard):
        """Test that raw dict is updated when adding shots."""
        service.add_shot(
            empty_storyboard,
            shot_id="001",
            filename_base="test",
            description="desc",
            prompt="prompt",
            duration=3.0
        )

        assert len(empty_storyboard.raw["shots"]) == 1
        assert empty_storyboard.raw["shots"][0]["shot_id"] == "001"

    # ========================================================================
    # Update Shot Tests
    # ========================================================================

    def test_update_shot_prompt(self, service, storyboard_with_shots):
        """Test updating shot prompt."""
        service.update_shot(
            storyboard_with_shots,
            shot_index=0,
            prompt="updated prompt"
        )

        assert storyboard_with_shots.shots[0].prompt == "updated prompt"

    def test_update_shot_duration(self, service, storyboard_with_shots):
        """Test updating shot duration."""
        service.update_shot(
            storyboard_with_shots,
            shot_index=0,
            duration=5.0
        )

        assert storyboard_with_shots.shots[0].duration == 5.0

    def test_update_shot_resolution(self, service, storyboard_with_shots):
        """Test updating shot resolution."""
        service.update_shot(
            storyboard_with_shots,
            shot_index=0,
            width=1920,
            height=1080
        )

        assert storyboard_with_shots.shots[0].raw["width"] == 1920
        assert storyboard_with_shots.shots[0].raw["height"] == 1080

    def test_update_shot_multiple_fields(self, service, storyboard_with_shots):
        """Test updating multiple fields at once."""
        service.update_shot(
            storyboard_with_shots,
            shot_index=0,
            prompt="new prompt",
            duration=4.0,
            description="new description"
        )

        shot = storyboard_with_shots.shots[0]
        assert shot.prompt == "new prompt"
        assert shot.duration == 4.0
        assert shot.raw["description"] == "new description"

    def test_update_shot_invalid_index_negative(self, service, storyboard_with_shots):
        """Test updating shot with negative index."""
        with pytest.raises(IndexError):
            service.update_shot(storyboard_with_shots, shot_index=-1, prompt="test")

    def test_update_shot_invalid_index_too_large(self, service, storyboard_with_shots):
        """Test updating shot with index out of range."""
        with pytest.raises(IndexError):
            service.update_shot(storyboard_with_shots, shot_index=10, prompt="test")

    def test_update_shot_presets(self, service, storyboard_with_shots):
        """Test updating shot presets."""
        presets = {"style": "anime", "lighting": "soft"}
        service.update_shot(
            storyboard_with_shots,
            shot_index=0,
            presets=presets
        )

        assert storyboard_with_shots.shots[0].raw["presets"] == presets

    def test_update_shot_characters(self, service, storyboard_with_shots):
        """Test updating shot characters."""
        service.update_shot(
            storyboard_with_shots,
            shot_index=0,
            characters=["elena", "marcus"]
        )

        assert storyboard_with_shots.shots[0].characters == ["elena", "marcus"]

    def test_update_shot_none_value_ignored(self, service, storyboard_with_shots):
        """Test that None values are ignored."""
        original_prompt = storyboard_with_shots.shots[0].prompt
        service.update_shot(
            storyboard_with_shots,
            shot_index=0,
            prompt=None
        )

        assert storyboard_with_shots.shots[0].prompt == original_prompt

    def test_update_shot_empty_string_ignored_except_negative(self, service, storyboard_with_shots):
        """Test that empty strings are ignored for most fields."""
        original_prompt = storyboard_with_shots.shots[0].prompt
        service.update_shot(
            storyboard_with_shots,
            shot_index=0,
            prompt=""
        )

        assert storyboard_with_shots.shots[0].prompt == original_prompt

    def test_update_shot_empty_negative_prompt_allowed(self, service, storyboard_with_shots):
        """Test that empty negative_prompt is allowed."""
        service.update_shot(
            storyboard_with_shots,
            shot_index=0,
            negative_prompt=""
        )

        assert storyboard_with_shots.shots[0].raw["negative_prompt"] == ""

    def test_update_shot_syncs_raw(self, service, storyboard_with_shots):
        """Test that raw dict is synced after update."""
        service.update_shot(
            storyboard_with_shots,
            shot_index=0,
            prompt="synced prompt"
        )

        assert storyboard_with_shots.raw["shots"][0]["prompt"] == "synced prompt"

    # ========================================================================
    # Delete Shot Tests
    # ========================================================================

    def test_delete_shot(self, service, storyboard_with_shots):
        """Test deleting a shot."""
        initial_count = len(storyboard_with_shots.shots)
        service.delete_shot(storyboard_with_shots, shot_index=0)

        assert len(storyboard_with_shots.shots) == initial_count - 1
        assert storyboard_with_shots.shots[0].shot_id == "002"

    def test_delete_shot_invalid_index(self, service, storyboard_with_shots):
        """Test deleting shot with invalid index."""
        with pytest.raises(IndexError):
            service.delete_shot(storyboard_with_shots, shot_index=10)

    def test_delete_shot_negative_index(self, service, storyboard_with_shots):
        """Test deleting shot with negative index."""
        with pytest.raises(IndexError):
            service.delete_shot(storyboard_with_shots, shot_index=-1)

    def test_delete_shot_updates_raw(self, service, storyboard_with_shots):
        """Test that raw dict is updated after deletion."""
        service.delete_shot(storyboard_with_shots, shot_index=0)

        assert len(storyboard_with_shots.raw["shots"]) == 1
        assert storyboard_with_shots.raw["shots"][0]["shot_id"] == "002"

    def test_delete_all_shots(self, service, storyboard_with_shots):
        """Test deleting all shots."""
        service.delete_shot(storyboard_with_shots, shot_index=1)
        service.delete_shot(storyboard_with_shots, shot_index=0)

        assert len(storyboard_with_shots.shots) == 0

    # ========================================================================
    # Get Next Shot ID Tests
    # ========================================================================

    def test_get_next_shot_id_empty_storyboard(self, service, empty_storyboard):
        """Test getting next shot ID for empty storyboard."""
        next_id = service.get_next_shot_id(empty_storyboard)
        assert next_id == "001"

    def test_get_next_shot_id_with_shots(self, service, storyboard_with_shots):
        """Test getting next shot ID with existing shots."""
        next_id = service.get_next_shot_id(storyboard_with_shots)
        assert next_id == "003"

    def test_get_next_shot_id_non_numeric(self, service, empty_storyboard):
        """Test getting next shot ID with non-numeric existing IDs."""
        service.add_shot(
            empty_storyboard,
            shot_id="intro",
            filename_base="intro",
            description="Intro",
            prompt="intro",
            duration=3.0
        )

        next_id = service.get_next_shot_id(empty_storyboard)
        assert next_id == "001"

    def test_get_next_shot_id_mixed(self, service, empty_storyboard):
        """Test getting next shot ID with mixed IDs."""
        service.add_shot(
            empty_storyboard, shot_id="005", filename_base="a",
            description="a", prompt="a", duration=1.0
        )
        service.add_shot(
            empty_storyboard, shot_id="intro", filename_base="b",
            description="b", prompt="b", duration=1.0
        )

        next_id = service.get_next_shot_id(empty_storyboard)
        assert next_id == "006"

    # ========================================================================
    # Storyboard to Dict Tests
    # ========================================================================

    def test_storyboard_to_dict_with_raw(self, service, storyboard_with_shots):
        """Test converting storyboard to dict when raw exists."""
        result = service.storyboard_to_dict(storyboard_with_shots)

        assert result == storyboard_with_shots.raw

    def test_storyboard_to_dict_structure(self, service, storyboard_with_shots):
        """Test storyboard dict structure."""
        result = service.storyboard_to_dict(storyboard_with_shots)

        assert "project" in result
        assert "shots" in result
        assert len(result["shots"]) == 2

    def test_storyboard_to_dict_shot_data(self, service, storyboard_with_shots):
        """Test shot data in converted dict."""
        result = service.storyboard_to_dict(storyboard_with_shots)

        shot = result["shots"][0]
        assert "shot_id" in shot
        assert "filename_base" in shot
        assert "prompt" in shot
        assert "duration" in shot
