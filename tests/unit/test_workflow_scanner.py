"""Tests for WorkflowScanner - ComfyUI workflow model reference extraction."""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.model_manager.workflow_scanner import WorkflowScanner


@pytest.fixture
def tmp_workflows_dir(tmp_path):
    """Create temporary workflows directory."""
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    return workflows


@pytest.fixture
def scanner(tmp_workflows_dir):
    """Create WorkflowScanner with temp directory."""
    return WorkflowScanner(str(tmp_workflows_dir))


class TestWorkflowScannerInit:
    """Tests for WorkflowScanner initialization."""

    def test_init_sets_workflows_dir(self, tmp_workflows_dir):
        """Scanner stores workflows directory path."""
        scanner = WorkflowScanner(str(tmp_workflows_dir))
        assert scanner.workflows_dir == tmp_workflows_dir

    def test_init_accepts_string_path(self, tmp_path):
        """Scanner accepts string path and converts to Path."""
        dir_path = str(tmp_path / "workflows")
        scanner = WorkflowScanner(dir_path)
        assert isinstance(scanner.workflows_dir, Path)

    def test_init_cache_is_none(self, tmp_workflows_dir):
        """Scanner starts with empty cache."""
        scanner = WorkflowScanner(str(tmp_workflows_dir))
        assert scanner._scan_cache is None


class TestModelNodeTypes:
    """Tests for MODEL_NODE_TYPES mapping."""

    def test_checkpoint_loaders_mapped(self):
        """Checkpoint loader nodes are mapped correctly."""
        types = WorkflowScanner.MODEL_NODE_TYPES
        assert types["CheckpointLoaderSimple"] == "checkpoints"
        assert types["CheckpointLoader"] == "checkpoints"
        assert types["CheckpointLoaderNF4"] == "checkpoints"

    def test_lora_loaders_mapped(self):
        """LoRA loader nodes are mapped correctly."""
        types = WorkflowScanner.MODEL_NODE_TYPES
        assert types["LoraLoader"] == "loras"
        assert types["LoraLoaderModelOnly"] == "loras"

    def test_vae_loader_mapped(self):
        """VAE loader is mapped correctly."""
        assert WorkflowScanner.MODEL_NODE_TYPES["VAELoader"] == "vae"

    def test_controlnet_loader_mapped(self):
        """ControlNet loader is mapped correctly."""
        assert WorkflowScanner.MODEL_NODE_TYPES["ControlNetLoader"] == "controlnet"

    def test_upscale_model_loader_mapped(self):
        """Upscale model loader is mapped correctly."""
        assert WorkflowScanner.MODEL_NODE_TYPES["UpscaleModelLoader"] == "upscale_models"

    def test_clip_loaders_mapped(self):
        """CLIP loaders are mapped correctly."""
        types = WorkflowScanner.MODEL_NODE_TYPES
        assert types["CLIPLoader"] == "clip"
        assert types["DualCLIPLoader"] == "clip"

    def test_unet_loaders_mapped(self):
        """UNET loaders are mapped to diffusion_models."""
        types = WorkflowScanner.MODEL_NODE_TYPES
        assert types["UNETLoader"] == "diffusion_models"
        assert types["UnetLoaderGGUF"] == "diffusion_models"

    def test_style_model_loader_mapped(self):
        """Style model loader is mapped correctly."""
        assert WorkflowScanner.MODEL_NODE_TYPES["StyleModelLoader"] == "style_models"


class TestScanWorkflow:
    """Tests for scan_workflow method."""

    def test_scan_api_format_checkpoint(self, scanner, tmp_workflows_dir):
        """Scan API format workflow with checkpoint loader."""
        workflow = {
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "v1-5-pruned.safetensors"
                }
            }
        }
        workflow_file = tmp_workflows_dir / "test.json"
        workflow_file.write_text(json.dumps(workflow))

        models = scanner.scan_workflow(str(workflow_file))

        assert len(models) == 1
        assert models[0]["type"] == "checkpoints"
        assert models[0]["filename"] == "v1-5-pruned.safetensors"
        assert models[0]["node_id"] == "4"
        assert models[0]["node_type"] == "CheckpointLoaderSimple"

    def test_scan_api_format_lora(self, scanner, tmp_workflows_dir):
        """Scan API format workflow with LoRA loader."""
        workflow = {
            "10": {
                "class_type": "LoraLoader",
                "inputs": {
                    "lora_name": "my_lora.safetensors",
                    "strength_model": 1.0,
                    "strength_clip": 1.0
                }
            }
        }
        workflow_file = tmp_workflows_dir / "test.json"
        workflow_file.write_text(json.dumps(workflow))

        models = scanner.scan_workflow(str(workflow_file))

        assert len(models) == 1
        assert models[0]["type"] == "loras"
        assert models[0]["filename"] == "my_lora.safetensors"

    def test_scan_api_format_vae(self, scanner, tmp_workflows_dir):
        """Scan API format workflow with VAE loader."""
        workflow = {
            "5": {
                "class_type": "VAELoader",
                "inputs": {
                    "vae_name": "vae-ft-mse-840000.safetensors"
                }
            }
        }
        workflow_file = tmp_workflows_dir / "test.json"
        workflow_file.write_text(json.dumps(workflow))

        models = scanner.scan_workflow(str(workflow_file))

        assert len(models) == 1
        assert models[0]["type"] == "vae"
        assert models[0]["filename"] == "vae-ft-mse-840000.safetensors"

    def test_scan_api_format_controlnet(self, scanner, tmp_workflows_dir):
        """Scan API format workflow with ControlNet loader."""
        workflow = {
            "8": {
                "class_type": "ControlNetLoader",
                "inputs": {
                    "control_net_name": "control_canny.safetensors"
                }
            }
        }
        workflow_file = tmp_workflows_dir / "test.json"
        workflow_file.write_text(json.dumps(workflow))

        models = scanner.scan_workflow(str(workflow_file))

        assert len(models) == 1
        assert models[0]["type"] == "controlnet"
        assert models[0]["filename"] == "control_canny.safetensors"

    def test_scan_api_format_upscale(self, scanner, tmp_workflows_dir):
        """Scan API format workflow with upscale model loader."""
        workflow = {
            "12": {
                "class_type": "UpscaleModelLoader",
                "inputs": {
                    "model_name": "4x_NMKD-Siax_200k.pth"
                }
            }
        }
        workflow_file = tmp_workflows_dir / "test.json"
        workflow_file.write_text(json.dumps(workflow))

        models = scanner.scan_workflow(str(workflow_file))

        assert len(models) == 1
        assert models[0]["type"] == "upscale_models"
        assert models[0]["filename"] == "4x_NMKD-Siax_200k.pth"

    def test_scan_api_format_clip(self, scanner, tmp_workflows_dir):
        """Scan API format workflow with CLIP loader."""
        workflow = {
            "3": {
                "class_type": "CLIPLoader",
                "inputs": {
                    "clip_name": "clip_l.safetensors"
                }
            }
        }
        workflow_file = tmp_workflows_dir / "test.json"
        workflow_file.write_text(json.dumps(workflow))

        models = scanner.scan_workflow(str(workflow_file))

        assert len(models) == 1
        assert models[0]["type"] == "clip"
        assert models[0]["filename"] == "clip_l.safetensors"

    def test_scan_api_format_dual_clip(self, scanner, tmp_workflows_dir):
        """Scan API format workflow with DualCLIPLoader."""
        workflow = {
            "3": {
                "class_type": "DualCLIPLoader",
                "inputs": {
                    "clip_name1": "clip_l.safetensors",
                    "clip_name2": "clip_g.safetensors"
                }
            }
        }
        workflow_file = tmp_workflows_dir / "test.json"
        workflow_file.write_text(json.dumps(workflow))

        models = scanner.scan_workflow(str(workflow_file))

        # DualCLIPLoader extracts first clip field found
        assert len(models) == 1
        assert models[0]["type"] == "clip"

    def test_scan_api_format_unet(self, scanner, tmp_workflows_dir):
        """Scan API format workflow with UNET loader."""
        workflow = {
            "2": {
                "class_type": "UNETLoader",
                "inputs": {
                    "unet_name": "flux1-dev.safetensors"
                }
            }
        }
        workflow_file = tmp_workflows_dir / "test.json"
        workflow_file.write_text(json.dumps(workflow))

        models = scanner.scan_workflow(str(workflow_file))

        assert len(models) == 1
        assert models[0]["type"] == "diffusion_models"
        assert models[0]["filename"] == "flux1-dev.safetensors"

    def test_scan_api_format_style_model(self, scanner, tmp_workflows_dir):
        """Scan API format workflow with style model loader."""
        workflow = {
            "15": {
                "class_type": "StyleModelLoader",
                "inputs": {
                    "style_model_name": "style_model.safetensors"
                }
            }
        }
        workflow_file = tmp_workflows_dir / "test.json"
        workflow_file.write_text(json.dumps(workflow))

        models = scanner.scan_workflow(str(workflow_file))

        assert len(models) == 1
        assert models[0]["type"] == "style_models"
        assert models[0]["filename"] == "style_model.safetensors"

    def test_scan_ui_format_with_widgets_values(self, scanner, tmp_workflows_dir):
        """Scan UI format workflow with widgets_values."""
        workflow = {
            "nodes": [
                {
                    "id": 4,
                    "type": "CheckpointLoaderSimple",
                    "inputs": [],
                    "widgets_values": ["sd_xl_base_1.0.safetensors"]
                }
            ]
        }
        workflow_file = tmp_workflows_dir / "test.json"
        workflow_file.write_text(json.dumps(workflow))

        models = scanner.scan_workflow(str(workflow_file))

        assert len(models) == 1
        assert models[0]["type"] == "checkpoints"
        assert models[0]["filename"] == "sd_xl_base_1.0.safetensors"
        assert models[0]["node_id"] == "4"

    def test_scan_ui_format_lora(self, scanner, tmp_workflows_dir):
        """Scan UI format workflow with LoRA."""
        workflow = {
            "nodes": [
                {
                    "id": 10,
                    "type": "LoraLoader",
                    "inputs": [],
                    "widgets_values": ["lora_character.safetensors", 1.0, 1.0]
                }
            ]
        }
        workflow_file = tmp_workflows_dir / "test.json"
        workflow_file.write_text(json.dumps(workflow))

        models = scanner.scan_workflow(str(workflow_file))

        assert len(models) == 1
        assert models[0]["type"] == "loras"
        assert models[0]["filename"] == "lora_character.safetensors"

    def test_scan_multiple_models(self, scanner, tmp_workflows_dir):
        """Scan workflow with multiple model loaders."""
        workflow = {
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model.safetensors"}
            },
            "10": {
                "class_type": "LoraLoader",
                "inputs": {"lora_name": "lora1.safetensors"}
            },
            "11": {
                "class_type": "LoraLoader",
                "inputs": {"lora_name": "lora2.safetensors"}
            },
            "5": {
                "class_type": "VAELoader",
                "inputs": {"vae_name": "vae.safetensors"}
            }
        }
        workflow_file = tmp_workflows_dir / "test.json"
        workflow_file.write_text(json.dumps(workflow))

        models = scanner.scan_workflow(str(workflow_file))

        assert len(models) == 4
        types = {m["type"] for m in models}
        assert "checkpoints" in types
        assert "loras" in types
        assert "vae" in types

    def test_scan_ignores_non_model_nodes(self, scanner, tmp_workflows_dir):
        """Scanner ignores nodes that don't load models."""
        workflow = {
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model.safetensors"}
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "a photo"}
            },
            "7": {
                "class_type": "KSampler",
                "inputs": {"steps": 20}
            }
        }
        workflow_file = tmp_workflows_dir / "test.json"
        workflow_file.write_text(json.dumps(workflow))

        models = scanner.scan_workflow(str(workflow_file))

        assert len(models) == 1
        assert models[0]["type"] == "checkpoints"

    def test_scan_empty_workflow(self, scanner, tmp_workflows_dir):
        """Scan empty workflow returns empty list."""
        workflow = {}
        workflow_file = tmp_workflows_dir / "test.json"
        workflow_file.write_text(json.dumps(workflow))

        models = scanner.scan_workflow(str(workflow_file))

        assert models == []

    def test_scan_invalid_json(self, scanner, tmp_workflows_dir):
        """Scan invalid JSON returns empty list."""
        workflow_file = tmp_workflows_dir / "invalid.json"
        workflow_file.write_text("not valid json {")

        models = scanner.scan_workflow(str(workflow_file))

        assert models == []

    def test_scan_workflow_not_dict(self, scanner, tmp_workflows_dir):
        """Scan non-dict workflow returns empty list."""
        workflow_file = tmp_workflows_dir / "array.json"
        workflow_file.write_text(json.dumps([1, 2, 3]))

        models = scanner.scan_workflow(str(workflow_file))

        assert models == []

    def test_scan_node_without_inputs(self, scanner, tmp_workflows_dir):
        """Handle node without inputs field."""
        workflow = {
            "4": {
                "class_type": "CheckpointLoaderSimple"
                # No inputs field
            }
        }
        workflow_file = tmp_workflows_dir / "test.json"
        workflow_file.write_text(json.dumps(workflow))

        models = scanner.scan_workflow(str(workflow_file))

        assert models == []

    def test_scan_node_with_empty_model_name(self, scanner, tmp_workflows_dir):
        """Handle node with empty model name."""
        workflow = {
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": ""}
            }
        }
        workflow_file = tmp_workflows_dir / "test.json"
        workflow_file.write_text(json.dumps(workflow))

        models = scanner.scan_workflow(str(workflow_file))

        assert models == []


class TestScanAllWorkflows:
    """Tests for scan_all_workflows method."""

    def test_scan_empty_directory(self, scanner):
        """Scan empty directory returns empty dict."""
        result = scanner.scan_all_workflows()
        assert result == {}

    def test_scan_nonexistent_directory(self, tmp_path):
        """Scan non-existent directory returns empty dict."""
        scanner = WorkflowScanner(str(tmp_path / "nonexistent"))
        result = scanner.scan_all_workflows()
        assert result == {}

    def test_scan_multiple_workflows(self, scanner, tmp_workflows_dir):
        """Scan multiple workflow files."""
        # Workflow 1
        wf1 = {
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model1.safetensors"}
            }
        }
        (tmp_workflows_dir / "workflow1.json").write_text(json.dumps(wf1))

        # Workflow 2
        wf2 = {
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model2.safetensors"}
            },
            "10": {
                "class_type": "LoraLoader",
                "inputs": {"lora_name": "lora.safetensors"}
            }
        }
        (tmp_workflows_dir / "workflow2.json").write_text(json.dumps(wf2))

        result = scanner.scan_all_workflows()

        assert len(result) == 2
        assert "workflow1.json" in result
        assert "workflow2.json" in result
        assert len(result["workflow1.json"]) == 1
        assert len(result["workflow2.json"]) == 2

    def test_scan_subdirectories(self, scanner, tmp_workflows_dir):
        """Scan workflows in subdirectories."""
        subdir = tmp_workflows_dir / "subfolder"
        subdir.mkdir()

        workflow = {
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model.safetensors"}
            }
        }
        (subdir / "nested.json").write_text(json.dumps(workflow))

        result = scanner.scan_all_workflows()

        assert len(result) >= 1
        assert any("nested.json" in name for name in result.keys())

    def test_scan_caches_results(self, scanner, tmp_workflows_dir):
        """Second call returns cached results."""
        workflow = {
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model.safetensors"}
            }
        }
        (tmp_workflows_dir / "test.json").write_text(json.dumps(workflow))

        # First call
        result1 = scanner.scan_all_workflows()
        assert len(result1) == 1

        # Add another workflow
        (tmp_workflows_dir / "test2.json").write_text(json.dumps(workflow))

        # Second call should return cached result
        result2 = scanner.scan_all_workflows(use_cache=True)
        assert len(result2) == 1  # Still 1, cached

    def test_scan_bypass_cache(self, scanner, tmp_workflows_dir):
        """Can bypass cache with use_cache=False."""
        workflow = {
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model.safetensors"}
            }
        }
        (tmp_workflows_dir / "test.json").write_text(json.dumps(workflow))

        # First call
        result1 = scanner.scan_all_workflows()
        assert len(result1) == 1

        # Add another workflow
        (tmp_workflows_dir / "test2.json").write_text(json.dumps(workflow))

        # Second call with cache disabled
        result2 = scanner.scan_all_workflows(use_cache=False)
        assert len(result2) == 2  # Now 2, refreshed

    def test_scan_skips_workflows_without_models(self, scanner, tmp_workflows_dir):
        """Workflows without model references are not included."""
        wf_with_models = {
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model.safetensors"}
            }
        }
        (tmp_workflows_dir / "with_models.json").write_text(json.dumps(wf_with_models))

        wf_without_models = {
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "a photo"}
            }
        }
        (tmp_workflows_dir / "without_models.json").write_text(json.dumps(wf_without_models))

        result = scanner.scan_all_workflows()

        assert len(result) == 1
        assert "with_models.json" in result
        assert "without_models.json" not in result


class TestExtractInputsFromWidgets:
    """Tests for _extract_inputs_from_widgets method."""

    def test_extract_checkpoint_from_widgets(self, scanner):
        """Extract checkpoint name from widgets_values."""
        node_data = {
            "type": "CheckpointLoaderSimple",
            "widgets_values": ["sd_xl_base.safetensors"]
        }
        inputs = scanner._extract_inputs_from_widgets(node_data, "CheckpointLoaderSimple")
        assert inputs["ckpt_name"] == "sd_xl_base.safetensors"

    def test_extract_lora_from_widgets(self, scanner):
        """Extract LoRA name from widgets_values."""
        node_data = {
            "type": "LoraLoader",
            "widgets_values": ["my_lora.safetensors", 1.0, 1.0]
        }
        inputs = scanner._extract_inputs_from_widgets(node_data, "LoraLoader")
        assert inputs["lora_name"] == "my_lora.safetensors"

    def test_extract_vae_from_widgets(self, scanner):
        """Extract VAE name from widgets_values."""
        node_data = {
            "type": "VAELoader",
            "widgets_values": ["vae.safetensors"]
        }
        inputs = scanner._extract_inputs_from_widgets(node_data, "VAELoader")
        assert inputs["vae_name"] == "vae.safetensors"

    def test_extract_controlnet_from_widgets(self, scanner):
        """Extract ControlNet name from widgets_values."""
        node_data = {
            "type": "ControlNetLoader",
            "widgets_values": ["control_canny.safetensors"]
        }
        inputs = scanner._extract_inputs_from_widgets(node_data, "ControlNetLoader")
        assert inputs["control_net_name"] == "control_canny.safetensors"

    def test_extract_clip_from_widgets(self, scanner):
        """Extract CLIP name from widgets_values."""
        node_data = {
            "type": "CLIPLoader",
            "widgets_values": ["clip_l.safetensors"]
        }
        inputs = scanner._extract_inputs_from_widgets(node_data, "CLIPLoader")
        assert inputs["clip_name"] == "clip_l.safetensors"

    def test_extract_unet_from_widgets(self, scanner):
        """Extract UNET name from widgets_values."""
        node_data = {
            "type": "UNETLoader",
            "widgets_values": ["flux.safetensors"]
        }
        inputs = scanner._extract_inputs_from_widgets(node_data, "UNETLoader")
        assert inputs["unet_name"] == "flux.safetensors"

    def test_extract_style_model_from_widgets(self, scanner):
        """Extract style model name from widgets_values."""
        node_data = {
            "type": "StyleModelLoader",
            "widgets_values": ["style.safetensors"]
        }
        inputs = scanner._extract_inputs_from_widgets(node_data, "StyleModelLoader")
        assert inputs["style_model_name"] == "style.safetensors"

    def test_extract_upscale_from_widgets(self, scanner):
        """Extract upscale model name from widgets_values."""
        node_data = {
            "type": "UpscaleModelLoader",
            "widgets_values": ["4x_esrgan.pth"]
        }
        inputs = scanner._extract_inputs_from_widgets(node_data, "UpscaleModelLoader")
        assert inputs["model_name"] == "4x_esrgan.pth"

    def test_extract_empty_widgets_values(self, scanner):
        """Handle empty widgets_values."""
        node_data = {
            "type": "CheckpointLoaderSimple",
            "widgets_values": []
        }
        inputs = scanner._extract_inputs_from_widgets(node_data, "CheckpointLoaderSimple")
        assert inputs == {}

    def test_extract_no_widgets_values(self, scanner):
        """Handle missing widgets_values."""
        node_data = {
            "type": "CheckpointLoaderSimple"
        }
        inputs = scanner._extract_inputs_from_widgets(node_data, "CheckpointLoaderSimple")
        assert inputs == {}

    def test_extract_non_string_first_widget(self, scanner):
        """Handle non-string first widget value."""
        node_data = {
            "type": "CheckpointLoaderSimple",
            "widgets_values": [123, "something"]
        }
        inputs = scanner._extract_inputs_from_widgets(node_data, "CheckpointLoaderSimple")
        assert inputs == {}


class TestExtractModelFilename:
    """Tests for _extract_model_filename method."""

    def test_extract_ckpt_name(self, scanner):
        """Extract from ckpt_name field."""
        inputs = {"ckpt_name": "model.safetensors"}
        result = scanner._extract_model_filename(inputs, "CheckpointLoaderSimple")
        assert result == "model.safetensors"

    def test_extract_lora_name(self, scanner):
        """Extract from lora_name field."""
        inputs = {"lora_name": "lora.safetensors"}
        result = scanner._extract_model_filename(inputs, "LoraLoader")
        assert result == "lora.safetensors"

    def test_extract_vae_name(self, scanner):
        """Extract from vae_name field."""
        inputs = {"vae_name": "vae.safetensors"}
        result = scanner._extract_model_filename(inputs, "VAELoader")
        assert result == "vae.safetensors"

    def test_extract_control_net_name(self, scanner):
        """Extract from control_net_name field."""
        inputs = {"control_net_name": "canny.safetensors"}
        result = scanner._extract_model_filename(inputs, "ControlNetLoader")
        assert result == "canny.safetensors"

    def test_extract_model_name(self, scanner):
        """Extract from model_name field."""
        inputs = {"model_name": "upscale.pth"}
        result = scanner._extract_model_filename(inputs, "UpscaleModelLoader")
        assert result == "upscale.pth"

    def test_extract_clip_name(self, scanner):
        """Extract from clip_name field."""
        inputs = {"clip_name": "clip.safetensors"}
        result = scanner._extract_model_filename(inputs, "CLIPLoader")
        assert result == "clip.safetensors"

    def test_extract_unet_name(self, scanner):
        """Extract from unet_name field."""
        inputs = {"unet_name": "flux.safetensors"}
        result = scanner._extract_model_filename(inputs, "UNETLoader")
        assert result == "flux.safetensors"

    def test_extract_style_model_name(self, scanner):
        """Extract from style_model_name field."""
        inputs = {"style_model_name": "style.safetensors"}
        result = scanner._extract_model_filename(inputs, "StyleModelLoader")
        assert result == "style.safetensors"

    def test_extract_checkpoint_field(self, scanner):
        """Extract from checkpoint field (alternative name)."""
        inputs = {"checkpoint": "model.safetensors"}
        result = scanner._extract_model_filename(inputs, "CheckpointLoader")
        assert result == "model.safetensors"

    def test_extract_empty_inputs(self, scanner):
        """Handle empty inputs."""
        inputs = {}
        result = scanner._extract_model_filename(inputs, "CheckpointLoaderSimple")
        assert result == ""

    def test_extract_no_matching_field(self, scanner):
        """Handle inputs without matching field."""
        inputs = {"unknown_field": "value"}
        result = scanner._extract_model_filename(inputs, "CheckpointLoaderSimple")
        assert result == ""

    def test_extract_empty_string_value(self, scanner):
        """Handle empty string value."""
        inputs = {"ckpt_name": ""}
        result = scanner._extract_model_filename(inputs, "CheckpointLoaderSimple")
        assert result == ""

    def test_extract_non_string_value(self, scanner):
        """Handle non-string value."""
        inputs = {"ckpt_name": 123}
        result = scanner._extract_model_filename(inputs, "CheckpointLoaderSimple")
        assert result == ""


class TestGetAllReferencedModels:
    """Tests for get_all_referenced_models method."""

    def test_get_all_empty_directory(self, scanner):
        """Get models from empty directory returns empty dict."""
        result = scanner.get_all_referenced_models()
        assert result == {}

    def test_get_all_aggregates_by_type(self, scanner, tmp_workflows_dir):
        """Models are aggregated by type."""
        wf1 = {
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model1.safetensors"}
            },
            "10": {
                "class_type": "LoraLoader",
                "inputs": {"lora_name": "lora1.safetensors"}
            }
        }
        (tmp_workflows_dir / "wf1.json").write_text(json.dumps(wf1))

        wf2 = {
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model2.safetensors"}
            },
            "10": {
                "class_type": "LoraLoader",
                "inputs": {"lora_name": "lora2.safetensors"}
            }
        }
        (tmp_workflows_dir / "wf2.json").write_text(json.dumps(wf2))

        result = scanner.get_all_referenced_models()

        assert "checkpoints" in result
        assert "loras" in result
        assert len(result["checkpoints"]) == 2
        assert len(result["loras"]) == 2
        assert "model1.safetensors" in result["checkpoints"]
        assert "model2.safetensors" in result["checkpoints"]

    def test_get_all_deduplicates(self, scanner, tmp_workflows_dir):
        """Same model in multiple workflows is only listed once."""
        wf1 = {
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "shared_model.safetensors"}
            }
        }
        (tmp_workflows_dir / "wf1.json").write_text(json.dumps(wf1))
        (tmp_workflows_dir / "wf2.json").write_text(json.dumps(wf1))
        (tmp_workflows_dir / "wf3.json").write_text(json.dumps(wf1))

        result = scanner.get_all_referenced_models()

        assert "checkpoints" in result
        assert len(result["checkpoints"]) == 1
        assert "shared_model.safetensors" in result["checkpoints"]


class TestGetWorkflowsUsingModel:
    """Tests for get_workflows_using_model method."""

    def test_find_workflows_using_model(self, scanner, tmp_workflows_dir):
        """Find all workflows that use a specific model."""
        wf1 = {
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "target_model.safetensors"}
            }
        }
        (tmp_workflows_dir / "uses_target.json").write_text(json.dumps(wf1))

        wf2 = {
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "other_model.safetensors"}
            }
        }
        (tmp_workflows_dir / "uses_other.json").write_text(json.dumps(wf2))

        wf3 = {
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "target_model.safetensors"}
            },
            "10": {
                "class_type": "LoraLoader",
                "inputs": {"lora_name": "lora.safetensors"}
            }
        }
        (tmp_workflows_dir / "also_uses_target.json").write_text(json.dumps(wf3))

        result = scanner.get_workflows_using_model("target_model.safetensors")

        assert len(result) == 2
        assert "uses_target.json" in result
        assert "also_uses_target.json" in result
        assert "uses_other.json" not in result

    def test_find_no_workflows_for_unknown_model(self, scanner, tmp_workflows_dir):
        """No workflows found for model not in use."""
        wf1 = {
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "some_model.safetensors"}
            }
        }
        (tmp_workflows_dir / "test.json").write_text(json.dumps(wf1))

        result = scanner.get_workflows_using_model("unknown_model.safetensors")

        assert result == []

    def test_workflow_only_listed_once(self, scanner, tmp_workflows_dir):
        """Workflow using same model multiple times is only listed once."""
        wf = {
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model.safetensors"}
            },
            "10": {
                "class_type": "LoraLoader",
                "inputs": {"lora_name": "model.safetensors"}
            }
        }
        # Note: unrealistic scenario but tests the break logic
        (tmp_workflows_dir / "test.json").write_text(json.dumps(wf))

        # Since same filename in different node types, but the break happens after first match
        result = scanner.get_workflows_using_model("model.safetensors")

        assert len(result) == 1
        assert "test.json" in result
