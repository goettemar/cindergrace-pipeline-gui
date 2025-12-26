"""Pytest configuration and shared fixtures"""
import sys
import os
import json
import sqlite3
from pathlib import Path
import pytest
from unittest.mock import Mock, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(autouse=True)
def reset_settings_store():
    """Reset the SettingsStore singleton and clear settings before each test.

    This ensures tests don't affect each other via the singleton.
    """
    import infrastructure.settings_store as ss

    # Reset the singleton
    ss._settings_store = None

    yield

    # Clean up after test - clear all settings except internal ones
    if ss._settings_store is not None:
        try:
            conn = sqlite3.connect(ss._settings_store.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM settings WHERE key NOT LIKE '\\_%' ESCAPE '\\'")
            conn.commit()
            conn.close()
        except Exception:
            pass

    # Reset singleton again
    ss._settings_store = None


# ============================================================================
# Directory Fixtures
# ============================================================================

@pytest.fixture
def temp_project_dir(tmp_path):
    """Create temporary project directory structure"""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    (project_dir / "keyframes").mkdir()
    (project_dir / "selected").mkdir()
    (project_dir / "video").mkdir()
    (project_dir / "checkpoints").mkdir()
    return project_dir


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create temporary config directory"""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "workflow_templates").mkdir()
    return config_dir


# ============================================================================
# Storyboard Fixtures
# ============================================================================

@pytest.fixture
def sample_storyboard_data():
    """Sample storyboard data as dict"""
    return {
        "project": "Test Project",
        "shots": [
            {
                "shot_id": "001",
                "filename_base": "cathedral-interior",
                "prompt": "gothic cathedral interior, dramatic lighting",
                "width": 1024,
                "height": 576,
                "duration": 3.0,
                "camera_movement": "slow_push",
                "wan_motion": {
                    "type": "macro_dolly",
                    "strength": 0.6,
                    "notes": "Small forward move"
                }
            },
            {
                "shot_id": "002",
                "filename_base": "hand-book",
                "prompt": "close-up of pale hand with silver rings",
                "width": 1024,
                "height": 576,
                "duration": 2.5,
                "camera_movement": "static"
            },
            {
                "shot_id": "003",
                "filename_base": "window-rain",
                "prompt": "rain streaming down gothic window",
                "width": 1024,
                "height": 576,
                "duration": 5.0,
                "camera_movement": "slow_pan"
            }
        ],
        "video_settings": {
            "default_fps": 24,
            "default_workflow": "Wan 2.2 14B i2v.json",
            "max_duration": 3.0
        }
    }


@pytest.fixture
def sample_storyboard_file(tmp_path, sample_storyboard_data):
    """Create temporary storyboard JSON file"""
    storyboard_file = tmp_path / "test_storyboard.json"
    with open(storyboard_file, "w") as f:
        json.dump(sample_storyboard_data, f, indent=2)
    return storyboard_file


@pytest.fixture
def sample_storyboard_minimal():
    """Minimal valid storyboard"""
    return {
        "project": "Minimal Test",
        "shots": [
            {
                "shot_id": "001",
                "filename_base": "test-shot",
                "prompt": "test prompt",
                "width": 1024,
                "height": 576,
                "duration": 3.0
            }
        ]
    }


# ============================================================================
# Selection Fixtures
# ============================================================================

@pytest.fixture
def sample_selection_data():
    """Sample selection data"""
    return {
        "project": "Test Project",
        "total_shots": 3,
        "exported_at": "2024-12-12T10:15:01",
        "selections": [
            {
                "shot_id": "001",
                "filename_base": "cathedral-interior",
                "selected_variant": 2,
                "selected_file": "cathedral-interior_v2_00001_.png",
                "source_path": "/path/to/keyframes/cathedral-interior_v2_00001_.png",
                "export_path": "/path/to/selected/cathedral-interior_v2_00001_.png"
            },
            {
                "shot_id": "002",
                "filename_base": "hand-book",
                "selected_variant": 1,
                "selected_file": "hand-book_v1_00001_.png",
                "source_path": "/path/to/keyframes/hand-book_v1_00001_.png",
                "export_path": "/path/to/selected/hand-book_v1_00001_.png"
            }
        ]
    }


@pytest.fixture
def sample_selection_file(tmp_path, sample_selection_data):
    """Create temporary selection JSON file"""
    selection_file = tmp_path / "selected_keyframes.json"
    with open(selection_file, "w") as f:
        json.dump(sample_selection_data, f, indent=2)
    return selection_file


# ============================================================================
# Workflow Fixtures
# ============================================================================

@pytest.fixture
def sample_flux_workflow():
    """Sample Flux workflow structure"""
    return {
        "1": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "test prompt",
                "clip": ["2", 0]
            }
        },
        "2": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": "flux1-krea-dev.safetensors"
            }
        },
        "3": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": 1024,
                "height": 576,
                "batch_size": 1
            }
        },
        "4": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 1001,
                "steps": 20,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["2", 0],
                "positive": ["1", 0],
                "negative": ["5", 0],
                "latent_image": ["3", 0]
            }
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "bad quality",
                "clip": ["2", 0]
            }
        },
        "6": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "test_output",
                "images": ["7", 0]
            }
        }
    }


@pytest.fixture
def sample_wan_workflow():
    """Sample Wan workflow structure"""
    return {
        "1": {
            "class_type": "LoadImage",
            "inputs": {
                "image": "startframe.png"
            }
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "test video prompt"
            }
        },
        "3": {
            "class_type": "HunyuanVideoSampler",
            "inputs": {
                "num_frames": 72,
                "seed": 1001,
                "steps": 30,
                "embedded_guidance_scale": 6.0
            }
        }
    }


# ============================================================================
# Config Fixtures
# ============================================================================

@pytest.fixture
def sample_config():
    """Sample configuration"""
    return {
        "comfy_url": "http://127.0.0.1:8188",
        "comfy_root": "/home/user/ComfyUI",
        "workflow_dir": "config/workflow_templates",
        "output_dir": "output",
        "active_project_slug": None
    }


@pytest.fixture
def sample_config_file(tmp_path, sample_config):
    """Create temporary config file"""
    config_file = tmp_path / "config" / "settings.json"
    config_file.parent.mkdir(exist_ok=True)
    with open(config_file, "w") as f:
        json.dump(sample_config, f, indent=2)
    return config_file


# ============================================================================
# Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_comfy_api():
    """Mock ComfyUIAPI"""
    mock = Mock()
    mock.test_connection.return_value = {
        "status": "success",
        "system_stats": {"ram_used": 1000}
    }
    mock.queue_prompt.return_value = "test-prompt-id-123"
    mock.monitor_progress.return_value = {
        "status": "success",
        "outputs": {"images": ["test.png"]}
    }
    mock.get_output_images.return_value = ["/path/to/output/test.png"]
    return mock


@pytest.fixture
def mock_config_manager(tmp_path):
    """Mock ConfigManager"""
    mock = Mock()
    mock.config_dir = str(tmp_path / "config")
    mock.comfy_url = "http://127.0.0.1:8188"
    mock.comfy_root = "/home/user/ComfyUI"
    mock.workflow_dir = str(tmp_path / "config" / "workflow_templates")
    mock.output_dir = str(tmp_path / "output")
    mock.get_comfy_url.return_value = "http://127.0.0.1:8188"
    mock.get_comfy_root.return_value = "/home/user/ComfyUI"
    return mock


@pytest.fixture
def mock_project_store(temp_project_dir):
    """Mock ProjectStore"""
    mock = Mock()
    mock.get_active_project.return_value = {
        "name": "Test Project",
        "slug": "test-project",
        "path": str(temp_project_dir),
        "created_at": "2024-12-12T10:00:00",
        "last_opened": "2024-12-12T10:00:00"
    }
    mock.create_project.return_value = {
        "name": "New Project",
        "slug": "new-project",
        "path": str(temp_project_dir),
        "created_at": "2024-12-12T10:00:00"
    }
    return mock


# ============================================================================
# Helper Functions
# ============================================================================

@pytest.fixture
def create_test_image(tmp_path):
    """Factory to create test PNG images"""
    def _create(filename, width=1024, height=576):
        from PIL import Image
        import numpy as np
        
        img_path = tmp_path / filename
        img_array = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
        img = Image.fromarray(img_array)
        img.save(img_path)
        return img_path
    
    return _create


@pytest.fixture
def create_keyframe_variants(tmp_path, create_test_image):
    """Factory to create keyframe variant files"""
    def _create(filename_base, num_variants=4):
        keyframes_dir = tmp_path / "keyframes"
        keyframes_dir.mkdir(exist_ok=True)
        
        created_files = []
        for variant in range(1, num_variants + 1):
            filename = f"{filename_base}_v{variant}_00001_.png"
            img_path = keyframes_dir / filename
            create_test_image(img_path.name)
            created_files.append(img_path)
        
        return created_files
    
    return _create
