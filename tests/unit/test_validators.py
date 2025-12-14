"""Unit tests for domain.validators validation models"""
import pytest
from pydantic import ValidationError

from domain import validators


class TestKeyframeGeneratorInput:
    """Tests for KeyframeGeneratorInput"""

    @pytest.mark.unit
    def test_valid_input(self):
        """Should accept values within allowed range"""
        payload = validators.KeyframeGeneratorInput(variants_per_shot=3, base_seed=42)

        assert payload.variants_per_shot == 3
        assert payload.base_seed == 42

    @pytest.mark.unit
    @pytest.mark.parametrize("variants", [0, -1, 11])
    def test_invalid_variants(self, variants):
        """Should reject variant counts outside bounds"""
        with pytest.raises(ValidationError):
            validators.KeyframeGeneratorInput(variants_per_shot=variants, base_seed=1)

    @pytest.mark.unit
    @pytest.mark.parametrize("seed", [-1, 3_000_000_000])
    def test_invalid_seed(self, seed):
        """Should reject seeds outside int32 range"""
        with pytest.raises(ValidationError):
            validators.KeyframeGeneratorInput(variants_per_shot=2, base_seed=seed)


class TestVideoGeneratorInput:
    """Tests for VideoGeneratorInput"""

    @pytest.mark.unit
    def test_valid_video_input(self):
        """Should accept fps and segment duration within limits"""
        payload = validators.VideoGeneratorInput(fps=24, max_segment_seconds=6.5)

        assert payload.fps == 24
        assert payload.max_segment_seconds == pytest.approx(6.5)

    @pytest.mark.unit
    @pytest.mark.parametrize("fps", [0, 8, 40])
    def test_invalid_fps(self, fps):
        """Should validate fps bounds"""
        with pytest.raises(ValidationError):
            validators.VideoGeneratorInput(fps=fps, max_segment_seconds=3.0)

    @pytest.mark.unit
    @pytest.mark.parametrize("seconds", [0, -0.1, 12.5])
    def test_invalid_segment_duration(self, seconds):
        """Should enforce positive duration and max limit"""
        with pytest.raises(ValidationError):
            validators.VideoGeneratorInput(fps=24, max_segment_seconds=seconds)


class TestProjectCreateInput:
    """Tests for ProjectCreateInput"""

    @pytest.mark.unit
    def test_valid_project_name(self):
        """Should accept trimmed, valid names"""
        payload = validators.ProjectCreateInput(name="  My Project  ")

        assert payload.name == "My Project"

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "name",
        ["", "   ", "Project/Name", "Name?", "A" * 101, "CON", "LPT1"],
    )
    def test_invalid_project_names(self, name):
        """Should reject empty, invalid, or reserved names"""
        with pytest.raises(ValidationError):
            validators.ProjectCreateInput(name=name)


class TestSettingsInput:
    """Tests for SettingsInput"""

    @pytest.mark.unit
    def test_valid_settings(self):
        """Should normalize and accept valid settings"""
        payload = validators.SettingsInput(
            comfy_url="http://127.0.0.1:8188 ",
            comfy_root="/opt/comfyui ",
        )

        assert payload.comfy_url == "http://127.0.0.1:8188"
        assert payload.comfy_root == "/opt/comfyui"

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "url",
        ["", "127.0.0.1:8188", "ftp://example.com", "http://not a url"],
    )
    def test_invalid_comfy_url(self, url):
        """Should validate URL format and scheme"""
        with pytest.raises(ValidationError):
            validators.SettingsInput(comfy_url=url, comfy_root="/opt/comfyui")

    @pytest.mark.unit
    @pytest.mark.parametrize("root", ["", "ab", "relative/path"])
    def test_invalid_comfy_root(self, root):
        """Should require absolute, non-empty root paths"""
        with pytest.raises(ValidationError):
            validators.SettingsInput(comfy_url="http://localhost:8188", comfy_root=root)


class TestFileInputs:
    """Tests for file selection validators"""

    @pytest.mark.unit
    def test_storyboard_file_validation(self):
        """Storyboard file must be json and not placeholder text"""
        valid = validators.StoryboardFileInput(storyboard_file="story.json")
        assert valid.storyboard_file == "story.json"

        with pytest.raises(ValidationError):
            validators.StoryboardFileInput(storyboard_file="")
        with pytest.raises(ValidationError):
            validators.StoryboardFileInput(storyboard_file="No storyboards found")
        with pytest.raises(ValidationError):
            validators.StoryboardFileInput(storyboard_file="story.txt")

    @pytest.mark.unit
    def test_workflow_file_validation(self):
        """Workflow file must be json and not placeholder text"""
        valid = validators.WorkflowFileInput(workflow_file="workflow.json")
        assert valid.workflow_file == "workflow.json"

        with pytest.raises(ValidationError):
            validators.WorkflowFileInput(workflow_file="")
        with pytest.raises(ValidationError):
            validators.WorkflowFileInput(workflow_file="No workflows available")
        with pytest.raises(ValidationError):
            validators.WorkflowFileInput(workflow_file="workflow.yaml")

    @pytest.mark.unit
    def test_selection_file_validation(self):
        """Selection file must be a json file"""
        valid = validators.SelectionFileInput(selection_file="selection.json")
        assert valid.selection_file == "selection.json"

        with pytest.raises(ValidationError):
            validators.SelectionFileInput(selection_file="")
        with pytest.raises(ValidationError):
            validators.SelectionFileInput(selection_file="selection.yaml")


class TestValidatorFunctionsDirect:
    """Direct calls into validator helpers to cover custom branches (bypassing Field ge/le)."""

    @pytest.mark.unit
    @pytest.mark.parametrize("value", [0, 11])
    def test_validate_variants_direct(self, value):
        """Direct variant validation should raise on out-of-range values."""
        with pytest.raises(ValueError):
            validators.KeyframeGeneratorInput.validate_variants(value)

    @pytest.mark.unit
    @pytest.mark.parametrize("value", [-1, 2_200_000_000])
    def test_validate_seed_direct(self, value):
        """Direct seed validation should enforce bounds."""
        with pytest.raises(ValueError):
            validators.KeyframeGeneratorInput.validate_seed(value)

    @pytest.mark.unit
    @pytest.mark.parametrize("value", [8, 40])
    def test_validate_fps_direct(self, value):
        """Direct fps validation should enforce limits."""
        with pytest.raises(ValueError):
            validators.VideoGeneratorInput.validate_fps(value)

    @pytest.mark.unit
    @pytest.mark.parametrize("value", [0.0, 11.0])
    def test_validate_segment_duration_direct(self, value):
        """Direct segment duration validation should reject invalid durations."""
        with pytest.raises(ValueError):
            validators.VideoGeneratorInput.validate_segment_duration(value)

    @pytest.mark.unit
    def test_validate_comfy_root_relative_path(self):
        """Direct comfy_root validation should reject relative paths."""
        with pytest.raises(ValueError):
            validators.SettingsInput.validate_comfy_root("relative/path")


class TestValidatorHelpersDirect:
    """Covers custom validators not reached via Field constraints."""

    @pytest.mark.unit
    def test_project_name_validator_direct(self):
        """Whitespace and overlong names should trigger custom errors."""
        with pytest.raises(ValueError):
            validators.ProjectCreateInput.validate_name("   ")
        with pytest.raises(ValueError):
            validators.ProjectCreateInput.validate_name("x" * 101)

    @pytest.mark.unit
    def test_settings_validators_direct(self):
        """Invalid URL/Root should raise when called directly."""
        with pytest.raises(ValueError):
            validators.SettingsInput.validate_comfy_url("invalid")
        with pytest.raises(ValueError):
            validators.SettingsInput.validate_comfy_root("ab")
        with pytest.raises(ValueError):
            validators.SettingsInput.validate_comfy_url("   ")
        with pytest.raises(ValueError):
            validators.SettingsInput.validate_comfy_root("   ")

    @pytest.mark.unit
    def test_file_validators_direct(self):
        """Storyboard/workflow/selection validators handle bad inputs."""
        with pytest.raises(ValueError):
            validators.StoryboardFileInput.validate_storyboard_file("story.txt")
        with pytest.raises(ValueError):
            validators.WorkflowFileInput.validate_workflow_file("workflow.txt")
        with pytest.raises(ValueError):
            validators.SelectionFileInput.validate_selection_file("")
        with pytest.raises(ValueError):
            validators.StoryboardFileInput.validate_storyboard_file("   ")
        with pytest.raises(ValueError):
            validators.WorkflowFileInput.validate_workflow_file("   ")
