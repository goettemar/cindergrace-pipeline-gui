"""Unit tests for CharacterLoraService - Character-Model compatibility validation"""
import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from services.character_lora_service import CharacterLoraService, CharacterLora


class TestCharacterLoraDataclass:
    """Test CharacterLora dataclass with compatible_models field"""

    @pytest.mark.unit
    def test_character_lora_without_models(self):
        """CharacterLora should work without compatible_models"""
        lora = CharacterLora(
            id="cg_elena",
            name="Elena",
            trigger_word="elena",
            lora_file="cg_elena.safetensors",
            lora_path="/path/to/cg_elena.safetensors",
            strength=1.0
        )
        assert lora.compatible_models is None

    @pytest.mark.unit
    def test_character_lora_with_models(self):
        """CharacterLora should store compatible_models list"""
        compatible = ["diffusion_models/flux1-dev.safetensors"]
        lora = CharacterLora(
            id="cg_elena",
            name="Elena",
            trigger_word="elena",
            lora_file="cg_elena.safetensors",
            lora_path="/path/to/cg_elena.safetensors",
            strength=1.0,
            compatible_models=compatible
        )
        assert lora.compatible_models == compatible


class TestLoadModelsFile:
    """Test _load_models_file method - returns (model_type, compatible_models) tuple"""

    @pytest.mark.unit
    def test_load_models_file_not_exists(self):
        """Should return (None, None) when .models file doesn't exist"""
        service = CharacterLoraService()
        model_type, models = service._load_models_file("/nonexistent/path.safetensors")
        assert model_type is None
        assert models is None

    @pytest.mark.unit
    def test_load_models_file_empty(self):
        """Should return (None, None) for empty .models file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.safetensors', delete=False) as sf:
            sf_path = sf.name
        models_path = sf_path.rsplit('.', 1)[0] + '.models'

        try:
            # Create empty .models file
            with open(models_path, 'w') as f:
                f.write("")

            service = CharacterLoraService()
            model_type, models = service._load_models_file(sf_path)
            assert model_type is None
            assert models is None
        finally:
            os.unlink(sf_path)
            if os.path.exists(models_path):
                os.unlink(models_path)

    @pytest.mark.unit
    def test_load_models_file_with_content(self):
        """Should parse .models file correctly"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.safetensors', delete=False) as sf:
            sf_path = sf.name
        models_path = sf_path.rsplit('.', 1)[0] + '.models'

        try:
            # Create .models file with content
            with open(models_path, 'w') as f:
                f.write("# Comment line\n")
                f.write("diffusion_models/flux1-dev.safetensors\n")
                f.write("\n")  # Empty line
                f.write("diffusion_models/flux1-krea-dev.safetensors\n")

            service = CharacterLoraService()
            model_type, models = service._load_models_file(sf_path)

            assert model_type is None  # No type= line in this test
            assert models is not None
            assert len(models) == 2
            assert "diffusion_models/flux1-dev.safetensors" in models
            assert "diffusion_models/flux1-krea-dev.safetensors" in models
        finally:
            os.unlink(sf_path)
            if os.path.exists(models_path):
                os.unlink(models_path)

    @pytest.mark.unit
    def test_load_models_file_with_type(self):
        """Should parse type= line from .models file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.safetensors', delete=False) as sf:
            sf_path = sf.name
        models_path = sf_path.rsplit('.', 1)[0] + '.models'

        try:
            with open(models_path, 'w') as f:
                f.write("type=flux\n")
                f.write("diffusion_models/flux1-dev.safetensors\n")

            service = CharacterLoraService()
            model_type, models = service._load_models_file(sf_path)

            assert model_type == "flux"
            assert models is not None
            assert len(models) == 1
        finally:
            os.unlink(sf_path)
            if os.path.exists(models_path):
                os.unlink(models_path)

    @pytest.mark.unit
    def test_load_models_file_only_comments(self):
        """Should return (None, None) when file contains only comments"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.safetensors', delete=False) as sf:
            sf_path = sf.name
        models_path = sf_path.rsplit('.', 1)[0] + '.models'

        try:
            with open(models_path, 'w') as f:
                f.write("# Comment 1\n")
                f.write("# Comment 2\n")

            service = CharacterLoraService()
            model_type, models = service._load_models_file(sf_path)
            assert model_type is None
            assert models is None
        finally:
            os.unlink(sf_path)
            if os.path.exists(models_path):
                os.unlink(models_path)

    @pytest.mark.unit
    def test_load_models_file_type_only(self):
        """Should return type without models when only type= is present"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.safetensors', delete=False) as sf:
            sf_path = sf.name
        models_path = sf_path.rsplit('.', 1)[0] + '.models'

        try:
            with open(models_path, 'w') as f:
                f.write("type=sdxl\n")

            service = CharacterLoraService()
            model_type, models = service._load_models_file(sf_path)
            assert model_type == "sdxl"
            assert models is None
        finally:
            os.unlink(sf_path)
            if os.path.exists(models_path):
                os.unlink(models_path)


class TestHasModelRestrictions:
    """Test has_model_restrictions method"""

    @pytest.mark.unit
    def test_has_model_restrictions_no_lora(self):
        """Should return False when character doesn't exist"""
        service = CharacterLoraService()
        with patch.object(service, 'scan_loras', return_value=[]):
            result = service.has_model_restrictions("nonexistent")
        assert result is False

    @pytest.mark.unit
    def test_has_model_restrictions_no_models_file(self):
        """Should return False when character has no .models file"""
        service = CharacterLoraService()
        lora = CharacterLora(
            id="cg_elena",
            name="Elena",
            trigger_word="elena",
            lora_file="cg_elena.safetensors",
            lora_path="/path/to/cg_elena.safetensors",
            strength=1.0,
            compatible_models=None
        )
        with patch.object(service, 'scan_loras', return_value=[lora]):
            result = service.has_model_restrictions("cg_elena")
        assert result is False

    @pytest.mark.unit
    def test_has_model_restrictions_with_models(self):
        """Should return True when character has .models file"""
        service = CharacterLoraService()
        lora = CharacterLora(
            id="cg_elena",
            name="Elena",
            trigger_word="elena",
            lora_file="cg_elena.safetensors",
            lora_path="/path/to/cg_elena.safetensors",
            strength=1.0,
            compatible_models=["diffusion_models/flux1-dev.safetensors"]
        )
        with patch.object(service, 'scan_loras', return_value=[lora]):
            result = service.has_model_restrictions("cg_elena")
        assert result is True


class TestIsModelCompatible:
    """Test is_model_compatible method"""

    @pytest.mark.unit
    def test_is_model_compatible_no_lora(self):
        """Should return True when character doesn't exist (fail later)"""
        service = CharacterLoraService()
        with patch.object(service, 'scan_loras', return_value=[]):
            result = service.is_model_compatible("nonexistent", "some/model.safetensors")
        assert result is True

    @pytest.mark.unit
    def test_is_model_compatible_no_restrictions(self):
        """Should return True when no restrictions defined"""
        service = CharacterLoraService()
        lora = CharacterLora(
            id="cg_elena",
            name="Elena",
            trigger_word="elena",
            lora_file="cg_elena.safetensors",
            lora_path="/path/to/cg_elena.safetensors",
            strength=1.0,
            compatible_models=None
        )
        with patch.object(service, 'scan_loras', return_value=[lora]):
            result = service.is_model_compatible("cg_elena", "any/model.safetensors")
        assert result is True

    @pytest.mark.unit
    def test_is_model_compatible_exact_match(self):
        """Should return True for exact path match"""
        service = CharacterLoraService()
        lora = CharacterLora(
            id="cg_elena",
            name="Elena",
            trigger_word="elena",
            lora_file="cg_elena.safetensors",
            lora_path="/path/to/cg_elena.safetensors",
            strength=1.0,
            compatible_models=["diffusion_models/flux1-dev.safetensors"]
        )
        with patch.object(service, 'scan_loras', return_value=[lora]):
            result = service.is_model_compatible("cg_elena", "diffusion_models/flux1-dev.safetensors")
        assert result is True

    @pytest.mark.unit
    def test_is_model_compatible_filename_match(self):
        """Should return True for filename-only match"""
        service = CharacterLoraService()
        lora = CharacterLora(
            id="cg_elena",
            name="Elena",
            trigger_word="elena",
            lora_file="cg_elena.safetensors",
            lora_path="/path/to/cg_elena.safetensors",
            strength=1.0,
            compatible_models=["diffusion_models/flux1-dev.safetensors"]
        )
        with patch.object(service, 'scan_loras', return_value=[lora]):
            # Different path but same filename
            result = service.is_model_compatible("cg_elena", "other/path/flux1-dev.safetensors")
        assert result is True

    @pytest.mark.unit
    def test_is_model_compatible_incompatible(self):
        """Should return False for incompatible model"""
        service = CharacterLoraService()
        lora = CharacterLora(
            id="cg_elena",
            name="Elena",
            trigger_word="elena",
            lora_file="cg_elena.safetensors",
            lora_path="/path/to/cg_elena.safetensors",
            strength=1.0,
            compatible_models=["diffusion_models/flux1-dev.safetensors"]
        )
        with patch.object(service, 'scan_loras', return_value=[lora]):
            result = service.is_model_compatible("cg_elena", "diffusion_models/sdxl.safetensors")
        assert result is False


class TestGetCompatibilityWarning:
    """Test get_compatibility_warning method"""

    @pytest.mark.unit
    def test_get_compatibility_warning_compatible(self):
        """Should return None for compatible model"""
        service = CharacterLoraService()
        lora = CharacterLora(
            id="cg_elena",
            name="Elena",
            trigger_word="elena",
            lora_file="cg_elena.safetensors",
            lora_path="/path/to/cg_elena.safetensors",
            strength=1.0,
            compatible_models=["diffusion_models/flux1-dev.safetensors"]
        )
        with patch.object(service, 'scan_loras', return_value=[lora]):
            result = service.get_compatibility_warning("cg_elena", "diffusion_models/flux1-dev.safetensors")
        assert result is None

    @pytest.mark.unit
    def test_get_compatibility_warning_incompatible(self):
        """Should return warning tuple for incompatible model"""
        service = CharacterLoraService()
        lora = CharacterLora(
            id="cg_elena",
            name="Elena",
            trigger_word="elena",
            lora_file="cg_elena.safetensors",
            lora_path="/path/to/cg_elena.safetensors",
            strength=1.0,
            compatible_models=["diffusion_models/flux1-dev.safetensors"]
        )
        with patch.object(service, 'scan_loras', return_value=[lora]):
            result = service.get_compatibility_warning("cg_elena", "diffusion_models/sdxl.safetensors")

        assert result is not None
        warning_msg, compatible_models = result
        assert "Elena" in warning_msg
        assert "sdxl.safetensors" in warning_msg
        assert "flux1-dev.safetensors" in warning_msg
        assert compatible_models == ["diffusion_models/flux1-dev.safetensors"]

    @pytest.mark.unit
    def test_get_compatibility_warning_no_restrictions(self):
        """Should return None when no restrictions defined"""
        service = CharacterLoraService()
        lora = CharacterLora(
            id="cg_elena",
            name="Elena",
            trigger_word="elena",
            lora_file="cg_elena.safetensors",
            lora_path="/path/to/cg_elena.safetensors",
            strength=1.0,
            compatible_models=None
        )
        with patch.object(service, 'scan_loras', return_value=[lora]):
            result = service.get_compatibility_warning("cg_elena", "any/model.safetensors")
        assert result is None

    @pytest.mark.unit
    def test_get_compatibility_warning_unknown_character(self):
        """Should return None for unknown character"""
        service = CharacterLoraService()
        with patch.object(service, 'scan_loras', return_value=[]):
            result = service.get_compatibility_warning("nonexistent", "any/model.safetensors")
        assert result is None


class TestGetCompatibleModelsForCharacter:
    """Test get_compatible_models_for_character method"""

    @pytest.mark.unit
    def test_get_compatible_models_no_lora(self):
        """Should return None when character doesn't exist"""
        service = CharacterLoraService()
        with patch.object(service, 'scan_loras', return_value=[]):
            result = service.get_compatible_models_for_character("nonexistent")
        assert result is None

    @pytest.mark.unit
    def test_get_compatible_models_with_restrictions(self):
        """Should return list of compatible models"""
        service = CharacterLoraService()
        compatible = ["diffusion_models/flux1-dev.safetensors", "diffusion_models/flux1-krea.safetensors"]
        lora = CharacterLora(
            id="cg_elena",
            name="Elena",
            trigger_word="elena",
            lora_file="cg_elena.safetensors",
            lora_path="/path/to/cg_elena.safetensors",
            strength=1.0,
            compatible_models=compatible
        )
        with patch.object(service, 'scan_loras', return_value=[lora]):
            result = service.get_compatible_models_for_character("cg_elena")
        assert result == compatible

    @pytest.mark.unit
    def test_get_compatible_models_no_restrictions(self):
        """Should return None when no restrictions"""
        service = CharacterLoraService()
        lora = CharacterLora(
            id="cg_elena",
            name="Elena",
            trigger_word="elena",
            lora_file="cg_elena.safetensors",
            lora_path="/path/to/cg_elena.safetensors",
            strength=1.0,
            compatible_models=None
        )
        with patch.object(service, 'scan_loras', return_value=[lora]):
            result = service.get_compatible_models_for_character("cg_elena")
        assert result is None


class TestScanLorasWithModels:
    """Test that scan_loras correctly loads .models files"""

    @pytest.mark.unit
    def test_scan_loras_loads_models_file(self):
        """Should load compatible_models when .models file exists"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create LoRA file and .models file
            lora_file = os.path.join(tmpdir, "cg_test.safetensors")
            models_file = os.path.join(tmpdir, "cg_test.models")

            Path(lora_file).touch()
            with open(models_file, 'w') as f:
                f.write("diffusion_models/flux1-dev.safetensors\n")

            # Mock the service to use our temp directory
            service = CharacterLoraService()
            with patch.object(service, 'get_lora_directory', return_value=tmpdir):
                loras = service.scan_loras(force_refresh=True)

            assert len(loras) == 1
            assert loras[0].id == "cg_test"
            assert loras[0].compatible_models == ["diffusion_models/flux1-dev.safetensors"]

    @pytest.mark.unit
    def test_scan_loras_without_models_file(self):
        """Should set compatible_models to None when no .models file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create only LoRA file, no .models
            lora_file = os.path.join(tmpdir, "cg_test.safetensors")
            Path(lora_file).touch()

            service = CharacterLoraService()
            with patch.object(service, 'get_lora_directory', return_value=tmpdir):
                loras = service.scan_loras(force_refresh=True)

            assert len(loras) == 1
            assert loras[0].id == "cg_test"
            assert loras[0].compatible_models is None
