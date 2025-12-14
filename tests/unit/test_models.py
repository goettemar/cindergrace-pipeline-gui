"""Unit tests for domain models utilities"""
import pytest

from domain.models import (
    MotionSettings,
    Shot,
    Storyboard,
    SelectionEntry,
    SelectionSet,
    PlanSegment,
    GenerationPlan,
)


@pytest.mark.unit
def test_storyboard_get_shot_returns_none_when_missing():
    storyboard = Storyboard(project="Test", shots=[])
    assert storyboard.get_shot("001") is None


@pytest.mark.unit
def test_selection_set_get_selection_and_default_values():
    entry = SelectionEntry.from_dict(
        {"shot_id": "001", "filename_base": "base", "selected_variant": 2, "selected_file": "f.png", "source_path": "/tmp/f.png"}
    )
    selection = SelectionSet(project="Test", selections=[entry], total_shots=1, exported_at="2025-01-01")

    assert selection.get_selection("001") == entry
    assert selection.get_selection("999") is None


@pytest.mark.unit
def test_plan_segment_to_dict_sets_defaults():
    segment = PlanSegment(
        plan_id="001",
        shot_id="001",
        filename_base="base",
        prompt="p",
        width=1280,
        height=720,
        duration=3.0,
        segment_index=1,
        segment_total=1,
        target_duration=3.0,
        effective_duration=3.0,
        segment_requested_duration=3.0,
        start_frame=None,
        start_frame_source="missing",
        wan_motion=MotionSettings(type="move", strength=0.5),
        ready=True,
        status="",
        output_files=[],
        meta={"foo": "bar"},
    )

    payload = segment.to_dict()
    assert payload["chain_id"] == ""  # preserved because asdict already sets key
    assert payload["status"] == ""  # value remains as provided when key exists
    assert payload["output_files"] == []
    assert payload["start_frame_source"] == "missing"


@pytest.mark.unit
def test_generation_plan_to_dict_list():
    segments = [
        PlanSegment(
            plan_id="001",
            shot_id="001",
            filename_base="base",
            prompt="p",
            width=1280,
            height=720,
            duration=3.0,
            segment_index=1,
            segment_total=1,
            target_duration=3.0,
            effective_duration=3.0,
            segment_requested_duration=3.0,
            start_frame=None,
            start_frame_source="missing",
            wan_motion=None,
            ready=True,
        )
    ]

    plan = GenerationPlan(segments=segments)
    dict_list = plan.to_dict_list()
    assert isinstance(dict_list, list)
    assert dict_list[0]["plan_id"] == "001"
