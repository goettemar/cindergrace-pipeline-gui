"""Unit tests for ModelValidator"""
import pytest
import os
from pathlib import Path

from infrastructure.model_validator import ModelValidator


class TestModelValidatorInit:
    """Test ModelValidator initialization"""

    @pytest.mark.unit
    def test_init_without_comfy_root(self):
        """Should initialize with enabled=False when no comfy_root"""
        # Act
        validator = ModelValidator()

        # Assert
        assert validator.comfy_root is None
        assert validator.enabled is False
        assert validator._index is None

    @pytest.mark.unit
    def test_init_with_valid_comfy_root(self, tmp_path):
        """Should initialize with enabled=True when comfy_root exists"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        comfy_root.mkdir()

        # Act
        validator = ModelValidator(comfy_root=str(comfy_root))

        # Assert
        assert validator.comfy_root == str(comfy_root)
        assert validator.enabled is True
        assert validator._index is None

    @pytest.mark.unit
    def test_init_with_nonexistent_comfy_root(self, tmp_path):
        """Should initialize with enabled=False when comfy_root doesn't exist"""
        # Arrange
        nonexistent = tmp_path / "nonexistent"

        # Act
        validator = ModelValidator(comfy_root=str(nonexistent))

        # Assert
        assert validator.comfy_root == str(nonexistent)
        assert validator.enabled is False
        assert validator._index is None


class TestModelValidatorBuildIndex:
    """Test ModelValidator._build_index()"""

    @pytest.mark.unit
    def test_build_index_when_disabled(self):
        """Should create empty index when disabled"""
        # Arrange
        validator = ModelValidator()

        # Act
        validator._build_index()

        # Assert
        assert validator._index == {}

    @pytest.mark.unit
    def test_build_index_no_models_dir(self, tmp_path, capsys):
        """Should create empty index when models directory doesn't exist"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        comfy_root.mkdir()
        # Don't create models directory

        validator = ModelValidator(comfy_root=str(comfy_root))

        # Act
        validator._build_index()

        # Assert
        assert validator._index == {}

        # Verify warning was printed
        captured = capsys.readouterr()
        assert "⚠️" in captured.out
        assert "Model directory not found" in captured.out

    @pytest.mark.unit
    def test_build_index_with_models(self, tmp_path):
        """Should index all model files"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        models_dir = comfy_root / "models"
        checkpoints_dir = models_dir / "checkpoints"
        vae_dir = models_dir / "vae"

        checkpoints_dir.mkdir(parents=True)
        vae_dir.mkdir(parents=True)

        # Create model files
        (checkpoints_dir / "model1.safetensors").touch()
        (checkpoints_dir / "model2.ckpt").touch()
        (vae_dir / "vae1.safetensors").touch()
        (models_dir / "other.txt").touch()  # Should also be indexed

        validator = ModelValidator(comfy_root=str(comfy_root))

        # Act
        validator._build_index()

        # Assert
        assert "model1.safetensors" in validator._index
        assert "model2.ckpt" in validator._index
        assert "vae1.safetensors" in validator._index
        assert "other.txt" in validator._index

    @pytest.mark.unit
    def test_build_index_case_insensitive(self, tmp_path):
        """Should index models with case-insensitive keys"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        models_dir = comfy_root / "models"
        models_dir.mkdir(parents=True)

        (models_dir / "Model.SAFETENSORS").touch()

        validator = ModelValidator(comfy_root=str(comfy_root))

        # Act
        validator._build_index()

        # Assert
        assert "model.safetensors" in validator._index  # Lowercase key
        assert len(validator._index["model.safetensors"]) == 1


class TestModelValidatorEnsureIndex:
    """Test ModelValidator._ensure_index()"""

    @pytest.mark.unit
    def test_ensure_index_builds_when_none(self, tmp_path):
        """Should build index when _index is None"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        models_dir = comfy_root / "models"
        models_dir.mkdir(parents=True)

        (models_dir / "test.safetensors").touch()

        validator = ModelValidator(comfy_root=str(comfy_root))
        assert validator._index is None

        # Act
        validator._ensure_index()

        # Assert
        assert validator._index is not None
        assert "test.safetensors" in validator._index

    @pytest.mark.unit
    def test_ensure_index_skips_when_built(self, tmp_path):
        """Should not rebuild index if already exists"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        models_dir = comfy_root / "models"
        models_dir.mkdir(parents=True)

        validator = ModelValidator(comfy_root=str(comfy_root))
        validator._index = {"existing": ["path"]}

        # Act
        validator._ensure_index()

        # Assert
        assert validator._index == {"existing": ["path"]}  # Unchanged


class TestModelValidatorExtractModelRefs:
    """Test ModelValidator._extract_model_refs()"""

    @pytest.mark.unit
    def test_extract_model_refs_from_workflow(self):
        """Should extract model filenames from workflow"""
        # Arrange
        validator = ModelValidator()
        workflow = {
            "1": {
                "inputs": {
                    "ckpt_name": "model.safetensors",
                    "other": "value"
                }
            },
            "2": {
                "inputs": {
                    "vae": "vae.ckpt"
                }
            }
        }

        # Act
        refs = validator._extract_model_refs(workflow)

        # Assert
        assert "model.safetensors" in refs
        assert "vae.ckpt" in refs
        assert len(refs) == 2

    @pytest.mark.unit
    def test_extract_model_refs_nested_values(self):
        """Should extract models from nested structures"""
        # Arrange
        validator = ModelValidator()
        workflow = {
            "1": {
                "inputs": {
                    "models": ["model1.safetensors", "model2.pt"],
                    "config": {
                        "vae": "vae.bin"
                    }
                }
            }
        }

        # Act
        refs = validator._extract_model_refs(workflow)

        # Assert
        assert "model1.safetensors" in refs
        assert "model2.pt" in refs
        assert "vae.bin" in refs

    @pytest.mark.unit
    def test_extract_model_refs_with_paths(self):
        """Should extract only basename from full paths"""
        # Arrange
        validator = ModelValidator()
        workflow = {
            "1": {
                "inputs": {
                    "model": "/path/to/model.safetensors"
                }
            }
        }

        # Act
        refs = validator._extract_model_refs(workflow)

        # Assert
        assert "model.safetensors" in refs
        assert "/path/to/model.safetensors" not in refs

    @pytest.mark.unit
    def test_extract_model_refs_filters_extensions(self):
        """Should only extract files with model extensions"""
        # Arrange
        validator = ModelValidator()
        workflow = {
            "1": {
                "inputs": {
                    "model": "model.safetensors",
                    "config": "config.json",
                    "image": "image.png"
                }
            }
        }

        # Act
        refs = validator._extract_model_refs(workflow)

        # Assert
        assert "model.safetensors" in refs
        assert "config.json" not in refs
        assert "image.png" not in refs

    @pytest.mark.unit
    def test_extract_model_refs_empty_workflow(self):
        """Should return empty set for empty workflow"""
        # Arrange
        validator = ModelValidator()
        workflow = {}

        # Act
        refs = validator._extract_model_refs(workflow)

        # Assert
        assert refs == set()


class TestModelValidatorHasModel:
    """Test ModelValidator._has_model()"""

    @pytest.mark.unit
    def test_has_model_when_exists(self):
        """Should return True when model exists in index"""
        # Arrange
        validator = ModelValidator()
        validator._index = {
            "model.safetensors": ["/path/to/model.safetensors"]
        }

        # Act
        result = validator._has_model("model.safetensors")

        # Assert
        assert result is True

    @pytest.mark.unit
    def test_has_model_when_missing(self):
        """Should return False when model not in index"""
        # Arrange
        validator = ModelValidator()
        validator._index = {
            "model.safetensors": ["/path/to/model.safetensors"]
        }

        # Act
        result = validator._has_model("other.ckpt")

        # Assert
        assert result is False

    @pytest.mark.unit
    def test_has_model_case_insensitive(self):
        """Should check case-insensitively"""
        # Arrange
        validator = ModelValidator()
        validator._index = {
            "model.safetensors": ["/path/to/Model.SAFETENSORS"]
        }

        # Act
        result = validator._has_model("MODEL.SAFETENSORS")

        # Assert
        assert result is True

    @pytest.mark.unit
    def test_has_model_when_index_empty(self):
        """Should return False when index is empty"""
        # Arrange
        validator = ModelValidator()
        validator._index = {}

        # Act
        result = validator._has_model("model.safetensors")

        # Assert
        assert result is False

    @pytest.mark.unit
    def test_has_model_when_index_none(self):
        """Should return False when index is None"""
        # Arrange
        validator = ModelValidator()
        validator._index = None

        # Act
        result = validator._has_model("model.safetensors")

        # Assert
        assert result is False


class TestModelValidatorFindMissing:
    """Test ModelValidator.find_missing()"""

    @pytest.mark.unit
    def test_find_missing_when_disabled(self):
        """Should return empty list when validator is disabled"""
        # Arrange
        validator = ModelValidator()
        workflow = {
            "1": {"inputs": {"model": "model.safetensors"}}
        }

        # Act
        result = validator.find_missing(workflow)

        # Assert
        assert result == []

    @pytest.mark.unit
    def test_find_missing_no_models_in_workflow(self, tmp_path):
        """Should return empty list when no models in workflow"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        models_dir = comfy_root / "models"
        models_dir.mkdir(parents=True)

        validator = ModelValidator(comfy_root=str(comfy_root))
        workflow = {
            "1": {"inputs": {"text": "hello"}}
        }

        # Act
        result = validator.find_missing(workflow)

        # Assert
        assert result == []

    @pytest.mark.unit
    def test_find_missing_all_present(self, tmp_path):
        """Should return empty list when all models exist"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        models_dir = comfy_root / "models"
        models_dir.mkdir(parents=True)

        (models_dir / "model.safetensors").touch()
        (models_dir / "vae.ckpt").touch()

        validator = ModelValidator(comfy_root=str(comfy_root))
        workflow = {
            "1": {"inputs": {"model": "model.safetensors"}},
            "2": {"inputs": {"vae": "vae.ckpt"}}
        }

        # Act
        result = validator.find_missing(workflow)

        # Assert
        assert result == []

    @pytest.mark.unit
    def test_find_missing_some_missing(self, tmp_path):
        """Should return list of missing models"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        models_dir = comfy_root / "models"
        models_dir.mkdir(parents=True)

        (models_dir / "model1.safetensors").touch()
        # model2.ckpt is missing

        validator = ModelValidator(comfy_root=str(comfy_root))
        workflow = {
            "1": {"inputs": {"model": "model1.safetensors"}},
            "2": {"inputs": {"vae": "model2.ckpt"}}
        }

        # Act
        result = validator.find_missing(workflow)

        # Assert
        assert result == ["model2.ckpt"]

    @pytest.mark.unit
    def test_find_missing_sorted_output(self, tmp_path):
        """Should return sorted list of missing models"""
        # Arrange
        comfy_root = tmp_path / "comfyui"
        models_dir = comfy_root / "models"
        models_dir.mkdir(parents=True)

        validator = ModelValidator(comfy_root=str(comfy_root))
        workflow = {
            "1": {"inputs": {"model": "zzz.safetensors"}},
            "2": {"inputs": {"vae": "aaa.ckpt"}},
            "3": {"inputs": {"lora": "mmm.pt"}}
        }

        # Act
        result = validator.find_missing(workflow)

        # Assert
        assert result == ["aaa.ckpt", "mmm.pt", "zzz.safetensors"]  # Sorted


class TestModelValidatorIntegration:
    """Integration tests for ModelValidator workflow"""

    @pytest.mark.unit
    def test_full_workflow(self, tmp_path):
        """Should validate models in realistic workflow"""
        # Arrange - Create ComfyUI structure
        comfy_root = tmp_path / "comfyui"
        checkpoints = comfy_root / "models" / "checkpoints"
        vae = comfy_root / "models" / "vae"
        loras = comfy_root / "models" / "loras"

        checkpoints.mkdir(parents=True)
        vae.mkdir(parents=True)
        loras.mkdir(parents=True)

        # Create some models
        (checkpoints / "flux-dev.safetensors").touch()
        (vae / "sdxl-vae.safetensors").touch()
        # lora1.safetensors is missing

        # Create workflow
        workflow = {
            "checkpoint_loader": {
                "inputs": {
                    "ckpt_name": "flux-dev.safetensors"
                }
            },
            "vae_loader": {
                "inputs": {
                    "vae_name": "sdxl-vae.safetensors"
                }
            },
            "lora_loader": {
                "inputs": {
                    "lora_name": "lora1.safetensors"
                }
            }
        }

        validator = ModelValidator(comfy_root=str(comfy_root))

        # Act
        missing = validator.find_missing(workflow)

        # Assert
        assert missing == ["lora1.safetensors"]
        assert "flux-dev.safetensors" not in missing
        assert "sdxl-vae.safetensors" not in missing
