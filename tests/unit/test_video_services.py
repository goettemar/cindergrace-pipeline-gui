"""Unit tests for Video Services (VideoPlanBuilder)"""
import pytest
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from services.video.video_plan_builder import VideoPlanBuilder
from domain.models import (
    Storyboard, Shot, SelectionSet, SelectionEntry,
    MotionSettings, GenerationPlan
)


class TestVideoPlanBuilderBuild:
    """Test VideoPlanBuilder.build()"""

    @pytest.mark.unit
    def test_build_single_shot_under_3s(self, tmp_path):
        """Should create single segment for shot under 3 seconds"""
        # Arrange
        builder = VideoPlanBuilder()  # Uses defaults: 73 frames @ 24 fps ≈ 3.04s

        # Create test startframe
        startframe_path = tmp_path / "shot001_v1.png"
        startframe_path.write_text("fake image")

        storyboard = Storyboard(
            project="Test Project",
            shots=[
                Shot(
                    shot_id="001",
                    filename_base="test-shot",
                    prompt="test prompt",
                    width=1024,
                    height=576,
                    duration=2.5
                )
            ]
        )

        selection = SelectionSet(
            project="Test Project",
            selections=[
                SelectionEntry(
                    shot_id="001",
                    filename_base="test-shot",
                    selected_variant=1,
                    selected_file="test-shot_v1.png",
                    source_path=str(startframe_path),
                    export_path=str(startframe_path)
                )
            ]
        )

        # Act
        plan = builder.build(storyboard, selection)

        # Assert
        assert len(plan.segments) == 1
        segment = plan.segments[0]
        assert segment.plan_id == "001"
        assert segment.shot_id == "001"
        assert segment.segment_index == 1
        assert segment.segment_total == 1
        assert segment.duration == 2.5
        assert segment.start_frame == str(startframe_path)
        assert segment.start_frame_source == "selection"
        assert segment.ready is True

    @pytest.mark.unit
    def test_build_single_shot_over_3s_segmented(self, tmp_path):
        """Should split shot over 3 seconds into multiple segments"""
        # Arrange
        builder = VideoPlanBuilder()  # Uses defaults: 73 frames @ 24 fps ≈ 3.04s

        startframe_path = tmp_path / "shot001_v1.png"
        startframe_path.write_text("fake image")

        storyboard = Storyboard(
            project="Test Project",
            shots=[
                Shot(
                    shot_id="001",
                    filename_base="long-shot",
                    prompt="test prompt",
                    width=1024,
                    height=576,
                    duration=5.0  # Will split into 2 segments
                )
            ]
        )

        selection = SelectionSet(
            project="Test Project",
            selections=[
                SelectionEntry(
                    shot_id="001",
                    filename_base="long-shot",
                    selected_variant=1,
                    selected_file="long-shot_v1.png",
                    source_path=str(startframe_path),
                    export_path=str(startframe_path)
                )
            ]
        )

        # Act
        plan = builder.build(storyboard, selection)

        # Assert
        assert len(plan.segments) == 2

        # First segment
        seg1 = plan.segments[0]
        assert seg1.plan_id == "001"
        assert seg1.segment_index == 1
        assert seg1.segment_total == 2
        assert seg1.start_frame == str(startframe_path)
        assert seg1.start_frame_source == "selection"
        assert seg1.ready is True

        # Second segment (waits for chain)
        seg2 = plan.segments[1]
        # Note: Suffix starts at 'B' because chr(ord('A') + idx) where idx=1 gives 'B'
        assert seg2.plan_id == "001B"  # Suffixed with B (idx=1)
        assert seg2.segment_index == 2
        assert seg2.segment_total == 2
        assert seg2.start_frame is None
        assert seg2.start_frame_source == "chain_wait"
        assert seg2.ready is False

    @pytest.mark.unit
    def test_build_multiple_shots(self, tmp_path):
        """Should handle multiple shots correctly"""
        # Arrange
        builder = VideoPlanBuilder()  # Uses defaults: 73 frames @ 24 fps ≈ 3.04s

        # Create startframes
        sf1 = tmp_path / "shot001_v1.png"
        sf2 = tmp_path / "shot002_v2.png"
        sf1.write_text("fake")
        sf2.write_text("fake")

        storyboard = Storyboard(
            project="Test",
            shots=[
                Shot(shot_id="001", filename_base="shot1", prompt="p1", duration=2.0),
                Shot(shot_id="002", filename_base="shot2", prompt="p2", duration=4.0),
            ]
        )

        selection = SelectionSet(
            project="Test",
            selections=[
                SelectionEntry(
                    shot_id="001", filename_base="shot1",
                    selected_variant=1, selected_file="shot001_v1.png",
                    source_path=str(sf1), export_path=str(sf1)
                ),
                SelectionEntry(
                    shot_id="002", filename_base="shot2",
                    selected_variant=2, selected_file="shot002_v2.png",
                    source_path=str(sf2), export_path=str(sf2)
                ),
            ]
        )

        # Act
        plan = builder.build(storyboard, selection)

        # Assert - Shot 1: 1 segment, Shot 2: 2 segments (4s duration)
        assert len(plan.segments) == 3
        assert plan.segments[0].shot_id == "001"
        assert plan.segments[1].shot_id == "002"
        assert plan.segments[2].shot_id == "002"

    @pytest.mark.unit
    def test_build_with_missing_selection(self, tmp_path):
        """Should create placeholder for shot without selection"""
        # Arrange
        builder = VideoPlanBuilder()  # Uses defaults: 73 frames @ 24 fps ≈ 3.04s

        storyboard = Storyboard(
            project="Test",
            shots=[
                Shot(shot_id="001", filename_base="shot1", prompt="p1", duration=2.0),
            ]
        )

        selection = SelectionSet(project="Test", selections=[])  # No selections

        # Act
        plan = builder.build(storyboard, selection)

        # Assert
        assert len(plan.segments) == 1
        segment = plan.segments[0]
        assert segment.status == "no_selection"
        assert segment.start_frame is None
        assert segment.start_frame_source == "missing"
        assert segment.ready is False

    @pytest.mark.unit
    def test_build_with_missing_startframe(self, tmp_path):
        """Should create placeholder when startframe file doesn't exist"""
        # Arrange
        builder = VideoPlanBuilder()  # Uses defaults: 73 frames @ 24 fps ≈ 3.04s

        storyboard = Storyboard(
            project="Test",
            shots=[
                Shot(shot_id="001", filename_base="shot1", prompt="p1", duration=2.0),
            ]
        )

        # Selection points to non-existent file
        selection = SelectionSet(
            project="Test",
            selections=[
                SelectionEntry(
                    shot_id="001", filename_base="shot1",
                    selected_variant=1, selected_file="missing.png",
                    source_path="/nonexistent/file.png",
                    export_path=None
                )
            ]
        )

        # Act
        plan = builder.build(storyboard, selection)

        # Assert
        assert len(plan.segments) == 1
        segment = plan.segments[0]
        assert segment.status == "startframe_missing"
        assert segment.start_frame is None
        assert segment.ready is False

    @pytest.mark.unit
    def test_build_with_wan_motion(self, tmp_path):
        """Should preserve wan_motion settings in segments"""
        # Arrange
        builder = VideoPlanBuilder()  # Uses defaults: 73 frames @ 24 fps ≈ 3.04s

        startframe_path = tmp_path / "shot001_v1.png"
        startframe_path.write_text("fake")

        motion = MotionSettings(type="macro_dolly", strength=0.6, notes="test")

        storyboard = Storyboard(
            project="Test",
            shots=[
                Shot(
                    shot_id="001", filename_base="shot1", prompt="p1",
                    duration=2.0, wan_motion=motion
                ),
            ]
        )

        selection = SelectionSet(
            project="Test",
            selections=[
                SelectionEntry(
                    shot_id="001", filename_base="shot1",
                    selected_variant=1, selected_file="shot001_v1.png",
                    source_path=str(startframe_path), export_path=str(startframe_path)
                )
            ]
        )

        # Act
        plan = builder.build(storyboard, selection)

        # Assert
        segment = plan.segments[0]
        assert segment.wan_motion is not None
        assert segment.wan_motion.type == "macro_dolly"
        assert segment.wan_motion.strength == 0.6

    @pytest.mark.unit
    def test_build_segmentation_math(self, tmp_path):
        """Should calculate correct number of segments"""
        # Arrange
        builder = VideoPlanBuilder()  # Uses defaults: 73 frames @ 24 fps ≈ 3.04s

        startframe = tmp_path / "sf.png"
        startframe.write_text("fake")

        test_cases = [
            (2.5, 1),   # Under 3s → 1 segment
            (3.0, 1),   # Exactly 3s → 1 segment
            (4.0, 2),   # 4s → 2 segments
            (6.0, 2),   # 6s → 2 segments
            (7.0, 3),   # 7s → 3 segments
            (9.0, 3),   # 9s → 3 segments
        ]

        for duration, expected_segments in test_cases:
            storyboard = Storyboard(
                project="Test",
                shots=[
                    Shot(shot_id="001", filename_base="s", prompt="p", duration=duration)
                ]
            )

            selection = SelectionSet(
                project="Test",
                selections=[
                    SelectionEntry(
                        shot_id="001", filename_base="s",
                        selected_variant=1, selected_file="s.png",
                        source_path=str(startframe), export_path=str(startframe)
                    )
                ]
            )

            # Act
            plan = builder.build(storyboard, selection)

            # Assert
            assert len(plan.segments) == expected_segments, \
                f"Duration {duration}s should create {expected_segments} segments"


class TestVideoPlanBuilderPlaceholder:
    """Test VideoPlanBuilder._placeholder_segment()"""

    @pytest.mark.unit
    def test_placeholder_segment_basic(self):
        """Should create valid placeholder segment"""
        # Arrange
        builder = VideoPlanBuilder()  # Uses defaults: 73 frames @ 24 fps ≈ 3.04s

        shot = Shot(
            shot_id="001",
            filename_base="test-shot",
            prompt="test prompt",
            width=1920,
            height=1080,
            duration=2.5
        )

        # Act
        placeholder = builder._placeholder_segment(shot, "test_status")

        # Assert
        assert placeholder.plan_id == "001"
        assert placeholder.shot_id == "001"
        assert placeholder.filename_base == "test-shot"
        assert placeholder.prompt == "test prompt"
        assert placeholder.width == 1920
        assert placeholder.height == 1080
        assert placeholder.duration == 2.5
        assert placeholder.status == "test_status"
        assert placeholder.ready is False
        assert placeholder.start_frame is None
        assert placeholder.start_frame_source == "missing"

    @pytest.mark.unit
    def test_placeholder_segment_long_shot(self):
        """Should handle segmentation for long shots in placeholder"""
        # Arrange
        builder = VideoPlanBuilder()  # Uses defaults: 73 frames @ 24 fps ≈ 3.04s

        shot = Shot(
            shot_id="001",
            filename_base="long-shot",
            prompt="test",
            duration=7.0  # Would need 3 segments
        )

        # Act
        placeholder = builder._placeholder_segment(shot, "missing")

        # Assert
        assert placeholder.segment_total == 3
        assert placeholder.needs_extension is True


class TestGenerationPlanHelpers:
    """Test GenerationPlan helper methods"""

    @pytest.mark.unit
    def test_generation_plan_for_shot(self, tmp_path):
        """Should filter segments by shot_id"""
        # Arrange
        builder = VideoPlanBuilder()  # Uses defaults: 73 frames @ 24 fps ≈ 3.04s

        startframe = tmp_path / "sf.png"
        startframe.write_text("fake")

        storyboard = Storyboard(
            project="Test",
            shots=[
                Shot(shot_id="001", filename_base="s1", prompt="p1", duration=2.0),
                Shot(shot_id="002", filename_base="s2", prompt="p2", duration=5.0),  # 2 segments
            ]
        )

        selection = SelectionSet(
            project="Test",
            selections=[
                SelectionEntry(shot_id="001", filename_base="s1", selected_variant=1,
                             selected_file="s1.png", source_path=str(startframe),
                             export_path=str(startframe)),
                SelectionEntry(shot_id="002", filename_base="s2", selected_variant=1,
                             selected_file="s2.png", source_path=str(startframe),
                             export_path=str(startframe)),
            ]
        )

        plan = builder.build(storyboard, selection)

        # Act
        shot1_segments = plan.for_shot("001")
        shot2_segments = plan.for_shot("002")

        # Assert
        assert len(shot1_segments) == 1
        assert len(shot2_segments) == 2
        assert all(seg.shot_id == "001" for seg in shot1_segments)
        assert all(seg.shot_id == "002" for seg in shot2_segments)

    @pytest.mark.unit
    def test_generation_plan_get(self, tmp_path):
        """Should retrieve segment by plan_id"""
        # Arrange
        builder = VideoPlanBuilder()  # Uses defaults: 73 frames @ 24 fps ≈ 3.04s

        startframe = tmp_path / "sf.png"
        startframe.write_text("fake")

        storyboard = Storyboard(
            project="Test",
            shots=[
                Shot(shot_id="001", filename_base="s1", prompt="p1", duration=5.0),  # Creates 001 and 001A
            ]
        )

        selection = SelectionSet(
            project="Test",
            selections=[
                SelectionEntry(shot_id="001", filename_base="s1", selected_variant=1,
                             selected_file="s1.png", source_path=str(startframe),
                             export_path=str(startframe)),
            ]
        )

        plan = builder.build(storyboard, selection)

        # Act
        seg1 = plan.get("001")
        seg2 = plan.get("001B")  # Second segment uses 'B' (idx=1)
        seg_none = plan.get("999")

        # Assert
        assert seg1 is not None
        assert seg1.plan_id == "001"
        assert seg2 is not None
        assert seg2.plan_id == "001B"
        assert seg_none is None
