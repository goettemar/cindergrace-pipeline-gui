"""Additional coverage for VideoGenerationService edge branches."""
from unittest.mock import Mock

import pytest

from services.video.video_generation_service import VideoGenerationService


@pytest.fixture
def service(tmp_path):
    project_store = Mock()
    project_store.ensure_dir.side_effect = lambda project, *sub: str(tmp_path / "video")
    project_store.comfy_output_dir.return_value = str(tmp_path / "comfy")
    # Add config mock with timeout settings
    project_store.config = Mock()
    project_store.config.get_video_initial_wait.return_value = 0
    project_store.config.get_video_retry_delay.return_value = 0
    project_store.config.get_video_max_retries.return_value = 1
    model_validator = Mock()
    state_store = Mock()
    return VideoGenerationService(project_store, model_validator, state_store)


def test_run_generation_waits_for_chain_startframe(service):
    """Should log wait/skip messages for non-ready entries."""
    plan = [
        {"shot_id": "001", "segment_index": 1, "segment_total": 2, "ready": False, "start_frame_source": "chain_wait"},
        {"shot_id": "001", "segment_index": 2, "segment_total": 2, "ready": False},
    ]
    working, logs, last = service.run_generation(plan, workflow_template={}, fps=24, project={}, comfy_api=Mock())

    assert any("wartet" in log for log in logs)
    assert any("übersprungen" in log for log in logs)
    assert last is None


def test_run_generation_generated_no_copy(service):
    """Should mark entry when job returns without outputs."""
    plan = [
        {"shot_id": "001", "segment_index": 1, "segment_total": 1, "ready": True},
    ]
    service._run_video_job = Mock(return_value=([], None))

    working, logs, _ = service.run_generation(plan, workflow_template={}, fps=24, project={}, comfy_api=Mock())

    assert working[0]["status"] == "generated_no_copy"
    assert any("keine Video-Datei gefunden" in log for log in logs)


def test_copy_video_outputs_skips_files_inside_project(service, tmp_path, monkeypatch):
    """Should skip files already inside the project path (commonpath guard)."""
    project = {"path": str(tmp_path)}
    comfy_output = tmp_path / "out"
    comfy_output.mkdir()
    inside_file = comfy_output / "clipA.mp4"
    inside_file.write_text("data")
    service.project_store.comfy_output_dir.return_value = str(comfy_output)

    # Simulate glob yielding a file within project path
    monkeypatch.setattr("glob.glob", lambda pattern, recursive=False: [str(inside_file)])

    copied = service._copy_video_outputs({"clip_name": "clipA"}, project)
    assert copied == []  # skipped due to commonpath guard


def test_propagate_chain_start_frame_no_next_segment(service):
    """Should return None when no next segment exists."""
    plan = [
        {"shot_id": "001", "segment_index": 1, "segment_total": 1},
    ]
    result = service._propagate_chain_start_frame(plan, plan[0], "/path/frame.png")
    assert result is None


def test_run_generation_logs_missing_last_frame(service):
    """Should log warning when last_frame_path is missing for chained segments."""
    plan = [
        {"shot_id": "001", "segment_index": 1, "segment_total": 2, "ready": True},
    ]
    service._run_video_job = Mock(return_value=(["clip.mp4"], None))

    working, logs, _ = service.run_generation(plan, workflow_template={}, fps=24, project={}, comfy_api=Mock())

    assert any("LastFrame konnte nicht extrahiert" in log for log in logs)
    assert working[0]["status"] == "completed"


def test_apply_video_params_sets_path_and_frame_rate(tmp_path):
    """_apply_video_params should map start_frame to filename/path and set frame_rate."""
    from services.video.video_generation_service import VideoGenerationService

    project_store = Mock()
    model_validator = Mock()
    state_store = Mock()
    service = VideoGenerationService(project_store, model_validator, state_store)
    comfy_api = Mock()

    workflow = {
        "1": {"class_type": "LoadImage", "inputs": {"filename": ""}},
        "2": {"class_type": "ImageInput", "inputs": {"path": ""}},
        "3": {"class_type": "SaveVideo", "inputs": {"filename_prefix": ""}},
        "4": {"class_type": "Custom", "inputs": {"frame_rate": 0}},
    }
    comfy_api.update_workflow_params.return_value = workflow

    updated = service._apply_video_params(
        workflow=workflow,
        comfy_api=comfy_api,
        prompt="p",
        width=128,
        height=72,
        filename_prefix="clip name",
        start_frame_path="/tmp/start.png",
        fps=30,
        frames=12,
    )

    assert updated["1"]["inputs"]["filename"] == "/tmp/start.png"
    assert updated["2"]["inputs"]["path"] == "/tmp/start.png"
    assert updated["4"]["inputs"]["frame_rate"] == 30
    assert updated["3"]["inputs"]["filename_prefix"] == "clip_name"


def test_propagate_chain_start_frame_missing_next_segment(service):
    """Should return None when next segment not found though total suggests more."""
    plan = [
        {"shot_id": "001", "segment_index": 1, "segment_total": 2},
    ]

    result = service._propagate_chain_start_frame(plan, plan[0], "/path/frame.png")
    assert result is None
