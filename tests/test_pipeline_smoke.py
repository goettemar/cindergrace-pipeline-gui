import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from infrastructure.config_manager import ConfigManager
from infrastructure.project_store import ProjectStore
from domain.storyboard_service import StoryboardService
from domain.models import SelectionSet
from services.selection_service import SelectionService
from services.video.video_plan_builder import VideoPlanBuilder


def _write_config(config_path: Path, comfy_root: Path) -> ConfigManager:
    cfg = ConfigManager(config_path=str(config_path))
    cfg.config["comfy_root"] = str(comfy_root)
    cfg.config["workflow_dir"] = "config/workflow_templates"
    cfg.save(cfg.config)
    return cfg


def _make_storyboard(path: Path) -> dict:
    storyboard = {
        "project": "Smoke Project",
        "shots": [
            {
                "shot_id": "001",
                "filename_base": "shot1",
                "description": "Test shot 1",
                "prompt": "A simple prompt",
                "width": 640,
                "height": 360,
                "duration": 1.0,
            },
            {
                "shot_id": "002",
                "filename_base": "shot2",
                "description": "Test shot 2",
                "prompt": "Another prompt",
                "width": 640,
                "height": 360,
                "duration": 1.5,
            },
        ],
    }
    path.write_text(json.dumps(storyboard, indent=2))
    return storyboard


def _make_keyframe_image(path: Path) -> None:
    img = Image.new("RGB", (64, 36), color=(123, 222, 111))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


@pytest.mark.smoke
@patch("infrastructure.project_store.get_db_path")
def test_smoke_storyboard_keyframe_selection_to_plan(mock_db_path, tmp_path: Path):
    """End-to-end smoke: storyboard -> selection export -> plan builder."""
    # Use temporary database to avoid polluting production database
    mock_db_path.return_value = str(tmp_path / "test_cindergrace.db")

    comfy_root = tmp_path / "comfy"
    comfy_root.mkdir(parents=True, exist_ok=True)
    settings_path = tmp_path / "settings.json"
    cfg = _write_config(settings_path, comfy_root)

    store = ProjectStore(cfg)
    project = store.create_project("Smoke Demo")

    # Prepare storyboard file
    storyboard_path = Path(project["path"]) / "storyboards" / "storyboard_smoke.json"
    storyboard_dict = _make_storyboard(storyboard_path)
    storyboard_model = StoryboardService.load_from_file(str(storyboard_path))

    # Create dummy keyframes
    keyframes_dir = store.ensure_dir(project, "keyframes")
    shot1_path = Path(keyframes_dir) / "shot1_v1_00001_.png"
    shot2_path = Path(keyframes_dir) / "shot2_v1_00001_.png"
    _make_keyframe_image(shot1_path)
    _make_keyframe_image(shot2_path)

    # Build selections state
    selections_state = {
        "001": {
            "shot_id": "001",
            "filename_base": "shot1",
            "selected_variant": 1,
            "selected_file": shot1_path.name,
            "source_path": str(shot1_path),
        },
        "002": {
            "shot_id": "002",
            "filename_base": "shot2",
            "selected_variant": 1,
            "selected_file": shot2_path.name,
            "source_path": str(shot2_path),
        },
    }

    # Export selections (copies files and writes JSON)
    selection_service = SelectionService(store)
    export_payload = selection_service.export_selections(project, storyboard_dict, selections_state)
    export_path = Path(export_payload["_path"])
    assert export_path.exists(), "Selection JSON should be written"
    assert export_payload["_copied"] == 2, "Keyframes should be copied to selected/"

    # Ensure copied files exist
    for entry in export_payload["selections"]:
        assert entry.get("export_path") and Path(entry["export_path"]).exists()

    # Build plan
    selection_set = SelectionSet.from_dict(export_payload)
    plan_builder = VideoPlanBuilder()
    plan = plan_builder.build(storyboard_model, selection_set)

    # All segments should be ready and reference valid start_frame paths
    assert plan.segments, "Plan should contain segments"
    for seg in plan.segments:
        assert seg.ready is True
        assert seg.start_frame and Path(seg.start_frame).exists()
        assert seg.duration > 0

    # Segments match shot count (durations small → no splitting)
    assert len(plan.segments) == len(storyboard_dict["shots"])
