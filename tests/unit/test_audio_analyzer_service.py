"""Tests for AudioAnalyzerService."""
import os
import json
import subprocess
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from services.audio_analyzer_service import (
    AudioAnalyzerService,
    CutPoint,
    AudioSegment,
    AnalysisResult,
    LIBROSA_AVAILABLE
)


class TestCutPoint:
    """Tests for CutPoint dataclass."""

    def test_cut_point_creation(self):
        """Test creating a CutPoint."""
        cp = CutPoint(time=10.5, score=0.8, reason="silence")
        assert cp.time == 10.5
        assert cp.score == 0.8
        assert cp.reason == "silence"

    def test_cut_point_repr(self):
        """Test CutPoint string representation."""
        cp = CutPoint(time=10.5, score=0.8, reason="silence")
        repr_str = repr(cp)
        assert "10.50s" in repr_str
        assert "0.80" in repr_str
        assert "silence" in repr_str


class TestAudioSegment:
    """Tests for AudioSegment dataclass."""

    def test_audio_segment_creation(self):
        """Test creating an AudioSegment."""
        seg = AudioSegment(
            index=0,
            start_time=0.0,
            end_time=25.0,
            duration=25.0
        )
        assert seg.index == 0
        assert seg.start_time == 0.0
        assert seg.end_time == 25.0
        assert seg.duration == 25.0

    def test_audio_segment_default_overlaps(self):
        """Test default overlap values."""
        seg = AudioSegment(
            index=0,
            start_time=0.0,
            end_time=25.0,
            duration=25.0
        )
        assert seg.overlap_before == 0.0
        assert seg.overlap_after == 0.0
        assert seg.cut_reason == ""

    def test_generation_start(self):
        """Test generation_start property."""
        seg = AudioSegment(
            index=1,
            start_time=25.0,
            end_time=50.0,
            duration=25.0,
            overlap_before=2.0
        )
        assert seg.generation_start == 23.0

    def test_generation_start_clamped_to_zero(self):
        """Test generation_start doesn't go below zero."""
        seg = AudioSegment(
            index=0,
            start_time=0.0,
            end_time=25.0,
            duration=25.0,
            overlap_before=5.0
        )
        assert seg.generation_start == 0.0

    def test_generation_end(self):
        """Test generation_end property."""
        seg = AudioSegment(
            index=0,
            start_time=0.0,
            end_time=25.0,
            duration=25.0,
            overlap_after=2.0
        )
        assert seg.generation_end == 27.0

    def test_generation_duration(self):
        """Test generation_duration property."""
        seg = AudioSegment(
            index=1,
            start_time=25.0,
            end_time=50.0,
            duration=25.0,
            overlap_before=2.0,
            overlap_after=2.0
        )
        # generation_end (52.0) - generation_start (23.0) = 29.0
        assert seg.generation_duration == 29.0


class TestAnalysisResult:
    """Tests for AnalysisResult dataclass."""

    def test_analysis_result_creation(self):
        """Test creating an AnalysisResult."""
        result = AnalysisResult(
            duration=120.0,
            sample_rate=44100
        )
        assert result.duration == 120.0
        assert result.sample_rate == 44100
        assert result.cut_points == []
        assert result.segments == []
        assert result.beats == []
        assert result.silence_ranges == []


class TestAudioAnalyzerService:
    """Tests for AudioAnalyzerService class."""

    @pytest.fixture
    def mock_config(self):
        """Create mock ConfigManager."""
        return Mock()

    @pytest.fixture
    def service(self, mock_config):
        """Create AudioAnalyzerService instance."""
        with patch('shutil.which', return_value='/usr/bin/ffmpeg'):
            return AudioAnalyzerService(config=mock_config)

    # ========================================================================
    # Initialization Tests
    # ========================================================================

    def test_init_finds_ffmpeg(self, mock_config):
        """Test that ffmpeg is found during init."""
        with patch('shutil.which', return_value='/usr/bin/ffmpeg'):
            service = AudioAnalyzerService(config=mock_config)
            assert service._ffmpeg_path == '/usr/bin/ffmpeg'

    def test_init_ffprobe_path(self, mock_config):
        """Test that ffprobe path is derived from ffmpeg."""
        with patch('shutil.which', return_value='/usr/bin/ffmpeg'):
            service = AudioAnalyzerService(config=mock_config)
            assert service._ffprobe_path == '/usr/bin/ffprobe'

    def test_init_fallback_ffmpeg_path(self, mock_config):
        """Test fallback when ffmpeg not in PATH."""
        with patch('shutil.which', return_value=None):
            with patch('os.path.isfile', return_value=False):
                service = AudioAnalyzerService(config=mock_config)
                assert service._ffmpeg_path == 'ffmpeg'

    def test_default_thresholds(self, service):
        """Test default threshold values."""
        assert service.SILENCE_THRESHOLD_DB == -40
        assert service.MIN_SILENCE_DURATION == 0.1
        assert service.MIN_SEGMENT_DURATION == 10.0
        assert service.MAX_SEGMENT_DURATION == 30.0
        assert service.DEFAULT_OVERLAP == 2.0

    # ========================================================================
    # Get Audio Duration Tests
    # ========================================================================

    def test_get_audio_duration_success(self, service):
        """Test getting audio duration successfully."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "format": {"duration": "120.5"}
        })

        with patch('subprocess.run', return_value=mock_result):
            duration = service.get_audio_duration("/path/to/audio.mp3")
            assert duration == 120.5

    def test_get_audio_duration_failure(self, service):
        """Test getting audio duration when ffprobe fails."""
        mock_result = Mock()
        mock_result.returncode = 1

        with patch('subprocess.run', return_value=mock_result):
            duration = service.get_audio_duration("/path/to/audio.mp3")
            assert duration is None

    def test_get_audio_duration_exception(self, service):
        """Test getting audio duration with exception."""
        with patch('subprocess.run', side_effect=Exception("error")):
            duration = service.get_audio_duration("/path/to/audio.mp3")
            assert duration is None

    # ========================================================================
    # Detect Silence Tests
    # ========================================================================

    def test_detect_silence_parses_output(self, service):
        """Test silence detection parses ffmpeg output."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = """
        [silencedetect @ 0x1234] silence_start: 5.5
        [silencedetect @ 0x1234] silence_end: 6.2 | silence_duration: 0.7
        [silencedetect @ 0x1234] silence_start: 15.0
        [silencedetect @ 0x1234] silence_end: 15.8 | silence_duration: 0.8
        """

        with patch('subprocess.run', return_value=mock_result):
            ranges = service.detect_silence("/path/to/audio.mp3")

            assert len(ranges) == 2
            assert ranges[0] == (5.5, 6.2)
            assert ranges[1] == (15.0, 15.8)

    def test_detect_silence_empty_output(self, service):
        """Test silence detection with no silence found."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = "No silence detected"

        with patch('subprocess.run', return_value=mock_result):
            ranges = service.detect_silence("/path/to/audio.mp3")
            assert ranges == []

    def test_detect_silence_exception(self, service):
        """Test silence detection with exception."""
        with patch('subprocess.run', side_effect=Exception("error")):
            ranges = service.detect_silence("/path/to/audio.mp3")
            assert ranges == []

    # ========================================================================
    # Detect Beats Tests
    # ========================================================================

    @pytest.mark.skipif(not LIBROSA_AVAILABLE, reason="librosa not installed")
    def test_detect_beats_without_librosa(self, service):
        """Test beat detection returns empty when librosa unavailable."""
        with patch.dict('services.audio_analyzer_service.__dict__', {'LIBROSA_AVAILABLE': False}):
            beats = service.detect_beats("/path/to/audio.mp3")
            # When librosa is not available, should return empty list
            assert isinstance(beats, list)

    # ========================================================================
    # Find Cut Points Tests
    # ========================================================================

    def test_find_cut_points_no_duration(self, service):
        """Test find_cut_points returns empty when no duration."""
        with patch.object(service, 'get_audio_duration', return_value=None):
            points = service.find_cut_points("/path/to/audio.mp3")
            assert points == []

    def test_find_cut_points_includes_silence(self, service):
        """Test find_cut_points includes silence-based cut points."""
        with patch.object(service, 'get_audio_duration', return_value=120.0):
            with patch.object(service, 'detect_silence', return_value=[(10.0, 10.5), (50.0, 51.0)]):
                with patch.object(service, 'detect_beats', return_value=[]):
                    points = service.find_cut_points("/path/to/audio.mp3")

                    silence_points = [p for p in points if "silence" in p.reason]
                    assert len(silence_points) >= 2

    def test_find_cut_points_includes_fallback(self, service):
        """Test find_cut_points includes interval-based fallback points."""
        with patch.object(service, 'get_audio_duration', return_value=120.0):
            with patch.object(service, 'detect_silence', return_value=[]):
                with patch.object(service, 'detect_beats', return_value=[]):
                    points = service.find_cut_points(
                        "/path/to/audio.mp3",
                        target_duration=25.0
                    )

                    interval_points = [p for p in points if p.reason == "interval"]
                    assert len(interval_points) > 0

    def test_find_cut_points_sorted_by_time(self, service):
        """Test that cut points are sorted by time."""
        with patch.object(service, 'get_audio_duration', return_value=120.0):
            with patch.object(service, 'detect_silence', return_value=[(50.0, 51.0), (10.0, 10.5)]):
                with patch.object(service, 'detect_beats', return_value=[]):
                    points = service.find_cut_points("/path/to/audio.mp3")

                    times = [p.time for p in points]
                    assert times == sorted(times)

    def test_find_cut_points_merges_nearby(self, service):
        """Test that nearby cut points are merged."""
        with patch.object(service, 'get_audio_duration', return_value=120.0):
            # Two silence ranges very close together
            with patch.object(service, 'detect_silence', return_value=[(10.0, 10.2), (10.3, 10.5)]):
                with patch.object(service, 'detect_beats', return_value=[]):
                    points = service.find_cut_points("/path/to/audio.mp3")

                    # Should merge into one (within 0.5s)
                    nearby = [p for p in points if 9.5 < p.time < 11.0]
                    assert len(nearby) == 1

    # ========================================================================
    # Create Segments Tests
    # ========================================================================

    def test_create_segments_no_duration(self, service):
        """Test create_segments returns empty when no duration."""
        with patch.object(service, 'get_audio_duration', return_value=None):
            segments = service.create_segments("/path/to/audio.mp3")
            assert segments == []

    def test_create_segments_basic(self, service):
        """Test basic segment creation."""
        with patch.object(service, 'get_audio_duration', return_value=60.0):
            with patch.object(service, 'find_cut_points', return_value=[]):
                segments = service.create_segments(
                    "/path/to/audio.mp3",
                    min_duration=10.0,
                    max_duration=30.0,
                    overlap=2.0
                )

                assert len(segments) >= 1
                for seg in segments:
                    assert isinstance(seg, AudioSegment)

    def test_create_segments_respects_max_duration(self, service):
        """Test that segments don't exceed max duration."""
        with patch.object(service, 'get_audio_duration', return_value=120.0):
            with patch.object(service, 'find_cut_points', return_value=[]):
                segments = service.create_segments(
                    "/path/to/audio.mp3",
                    max_duration=30.0,
                    overlap=2.0
                )

                for seg in segments:
                    assert seg.duration <= 30.0

    def test_create_segments_uses_cut_points(self, service):
        """Test that segments use provided cut points."""
        cut_points = [
            CutPoint(time=25.0, score=0.9, reason="silence"),
            CutPoint(time=50.0, score=0.8, reason="silence"),
        ]

        with patch.object(service, 'get_audio_duration', return_value=75.0):
            segments = service.create_segments(
                "/path/to/audio.mp3",
                cut_points=cut_points,
                min_duration=10.0,
                max_duration=30.0,
                overlap=2.0
            )

            # Should have cuts near the cut points
            end_times = [seg.end_time for seg in segments]
            assert any(abs(t - 25.0) < 1.0 for t in end_times)

    def test_create_segments_first_has_no_overlap_before(self, service):
        """Test that first segment has no overlap_before."""
        with patch.object(service, 'get_audio_duration', return_value=60.0):
            with patch.object(service, 'find_cut_points', return_value=[]):
                segments = service.create_segments(
                    "/path/to/audio.mp3",
                    overlap=2.0
                )

                assert segments[0].overlap_before == 0.0

    def test_create_segments_middle_has_overlap(self, service):
        """Test that middle segments have overlap."""
        with patch.object(service, 'get_audio_duration', return_value=90.0):
            with patch.object(service, 'find_cut_points', return_value=[]):
                segments = service.create_segments(
                    "/path/to/audio.mp3",
                    max_duration=30.0,
                    overlap=2.0
                )

                if len(segments) > 1:
                    assert segments[1].overlap_before == 2.0

    # ========================================================================
    # Full Analysis Tests
    # ========================================================================

    def test_analyze_raises_on_invalid_file(self, service):
        """Test analyze raises ValueError for invalid file."""
        with patch.object(service, 'get_audio_duration', return_value=None):
            with pytest.raises(ValueError):
                service.analyze("/path/to/invalid.mp3")

    def test_analyze_returns_analysis_result(self, service):
        """Test analyze returns AnalysisResult."""
        with patch.object(service, 'get_audio_duration', return_value=60.0):
            with patch.object(service, 'detect_silence', return_value=[]):
                with patch.object(service, 'detect_beats', return_value=[]):
                    with patch.object(service, 'find_cut_points', return_value=[]):
                        with patch.object(service, 'create_segments', return_value=[]):
                            result = service.analyze("/path/to/audio.mp3")

                            assert isinstance(result, AnalysisResult)
                            assert result.duration == 60.0

    # ========================================================================
    # Export Segments Tests
    # ========================================================================

    def test_export_segments_creates_directory(self, service, tmp_path):
        """Test export_segments creates output directory."""
        output_dir = tmp_path / "segments"
        segments = [
            AudioSegment(index=0, start_time=0, end_time=25, duration=25)
        ]

        mock_result = Mock()
        mock_result.returncode = 0

        with patch('subprocess.run', return_value=mock_result):
            service.export_segments(
                "/path/to/audio.mp3",
                segments,
                str(output_dir)
            )

        assert output_dir.exists()

    def test_export_segments_returns_paths(self, service, tmp_path):
        """Test export_segments returns output paths."""
        output_dir = tmp_path / "segments"
        segments = [
            AudioSegment(index=0, start_time=0, end_time=25, duration=25),
            AudioSegment(index=1, start_time=23, end_time=48, duration=25),
        ]

        mock_result = Mock()
        mock_result.returncode = 0

        with patch('subprocess.run', return_value=mock_result):
            paths = service.export_segments(
                "/path/to/audio.mp3",
                segments,
                str(output_dir)
            )

            assert len(paths) == 2

    def test_export_segments_handles_failure(self, service, tmp_path):
        """Test export_segments handles ffmpeg failure."""
        output_dir = tmp_path / "segments"
        segments = [
            AudioSegment(index=0, start_time=0, end_time=25, duration=25)
        ]

        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "error"

        with patch('subprocess.run', return_value=mock_result):
            paths = service.export_segments(
                "/path/to/audio.mp3",
                segments,
                str(output_dir)
            )

            assert paths == []

    # ========================================================================
    # Format Segments Table Tests
    # ========================================================================

    def test_format_segments_table(self, service):
        """Test format_segments_table output."""
        segments = [
            AudioSegment(
                index=0,
                start_time=0.0,
                end_time=25.0,
                duration=25.0,
                overlap_before=0.0,
                overlap_after=2.0,
                cut_reason="silence"
            )
        ]

        rows = service.format_segments_table(segments)

        assert len(rows) == 1
        row = rows[0]
        assert row[0] == "1"  # 1-indexed
        assert "0.0s" in row[1]
        assert "25.0s" in row[2]
        assert "25.0s" in row[3]
        assert "silence" in row[5]

    def test_format_segments_table_multiple(self, service):
        """Test format_segments_table with multiple segments."""
        segments = [
            AudioSegment(index=0, start_time=0, end_time=25, duration=25),
            AudioSegment(index=1, start_time=23, end_time=48, duration=25),
            AudioSegment(index=2, start_time=46, end_time=60, duration=14),
        ]

        rows = service.format_segments_table(segments)

        assert len(rows) == 3
        assert rows[0][0] == "1"
        assert rows[1][0] == "2"
        assert rows[2][0] == "3"
