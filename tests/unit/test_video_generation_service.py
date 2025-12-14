"""Unit tests for VideoGenerationService"""
import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from services.video.video_generation_service import VideoGenerationService
from infrastructure.model_validator import ModelValidator
from infrastructure.state_store import VideoGeneratorStateStore


@pytest.fixture
def project_store(tmp_path):
    """ProjectStore mock that creates real directories under tmp_path"""
    store = Mock()
    comfy_output = tmp_path / "comfy_output"
    store.comfy_output_dir.return_value = str(comfy_output)

    def ensure_dir(project, *parts):
        dest = Path(project["path"]).joinpath(*parts)
        dest.mkdir(parents=True, exist_ok=True)
        return str(dest)

    store.ensure_dir.side_effect = ensure_dir
    return store


@pytest.fixture
def service(project_store):
    return VideoGenerationService(
        project_store=project_store,
        model_validator=Mock(spec=ModelValidator),
        state_store=Mock(spec=VideoGeneratorStateStore),
    )


class TestApplyVideoParams:
    """Tests for _apply_video_params()"""

    @pytest.mark.unit
    def test_injects_startframe_and_runtime_values(self, service):
        """Should inject fps, frames, startframe, and sanitize filename"""
        comfy_api = Mock()
        workflow = {
            "1": {"class_type": "LoadImage", "inputs": {"image": ""}},
            "2": {"class_type": "SaveVideo", "inputs": {"filename_prefix": ""}},
            "3": {"class_type": "EmptyLatentImage", "inputs": {"width": 0, "height": 0}},
            "4": {"class_type": "VideoHelper", "inputs": {"fps": 0, "frame_count": 0}},
        }
        comfy_api.update_workflow_params.return_value = workflow

        updated = service._apply_video_params(
            comfy_api=comfy_api,
            workflow=workflow,
            prompt="test prompt",
            width=1280,
            height=720,
            filename_prefix="clip name/!",
            start_frame_path="/tmp/frame.png",
            fps=24,
            frames=48,
        )

        assert updated["1"]["inputs"]["image"] == "/tmp/frame.png"
        assert updated["2"]["inputs"]["filename_prefix"] == "clip_name_"
        assert updated["3"]["inputs"]["width"] == 1280
        assert updated["3"]["inputs"]["height"] == 720
        assert updated["4"]["inputs"]["fps"] == 24
        assert updated["4"]["inputs"]["frame_count"] == 48


class TestCopyVideoOutputs:
    """Tests for _copy_video_outputs()"""

    @pytest.mark.unit
    def test_copies_matching_outputs(self, service, project_store, tmp_path):
        """Should copy videos from ComfyUI output into project folder"""
        comfy_output = Path(project_store.comfy_output_dir.return_value)
        comfy_output.mkdir(parents=True, exist_ok=True)
        (comfy_output / "clipA.mp4").write_text("video-a")

        video_dir = comfy_output / "video"
        video_dir.mkdir(parents=True, exist_ok=True)
        (video_dir / "ComfyUI_00001.webm").write_text("video-b")

        project = {"path": str(tmp_path / "project")}
        entry = {
            "clip_name": "clipA",
            "filename_base": "clipA",
            "shot_id": "001",
            "segment_index": 1,
            "segment_total": 1,
        }

        copied = service._copy_video_outputs(entry, project)

        assert len(copied) == 2
        assert all(Path(path).exists() for path in copied)
        assert Path(copied[0]).name.startswith("clipA")

    @pytest.mark.unit
    def test_returns_empty_when_comfy_output_missing(self, service, project_store, tmp_path):
        """Should return empty list if ComfyUI output directory is missing"""
        project_store.comfy_output_dir.side_effect = FileNotFoundError("missing")
        project = {"path": str(tmp_path / "project")}

        copied = service._copy_video_outputs({}, project)

        assert copied == []


class TestHelperMethods:
    """Tests for helper methods used by VideoGenerationService"""

    @pytest.mark.unit
    def test_build_video_filename_avoids_collisions(self, service, tmp_path):
        """Should append counter when filename already exists"""
        dest_dir = tmp_path / "project" / "video"
        dest_dir.mkdir(parents=True, exist_ok=True)

        existing = dest_dir / "clip_name.mp4"
        existing.write_text("existing")

        filename = service._build_video_filename(
            base_name="clip name",
            entry={},
            ext="mp4",
            dest_dir=str(dest_dir),
        )

        assert filename == "clip_name_1.mp4"

    @pytest.mark.unit
    def test_propagate_chain_start_frame_sets_next_segment(self, service):
        """Should update next segment in chain and mark it ready"""
        plan = [
            {"shot_id": "001", "segment_index": 1, "segment_total": 2, "plan_id": "001"},
            {
                "shot_id": "001",
                "segment_index": 2,
                "segment_total": 2,
                "plan_id": "001B",
                "ready": False,
                "status": "no_start",
            },
        ]

        target_id = service._propagate_chain_start_frame(plan, plan[0], "/tmp/frame.png")

        assert target_id == "001B"
        assert plan[1]["start_frame"] == "/tmp/frame.png"
        assert plan[1]["start_frame_source"] == "chain"
        assert plan[1]["ready"] is True
        assert plan[1]["status"] == "pending"


class TestRunGeneration:
    """Tests for run_generation() orchestration"""

    @pytest.mark.unit
    @patch("services.video.video_generation_service.LastFrameExtractor")
    def test_processes_ready_segments_and_propagates_frames(
        self, mock_extractor, service, tmp_path
    ):
        """Should mark completed entries and propagate startframe to next segment"""
        mock_extractor.return_value.is_available.return_value = True
        mock_extractor.return_value.extract.return_value = "/tmp/frame.png"

        service._run_video_job = Mock(
            return_value=([str(tmp_path / "video.mp4")], "/tmp/frame.png")
        )

        plan_state = [
            {
                "plan_id": "001",
                "shot_id": "001",
                "segment_index": 1,
                "segment_total": 2,
                "ready": True,
                "clip_name": "clip",
            },
            {
                "plan_id": "001B",
                "shot_id": "001",
                "segment_index": 2,
                "segment_total": 2,
                "ready": False,
                "start_frame_source": "chain_wait",
            },
        ]

        project = {"path": str(tmp_path / "project")}
        comfy_api = Mock()

        updated_plan, logs, last_video = service.run_generation(
            plan_state=plan_state,
            workflow_template={"nodes": {}},
            fps=24,
            project=project,
            comfy_api=comfy_api,
        )

        assert updated_plan[0]["status"] == "completed"
        assert updated_plan[0]["output_files"] == [str(tmp_path / "video.mp4")]
        assert updated_plan[1]["start_frame"] == "/tmp/frame.png"
        assert updated_plan[1]["ready"] is True
        assert any("Startframe an Segment" in log for log in logs)
        assert last_video == str(tmp_path / "video.mp4")

    @pytest.mark.unit
    @patch("services.video.video_generation_service.LastFrameExtractor")
    def test_handles_video_job_errors(self, mock_extractor, service, tmp_path):
        """Should capture errors and continue processing other entries"""
        mock_extractor.return_value.is_available.return_value = False
        service._run_video_job = Mock(side_effect=RuntimeError("boom"))

        plan_state = [
            {"shot_id": "001", "segment_index": 1, "segment_total": 1, "ready": True},
            {"shot_id": "002", "segment_index": 1, "segment_total": 1, "ready": False},
        ]

        project = {"path": str(tmp_path / "project")}
        comfy_api = Mock()

        updated_plan, logs, last_video = service.run_generation(
            plan_state=plan_state,
            workflow_template={},
            fps=24,
            project=project,
            comfy_api=comfy_api,
        )

        assert updated_plan[0]["status"].startswith("error")
        assert any("boom" in log for log in logs)
        assert updated_plan[1].get("ready") is False
        assert updated_plan[1].get("status") is None
        assert last_video is None


class TestRunVideoJob:
    """Tests for _run_video_job() execution wrapper"""

    @pytest.mark.unit
    def test_run_video_job_success(self, service, tmp_path):
        """Should queue prompt, copy outputs, and extract last frame"""
        comfy_api = Mock()
        comfy_api.update_workflow_params.return_value = {"1": {"inputs": {}}}
        comfy_api.queue_prompt.return_value = "job-1"
        comfy_api.monitor_progress.return_value = {"status": "success"}

        service._copy_video_outputs = Mock(return_value=[str(tmp_path / "video.mp4")])

        extractor = Mock()
        extractor.extract.return_value = "last_frame.png"

        entry = {
            "shot_id": "001",
            "segment_index": 1,
            "segment_total": 2,
            "clip_name": "clip",
            "prompt": "test",
            "width": 640,
            "height": 360,
            "effective_duration": 1.5,
        }

        videos, last_frame = service._run_video_job(
            workflow_template={"1": {"inputs": {}}},
            entry=entry,
            fps=24,
            project={"path": str(tmp_path / "project")},
            comfy_api=comfy_api,
            extractor=extractor,
        )

        assert videos == [str(tmp_path / "video.mp4")]
        assert last_frame == "last_frame.png"
        comfy_api.queue_prompt.assert_called_once()
        comfy_api.monitor_progress.assert_called_once_with("job-1", timeout=1800)

    @pytest.mark.unit
    def test_run_video_job_raises_on_failed_monitor(self, service, tmp_path):
        """Should raise when ComfyUI returns non-success status"""
        comfy_api = Mock()
        comfy_api.update_workflow_params.return_value = {"1": {"inputs": {}}}
        comfy_api.queue_prompt.return_value = "job-2"
        comfy_api.monitor_progress.return_value = {"status": "failed", "error": "bad"}

        extractor = Mock()
        extractor.extract.return_value = None
        service._copy_video_outputs = Mock(return_value=[str(tmp_path / "video.mp4")])

        entry = {"effective_duration": 1.0, "segment_total": 1, "segment_index": 1}

        with pytest.raises(RuntimeError):
            service._run_video_job(
                workflow_template={"1": {"inputs": {}}},
                entry=entry,
                fps=24,
                project={"path": str(tmp_path / "project")},
                comfy_api=comfy_api,
                extractor=extractor,
            )

    @pytest.mark.unit
    def test_run_video_job_raises_when_no_outputs(self, service, tmp_path):
        """Should raise when no video files are copied"""
        comfy_api = Mock()
        comfy_api.update_workflow_params.return_value = {"1": {"inputs": {}}}
        comfy_api.queue_prompt.return_value = "job-3"
        comfy_api.monitor_progress.return_value = {"status": "success"}

        extractor = Mock()
        extractor.extract.return_value = None
        service._copy_video_outputs = Mock(return_value=[])

        entry = {"effective_duration": 1.0, "segment_total": 1, "segment_index": 1}

        with pytest.raises(RuntimeError):
            service._run_video_job(
                workflow_template={"1": {"inputs": {}}},
                entry=entry,
                fps=24,
                project={"path": str(tmp_path / "project")},
                comfy_api=comfy_api,
                extractor=extractor,
            )
