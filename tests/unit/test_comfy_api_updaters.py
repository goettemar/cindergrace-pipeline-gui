"""Unit tests for ComfyAPI NodeUpdaters"""
import pytest
from infrastructure.comfy_api.updaters import (
    CLIPTextEncodeUpdater,
    SaveImageUpdater,
    SaveVideoUpdater,
    RandomNoiseUpdater,
    KSamplerUpdater,
    BasicSchedulerUpdater,
    EmptyLatentImageUpdater,
    LoadImageUpdater,
    HunyuanVideoSamplerUpdater,
    GenericSeedUpdater,
    default_updaters,
    _merge_params,
)


class TestMergeParams:
    """Test _merge_params helper function"""

    @pytest.mark.unit
    def test_merge_params_first_non_none(self):
        """Should return first non-None value"""
        # Act
        result = _merge_params(None, "value", "other")

        # Assert
        assert result == "value"

    @pytest.mark.unit
    def test_merge_params_all_none(self):
        """Should return None if all values are None"""
        # Act
        result = _merge_params(None, None, None)

        # Assert
        assert result is None

    @pytest.mark.unit
    def test_merge_params_first_value(self):
        """Should return first value even if others exist"""
        # Act
        result = _merge_params("first", "second", "third")

        # Assert
        assert result == "first"


class TestCLIPTextEncodeUpdater:
    """Test CLIPTextEncodeUpdater"""

    @pytest.mark.unit
    def test_update_with_prompt(self):
        """Should update text input with prompt"""
        # Arrange
        updater = CLIPTextEncodeUpdater()
        node_data = {"inputs": {}}
        params = {"prompt": "test prompt"}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["text"] == "test prompt"

    @pytest.mark.unit
    def test_update_without_prompt(self):
        """Should not modify node if prompt is None"""
        # Arrange
        updater = CLIPTextEncodeUpdater()
        node_data = {"inputs": {}}
        params = {}

        # Act
        updater.update(node_data, params)

        # Assert
        assert "text" not in node_data["inputs"]

    @pytest.mark.unit
    def test_update_creates_inputs_if_missing(self):
        """Should create inputs dict if not present"""
        # Arrange
        updater = CLIPTextEncodeUpdater()
        node_data = {}
        params = {"prompt": "test"}

        # Act
        updater.update(node_data, params)

        # Assert
        assert "inputs" in node_data
        assert node_data["inputs"]["text"] == "test"


class TestSaveImageUpdater:
    """Test SaveImageUpdater"""

    @pytest.mark.unit
    def test_update_with_filename_prefix(self):
        """Should update filename_prefix"""
        # Arrange
        updater = SaveImageUpdater()
        node_data = {"inputs": {}}
        params = {"filename_prefix": "output_"}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["filename_prefix"] == "output_"

    @pytest.mark.unit
    def test_update_without_filename_prefix(self):
        """Should not modify node if filename_prefix is None"""
        # Arrange
        updater = SaveImageUpdater()
        node_data = {"inputs": {}}
        params = {}

        # Act
        updater.update(node_data, params)

        # Assert
        assert "filename_prefix" not in node_data["inputs"]


class TestSaveVideoUpdater:
    """Test SaveVideoUpdater"""

    @pytest.mark.unit
    def test_update_with_filename_prefix(self):
        """Should update filename_prefix for video"""
        # Arrange
        updater = SaveVideoUpdater()
        node_data = {"inputs": {}}
        params = {"filename_prefix": "video_"}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["filename_prefix"] == "video_"


class TestRandomNoiseUpdater:
    """Test RandomNoiseUpdater"""

    @pytest.mark.unit
    def test_update_with_noise_seed(self):
        """Should update noise_seed if present"""
        # Arrange
        updater = RandomNoiseUpdater()
        node_data = {"inputs": {"noise_seed": 0}}
        params = {"seed": 1234}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["noise_seed"] == 1234

    @pytest.mark.unit
    def test_update_with_seed(self):
        """Should update seed if present"""
        # Arrange
        updater = RandomNoiseUpdater()
        node_data = {"inputs": {"seed": 0}}
        params = {"seed": 5678}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["seed"] == 5678

    @pytest.mark.unit
    def test_update_both_seeds(self):
        """Should update both noise_seed and seed if present"""
        # Arrange
        updater = RandomNoiseUpdater()
        node_data = {"inputs": {"noise_seed": 0, "seed": 0}}
        params = {"seed": 9999}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["noise_seed"] == 9999
        assert node_data["inputs"]["seed"] == 9999


class TestKSamplerUpdater:
    """Test KSamplerUpdater"""

    @pytest.mark.unit
    def test_update_seed(self):
        """Should update seed if present in inputs"""
        # Arrange
        updater = KSamplerUpdater()
        node_data = {"inputs": {"seed": 0}}
        params = {"seed": 1234}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["seed"] == 1234

    @pytest.mark.unit
    def test_update_steps(self):
        """Should update steps if present in inputs"""
        # Arrange
        updater = KSamplerUpdater()
        node_data = {"inputs": {"steps": 20}}
        params = {"steps": 30}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["steps"] == 30

    @pytest.mark.unit
    def test_update_cfg(self):
        """Should update cfg if present in inputs"""
        # Arrange
        updater = KSamplerUpdater()
        node_data = {"inputs": {"cfg": 7.0}}
        params = {"cfg": 8.5}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["cfg"] == 8.5

    @pytest.mark.unit
    def test_update_all_params(self):
        """Should update all params if present"""
        # Arrange
        updater = KSamplerUpdater()
        node_data = {"inputs": {"seed": 0, "steps": 20, "cfg": 7.0}}
        params = {"seed": 5555, "steps": 50, "cfg": 9.0}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["seed"] == 5555
        assert node_data["inputs"]["steps"] == 50
        assert node_data["inputs"]["cfg"] == 9.0

    @pytest.mark.unit
    def test_update_skips_missing_keys(self):
        """Should only update keys that exist in inputs"""
        # Arrange
        updater = KSamplerUpdater()
        node_data = {"inputs": {"seed": 0}}  # Only seed, no steps/cfg
        params = {"seed": 1111, "steps": 30, "cfg": 8.0}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["seed"] == 1111
        assert "steps" not in node_data["inputs"]
        assert "cfg" not in node_data["inputs"]


class TestBasicSchedulerUpdater:
    """Test BasicSchedulerUpdater"""

    @pytest.mark.unit
    def test_update_steps(self):
        """Should update steps if present"""
        # Arrange
        updater = BasicSchedulerUpdater()
        node_data = {"inputs": {"steps": 20}}
        params = {"steps": 40}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["steps"] == 40

    @pytest.mark.unit
    def test_update_without_steps_param(self):
        """Should not modify if steps param is None"""
        # Arrange
        updater = BasicSchedulerUpdater()
        node_data = {"inputs": {"steps": 20}}
        params = {}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["steps"] == 20  # Unchanged


class TestEmptyLatentImageUpdater:
    """Test EmptyLatentImageUpdater"""

    @pytest.mark.unit
    def test_update_width_and_height(self):
        """Should update width and height"""
        # Arrange
        updater = EmptyLatentImageUpdater()
        node_data = {"inputs": {"width": 512, "height": 512}}
        params = {"width": 1024, "height": 576}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["width"] == 1024
        assert node_data["inputs"]["height"] == 576

    @pytest.mark.unit
    def test_update_capitalized_keys(self):
        """Should update W and H for nodes using capitalized keys"""
        # Arrange
        updater = EmptyLatentImageUpdater()
        node_data = {"inputs": {"W": 512, "H": 512}}
        params = {"width": 1920, "height": 1080}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["W"] == 1920
        assert node_data["inputs"]["H"] == 1080

    @pytest.mark.unit
    def test_update_only_width(self):
        """Should update only width if height is None"""
        # Arrange
        updater = EmptyLatentImageUpdater()
        node_data = {"inputs": {"width": 512, "height": 512}}
        params = {"width": 1024}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["width"] == 1024
        assert node_data["inputs"]["height"] == 512  # Unchanged

    @pytest.mark.unit
    def test_update_skips_if_both_none(self):
        """Should skip update if both width and height are None"""
        # Arrange
        updater = EmptyLatentImageUpdater()
        node_data = {"inputs": {"width": 512, "height": 512}}
        params = {}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["width"] == 512  # Unchanged
        assert node_data["inputs"]["height"] == 512  # Unchanged


class TestLoadImageUpdater:
    """Test LoadImageUpdater"""

    @pytest.mark.unit
    def test_update_with_startframe_path(self):
        """Should update image path using startframe_path"""
        # Arrange
        updater = LoadImageUpdater()
        node_data = {"inputs": {"image": ""}}
        params = {"startframe_path": "/path/to/image.png"}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["image"] == "/path/to/image.png"

    @pytest.mark.unit
    def test_update_with_start_frame_path(self):
        """Should update using start_frame_path as fallback"""
        # Arrange
        updater = LoadImageUpdater()
        node_data = {"inputs": {"filename": ""}}
        params = {"start_frame_path": "/path/to/frame.png"}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["filename"] == "/path/to/frame.png"

    @pytest.mark.unit
    def test_update_with_image_path(self):
        """Should update using image_path as fallback"""
        # Arrange
        updater = LoadImageUpdater()
        node_data = {"inputs": {"path": ""}}
        params = {"image_path": "/path/to/img.png"}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["path"] == "/path/to/img.png"

    @pytest.mark.unit
    def test_update_all_keys(self):
        """Should update all supported keys"""
        # Arrange
        updater = LoadImageUpdater()
        node_data = {"inputs": {"image": "", "filename": "", "path": ""}}
        params = {"startframe_path": "/path/to/image.png"}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["image"] == "/path/to/image.png"
        assert node_data["inputs"]["filename"] == "/path/to/image.png"
        assert node_data["inputs"]["path"] == "/path/to/image.png"


class TestHunyuanVideoSamplerUpdater:
    """Test HunyuanVideoSamplerUpdater"""

    @pytest.mark.unit
    def test_update_seed(self):
        """Should update seed if present"""
        # Arrange
        updater = HunyuanVideoSamplerUpdater()
        node_data = {"inputs": {"seed": 0}}
        params = {"seed": 7777}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["seed"] == 7777

    @pytest.mark.unit
    def test_update_steps(self):
        """Should update steps if present"""
        # Arrange
        updater = HunyuanVideoSamplerUpdater()
        node_data = {"inputs": {"steps": 20}}
        params = {"steps": 50}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["steps"] == 50

    @pytest.mark.unit
    def test_update_frames_variants(self):
        """Should update frame count using various param names"""
        # Arrange
        updater = HunyuanVideoSamplerUpdater()

        # Test with frames param
        node_data1 = {"inputs": {"num_frames": 30}}
        updater.update(node_data1, {"frames": 60})
        assert node_data1["inputs"]["num_frames"] == 60

        # Test with num_frames param
        node_data2 = {"inputs": {"frame_count": 30}}
        updater.update(node_data2, {"num_frames": 90})
        assert node_data2["inputs"]["frame_count"] == 90

        # Test with frame_count param
        node_data3 = {"inputs": {"frames": 30}}
        updater.update(node_data3, {"frame_count": 120})
        assert node_data3["inputs"]["frames"] == 120

    @pytest.mark.unit
    def test_update_all_frame_keys(self):
        """Should update all frame-related keys"""
        # Arrange
        updater = HunyuanVideoSamplerUpdater()
        node_data = {"inputs": {"num_frames": 30, "frame_count": 30, "frames": 30}}
        params = {"frames": 60}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["num_frames"] == 60
        assert node_data["inputs"]["frame_count"] == 60
        assert node_data["inputs"]["frames"] == 60


class TestGenericSeedUpdater:
    """Test GenericSeedUpdater"""

    @pytest.mark.unit
    def test_applies_to_any_node(self):
        """Should apply to any node type"""
        # Arrange
        updater = GenericSeedUpdater()

        # Act & Assert
        assert updater.applies_to("AnyNode") is True
        assert updater.applies_to("RandomType") is True
        assert updater.applies_to("") is True

    @pytest.mark.unit
    def test_update_seed(self):
        """Should update seed if present"""
        # Arrange
        updater = GenericSeedUpdater()
        node_data = {"inputs": {"seed": 0}}
        params = {"seed": 4444}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["seed"] == 4444

    @pytest.mark.unit
    def test_update_noise_seed(self):
        """Should update noise_seed if present"""
        # Arrange
        updater = GenericSeedUpdater()
        node_data = {"inputs": {"noise_seed": 0}}
        params = {"seed": 5555}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["noise_seed"] == 5555

    @pytest.mark.unit
    def test_update_both_seeds(self):
        """Should update both seed and noise_seed"""
        # Arrange
        updater = GenericSeedUpdater()
        node_data = {"inputs": {"seed": 0, "noise_seed": 0}}
        params = {"seed": 6666}

        # Act
        updater.update(node_data, params)

        # Assert
        assert node_data["inputs"]["seed"] == 6666
        assert node_data["inputs"]["noise_seed"] == 6666


class TestDefaultUpdaters:
    """Test default_updaters factory"""

    @pytest.mark.unit
    def test_returns_all_updaters(self):
        """Should return all default updaters"""
        # Act
        updaters = list(default_updaters())

        # Assert
        assert len(updaters) == 10
        assert isinstance(updaters[0], CLIPTextEncodeUpdater)
        assert isinstance(updaters[1], SaveImageUpdater)
        assert isinstance(updaters[2], SaveVideoUpdater)
        assert isinstance(updaters[3], RandomNoiseUpdater)
        assert isinstance(updaters[4], KSamplerUpdater)
        assert isinstance(updaters[5], BasicSchedulerUpdater)
        assert isinstance(updaters[6], EmptyLatentImageUpdater)
        assert isinstance(updaters[7], LoadImageUpdater)
        assert isinstance(updaters[8], HunyuanVideoSamplerUpdater)
        assert isinstance(updaters[9], GenericSeedUpdater)
