"""Tests for PresetService - Prompt preset management for generation phases."""
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from infrastructure.preset_service import PresetService, get_preset_db_path


@pytest.fixture
def temp_db(tmp_path):
    """Create temporary database path."""
    return str(tmp_path / "test_presets.db")


@pytest.fixture
def service(temp_db):
    """Create PresetService with temporary database."""
    return PresetService(db_path=temp_db, auto_seed=False)


@pytest.fixture
def seeded_service(temp_db):
    """Create PresetService with seeded presets."""
    return PresetService(db_path=temp_db, auto_seed=True)


class TestGetPresetDbPath:
    """Tests for get_preset_db_path function."""

    def test_returns_path_string(self):
        """Returns a string path."""
        path = get_preset_db_path()
        assert isinstance(path, str)

    def test_path_ends_with_presets_db(self):
        """Path ends with presets.db."""
        path = get_preset_db_path()
        assert path.endswith("presets.db")

    def test_path_contains_data_directory(self):
        """Path contains data directory."""
        path = get_preset_db_path()
        assert "data" in path


class TestPresetServiceCategories:
    """Tests for CATEGORIES constant."""

    def test_style_is_universal(self):
        """Style category is universal."""
        assert PresetService.CATEGORIES["style"] == "universal"

    def test_lighting_is_universal(self):
        """Lighting category is universal."""
        assert PresetService.CATEGORIES["lighting"] == "universal"

    def test_mood_is_universal(self):
        """Mood category is universal."""
        assert PresetService.CATEGORIES["mood"] == "universal"

    def test_time_of_day_is_universal(self):
        """Time of day category is universal."""
        assert PresetService.CATEGORIES["time_of_day"] == "universal"

    def test_composition_is_keyframe(self):
        """Composition category is keyframe."""
        assert PresetService.CATEGORIES["composition"] == "keyframe"

    def test_color_grade_is_keyframe(self):
        """Color grade category is keyframe."""
        assert PresetService.CATEGORIES["color_grade"] == "keyframe"

    def test_camera_is_video(self):
        """Camera category is video."""
        assert PresetService.CATEGORIES["camera"] == "video"

    def test_motion_is_video(self):
        """Motion category is video."""
        assert PresetService.CATEGORIES["motion"] == "video"


class TestPresetServiceInit:
    """Tests for PresetService initialization."""

    def test_init_uses_provided_db_path(self, temp_db):
        """Uses provided database path."""
        service = PresetService(db_path=temp_db, auto_seed=False)
        assert service.db_path == temp_db

    def test_init_uses_default_db_path(self):
        """Uses default path when not provided."""
        with patch("infrastructure.preset_service.get_preset_db_path", return_value="/default/path.db"):
            with patch.object(PresetService, "_ensure_db"):
                with patch.object(PresetService, "get_preset_count", return_value=1):
                    service = PresetService(auto_seed=False)
                    assert service.db_path == "/default/path.db"

    def test_init_creates_database(self, temp_db):
        """Creates database file."""
        service = PresetService(db_path=temp_db, auto_seed=False)
        assert Path(temp_db).exists()

    def test_init_creates_tables(self, temp_db):
        """Creates required tables."""
        service = PresetService(db_path=temp_db, auto_seed=False)

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Check prompt_presets table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='prompt_presets'")
        assert cursor.fetchone() is not None

        # Check model_profiles table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='model_profiles'")
        assert cursor.fetchone() is not None

        conn.close()

    def test_init_auto_seeds_when_empty(self, temp_db):
        """Auto-seeds presets when database is empty."""
        service = PresetService(db_path=temp_db, auto_seed=True)
        count = service.get_preset_count()
        assert count > 0

    def test_init_no_auto_seed_option(self, temp_db):
        """Does not seed when auto_seed=False."""
        service = PresetService(db_path=temp_db, auto_seed=False)
        count = service.get_preset_count()
        assert count == 0


class TestEnsureDb:
    """Tests for _ensure_db method."""

    def test_creates_parent_directory(self, tmp_path):
        """Creates parent directory if it doesn't exist."""
        db_path = str(tmp_path / "subdir" / "nested" / "presets.db")
        service = PresetService(db_path=db_path, auto_seed=False)

        assert Path(db_path).parent.exists()

    def test_creates_index(self, temp_db):
        """Creates index on presets table."""
        service = PresetService(db_path=temp_db, auto_seed=False)

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_presets_category'")
        assert cursor.fetchone() is not None
        conn.close()


class TestGetConn:
    """Tests for _get_conn method."""

    def test_returns_connection(self, service):
        """Returns sqlite3 connection."""
        conn = service._get_conn()
        assert isinstance(conn, sqlite3.Connection)
        conn.close()

    def test_uses_row_factory(self, service):
        """Connection uses Row factory."""
        conn = service._get_conn()
        assert conn.row_factory == sqlite3.Row
        conn.close()


class TestAddPreset:
    """Tests for add_preset method."""

    def test_add_new_preset(self, service):
        """Adds a new preset."""
        result = service.add_preset(
            category="style",
            key="test_style",
            name_de="Teststil",
            prompt_text="test style prompt",
            phase="universal"
        )

        assert result is True
        assert service.get_preset_count() == 1

    def test_add_preset_with_english_name(self, service):
        """Adds preset with English name."""
        result = service.add_preset(
            category="style",
            key="test_style",
            name_de="Teststil",
            name_en="Test Style",
            prompt_text="test style prompt"
        )

        assert result is True
        presets = service.get_presets_by_category("style")
        assert presets[0]["name_en"] == "Test Style"

    def test_add_preset_with_sort_order(self, service):
        """Adds preset with sort order."""
        service.add_preset(
            category="style",
            key="second",
            name_de="Zweiter",
            prompt_text="second",
            sort_order=2
        )
        service.add_preset(
            category="style",
            key="first",
            name_de="Erster",
            prompt_text="first",
            sort_order=1
        )

        presets = service.get_presets_by_category("style")
        assert presets[0]["key"] == "first"
        assert presets[1]["key"] == "second"

    def test_update_existing_preset(self, service):
        """Updates existing preset."""
        service.add_preset(
            category="style",
            key="test",
            name_de="Original",
            prompt_text="original prompt"
        )
        service.add_preset(
            category="style",
            key="test",
            name_de="Updated",
            prompt_text="updated prompt"
        )

        presets = service.get_presets_by_category("style")
        assert len(presets) == 1
        assert presets[0]["name_de"] == "Updated"
        assert presets[0]["prompt_text"] == "updated prompt"


class TestGetPresetsByCategory:
    """Tests for get_presets_by_category method."""

    def test_get_empty_category(self, service):
        """Returns empty list for empty category."""
        presets = service.get_presets_by_category("style")
        assert presets == []

    def test_get_presets_returns_list(self, seeded_service):
        """Returns list of presets."""
        presets = seeded_service.get_presets_by_category("style")
        assert isinstance(presets, list)
        assert len(presets) > 0

    def test_get_presets_contains_expected_fields(self, seeded_service):
        """Presets contain expected fields."""
        presets = seeded_service.get_presets_by_category("style")
        preset = presets[0]

        assert "key" in preset
        assert "name_de" in preset
        assert "name_en" in preset
        assert "prompt_text" in preset
        assert "phase" in preset

    def test_get_presets_filters_by_category(self, seeded_service):
        """Only returns presets from specified category."""
        style_presets = seeded_service.get_presets_by_category("style")
        lighting_presets = seeded_service.get_presets_by_category("lighting")

        style_keys = {p["key"] for p in style_presets}
        lighting_keys = {p["key"] for p in lighting_presets}

        # Categories should have different presets
        assert style_keys != lighting_keys

    def test_get_presets_only_active(self, service):
        """Only returns active presets."""
        # Add active preset
        service.add_preset(
            category="style",
            key="active",
            name_de="Active",
            prompt_text="active"
        )

        # Manually deactivate a preset
        conn = service._get_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE prompt_presets SET is_active = 0 WHERE key = 'active'")
        conn.commit()
        conn.close()

        presets = service.get_presets_by_category("style")
        assert len(presets) == 0


class TestGetPresetsByPhase:
    """Tests for get_presets_by_phase method."""

    def test_get_universal_phase(self, seeded_service):
        """Returns presets for universal phase."""
        result = seeded_service.get_presets_by_phase("universal")

        assert isinstance(result, dict)
        assert "style" in result
        assert "lighting" in result
        assert "mood" in result
        assert "time_of_day" in result

    def test_get_keyframe_phase(self, seeded_service):
        """Returns presets for keyframe phase."""
        result = seeded_service.get_presets_by_phase("keyframe")

        assert "composition" in result
        assert "color_grade" in result

    def test_get_video_phase(self, seeded_service):
        """Returns presets for video phase."""
        result = seeded_service.get_presets_by_phase("video")

        assert "camera" in result
        assert "motion" in result

    def test_phase_presets_are_grouped(self, seeded_service):
        """Presets are grouped by category."""
        result = seeded_service.get_presets_by_phase("universal")

        for category, presets in result.items():
            assert isinstance(presets, list)
            for preset in presets:
                assert "key" in preset
                assert "name_de" in preset


class TestGetDropdownChoices:
    """Tests for get_dropdown_choices method."""

    def test_returns_tuples(self, seeded_service):
        """Returns list of tuples."""
        choices = seeded_service.get_dropdown_choices("style")
        assert isinstance(choices, list)
        assert all(isinstance(c, tuple) and len(c) == 2 for c in choices)

    def test_includes_none_option(self, seeded_service):
        """Includes 'None' option by default."""
        choices = seeded_service.get_dropdown_choices("style")
        assert choices[0] == ("-- Keine --", "none")

    def test_excludes_none_option(self, seeded_service):
        """Can exclude 'None' option."""
        choices = seeded_service.get_dropdown_choices("style", include_none=False)
        assert ("-- Keine --", "none") not in choices

    def test_choices_have_label_and_value(self, seeded_service):
        """Each choice has label and value."""
        choices = seeded_service.get_dropdown_choices("style", include_none=False)
        for label, value in choices:
            assert isinstance(label, str) and len(label) > 0
            assert isinstance(value, str) and len(value) > 0


class TestGetPromptText:
    """Tests for get_prompt_text method."""

    def test_get_existing_preset(self, seeded_service):
        """Returns prompt text for existing preset."""
        text = seeded_service.get_prompt_text("style", "cinematic")
        assert text is not None
        assert "cinematic" in text.lower()

    def test_get_nonexistent_preset(self, seeded_service):
        """Returns None for non-existent preset."""
        text = seeded_service.get_prompt_text("style", "nonexistent_key")
        assert text is None

    def test_get_none_key(self, seeded_service):
        """Returns None for 'none' key."""
        text = seeded_service.get_prompt_text("style", "none")
        assert text is None

    def test_get_empty_key(self, seeded_service):
        """Returns None for empty key."""
        text = seeded_service.get_prompt_text("style", "")
        assert text is None

    def test_get_wrong_category(self, seeded_service):
        """Returns None for wrong category."""
        # 'cinematic' exists in 'style' but not in 'lighting'
        text = seeded_service.get_prompt_text("lighting", "cinematic")
        assert text is None


class TestBuildPrompt:
    """Tests for build_prompt method."""

    def test_build_base_prompt_only(self, seeded_service):
        """Returns base prompt when no presets selected."""
        result = seeded_service.build_prompt("A beautiful scene")
        assert result == "A beautiful scene"

    def test_build_with_style(self, seeded_service):
        """Adds style preset to prompt."""
        result = seeded_service.build_prompt("A scene", style="cinematic")
        assert "A scene" in result
        assert "cinematic" in result.lower()

    def test_build_with_lighting(self, seeded_service):
        """Adds lighting preset to prompt."""
        result = seeded_service.build_prompt("A scene", lighting="golden_hour")
        assert "A scene" in result
        assert "golden" in result.lower()

    def test_build_with_mood(self, seeded_service):
        """Adds mood preset to prompt."""
        result = seeded_service.build_prompt("A scene", mood="dramatic")
        assert "A scene" in result
        assert "dramatic" in result.lower()

    def test_build_with_time_of_day(self, seeded_service):
        """Adds time of day preset to prompt."""
        result = seeded_service.build_prompt("A scene", time_of_day="sunset")
        assert "A scene" in result
        assert "sunset" in result.lower()

    def test_build_with_camera(self, seeded_service):
        """Adds camera preset to prompt."""
        result = seeded_service.build_prompt("A scene", camera="pan_left")
        assert "A scene" in result
        assert "pan" in result.lower()

    def test_build_with_motion(self, seeded_service):
        """Adds motion preset to prompt."""
        result = seeded_service.build_prompt("A scene", motion="slow_motion")
        assert "A scene" in result
        assert "slow" in result.lower()

    def test_build_with_multiple_presets(self, seeded_service):
        """Combines multiple presets."""
        result = seeded_service.build_prompt(
            "A scene",
            style="cinematic",
            lighting="golden_hour",
            mood="peaceful"
        )

        assert "A scene" in result
        # Parts are joined by ", "
        parts = result.split(", ")
        assert len(parts) >= 4  # base + 3 presets

    def test_build_ignores_none_values(self, seeded_service):
        """Ignores None preset values."""
        result = seeded_service.build_prompt("A scene", style=None, lighting=None)
        assert result == "A scene"

    def test_build_ignores_none_string(self, seeded_service):
        """Ignores 'none' string values."""
        result = seeded_service.build_prompt("A scene", style="none")
        assert result == "A scene"

    def test_build_strips_base_prompt(self, seeded_service):
        """Strips whitespace from base prompt."""
        result = seeded_service.build_prompt("  A scene with spaces  ")
        assert result == "A scene with spaces"


class TestSeedDefaultPresets:
    """Tests for seed_default_presets method."""

    def test_seed_returns_count(self, service):
        """Returns count of seeded presets."""
        count = service.seed_default_presets()
        assert count > 0

    def test_seed_creates_style_presets(self, service):
        """Creates style presets."""
        service.seed_default_presets()
        presets = service.get_presets_by_category("style")
        assert len(presets) >= 5

    def test_seed_creates_lighting_presets(self, service):
        """Creates lighting presets."""
        service.seed_default_presets()
        presets = service.get_presets_by_category("lighting")
        assert len(presets) >= 5

    def test_seed_creates_mood_presets(self, service):
        """Creates mood presets."""
        service.seed_default_presets()
        presets = service.get_presets_by_category("mood")
        assert len(presets) >= 5

    def test_seed_creates_time_of_day_presets(self, service):
        """Creates time of day presets."""
        service.seed_default_presets()
        presets = service.get_presets_by_category("time_of_day")
        assert len(presets) >= 5

    def test_seed_creates_composition_presets(self, service):
        """Creates composition presets."""
        service.seed_default_presets()
        presets = service.get_presets_by_category("composition")
        assert len(presets) >= 5

    def test_seed_creates_color_grade_presets(self, service):
        """Creates color grade presets."""
        service.seed_default_presets()
        presets = service.get_presets_by_category("color_grade")
        assert len(presets) >= 5

    def test_seed_creates_camera_presets(self, service):
        """Creates camera presets."""
        service.seed_default_presets()
        presets = service.get_presets_by_category("camera")
        assert len(presets) >= 5

    def test_seed_creates_motion_presets(self, service):
        """Creates motion presets."""
        service.seed_default_presets()
        presets = service.get_presets_by_category("motion")
        assert len(presets) >= 3

    def test_seed_presets_have_german_names(self, service):
        """Seeded presets have German names."""
        service.seed_default_presets()
        presets = service.get_presets_by_category("style")
        for preset in presets:
            assert preset["name_de"] is not None
            assert len(preset["name_de"]) > 0


class TestGetPresetCount:
    """Tests for get_preset_count method."""

    def test_count_empty_database(self, service):
        """Returns 0 for empty database."""
        assert service.get_preset_count() == 0

    def test_count_after_adding(self, service):
        """Returns correct count after adding presets."""
        service.add_preset("style", "test1", "Test 1", "prompt 1")
        assert service.get_preset_count() == 1

        service.add_preset("style", "test2", "Test 2", "prompt 2")
        assert service.get_preset_count() == 2

    def test_count_only_active(self, service):
        """Only counts active presets."""
        service.add_preset("style", "test", "Test", "prompt")

        # Deactivate the preset
        conn = service._get_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE prompt_presets SET is_active = 0 WHERE key = 'test'")
        conn.commit()
        conn.close()

        assert service.get_preset_count() == 0

    def test_count_after_seeding(self, temp_db):
        """Returns correct count after seeding."""
        service = PresetService(db_path=temp_db, auto_seed=True)
        count = service.get_preset_count()
        assert count > 50  # Default seed has many presets


class TestKnownPresets:
    """Tests for specific known presets."""

    def test_cinematic_style(self, seeded_service):
        """Cinematic style preset exists and has correct prompt."""
        text = seeded_service.get_prompt_text("style", "cinematic")
        assert text is not None
        assert "cinematic" in text.lower()
        assert "film" in text.lower()

    def test_golden_hour_lighting(self, seeded_service):
        """Golden hour lighting preset exists."""
        text = seeded_service.get_prompt_text("lighting", "golden_hour")
        assert text is not None
        assert "golden" in text.lower()

    def test_dramatic_mood(self, seeded_service):
        """Dramatic mood preset exists."""
        text = seeded_service.get_prompt_text("mood", "dramatic")
        assert text is not None
        assert "dramatic" in text.lower()

    def test_sunset_time(self, seeded_service):
        """Sunset time of day preset exists."""
        text = seeded_service.get_prompt_text("time_of_day", "sunset")
        assert text is not None
        assert "sunset" in text.lower()

    def test_pan_left_camera(self, seeded_service):
        """Pan left camera preset exists."""
        text = seeded_service.get_prompt_text("camera", "pan_left")
        assert text is not None
        assert "pan" in text.lower()

    def test_slow_motion(self, seeded_service):
        """Slow motion preset exists."""
        text = seeded_service.get_prompt_text("motion", "slow_motion")
        assert text is not None
        assert "slow" in text.lower()
