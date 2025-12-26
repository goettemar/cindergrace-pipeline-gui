"""Audio Analyzer Service - Smart audio segmentation for lipsync videos."""
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from infrastructure.config_manager import ConfigManager
from infrastructure.logger import get_logger

logger = get_logger(__name__)

# Try to import librosa for advanced beat detection
try:
    import librosa
    import numpy as np
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    logger.info("librosa not available - using basic analysis only")


@dataclass
class CutPoint:
    """A potential cut point in audio."""
    time: float  # Time in seconds
    score: float  # Quality score (0-1, higher = better cut point)
    reason: str  # Why this is a good cut point

    def __repr__(self):
        return f"CutPoint({self.time:.2f}s, score={self.score:.2f}, {self.reason})"


@dataclass
class AudioSegment:
    """A segment of audio for lipsync generation."""
    index: int
    start_time: float
    end_time: float
    duration: float
    overlap_before: float = 0.0
    overlap_after: float = 0.0
    cut_reason: str = ""

    @property
    def generation_start(self) -> float:
        """Start time including overlap for generation."""
        return max(0, self.start_time - self.overlap_before)

    @property
    def generation_end(self) -> float:
        """End time including overlap for generation."""
        return self.end_time + self.overlap_after

    @property
    def generation_duration(self) -> float:
        """Total duration including overlaps."""
        return self.generation_end - self.generation_start


@dataclass
class AnalysisResult:
    """Result of audio analysis."""
    duration: float
    sample_rate: int
    cut_points: List[CutPoint] = field(default_factory=list)
    segments: List[AudioSegment] = field(default_factory=list)
    beats: List[float] = field(default_factory=list)
    silence_ranges: List[Tuple[float, float]] = field(default_factory=list)


class AudioAnalyzerService:
    """Service for analyzing audio and finding optimal cut points."""

    # Thresholds
    SILENCE_THRESHOLD_DB = -40  # dB threshold for silence
    MIN_SILENCE_DURATION = 0.1  # Minimum silence duration in seconds
    MIN_SEGMENT_DURATION = 10.0  # Minimum segment length
    MAX_SEGMENT_DURATION = 30.0  # Maximum segment length (hardware limit)
    DEFAULT_OVERLAP = 2.0  # Default overlap between segments

    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config or ConfigManager()
        self._ffmpeg_path = self._find_ffmpeg()
        self._ffprobe_path = self._ffmpeg_path.replace("ffmpeg", "ffprobe")

    def _find_ffmpeg(self) -> str:
        """Find ffmpeg executable."""
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            return ffmpeg
        for path in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"]:
            if os.path.isfile(path):
                return path
        return "ffmpeg"

    def get_audio_duration(self, audio_path: str) -> Optional[float]:
        """Get duration of audio file in seconds."""
        try:
            result = subprocess.run(
                [
                    self._ffprobe_path,
                    "-v", "quiet",
                    "-show_entries", "format=duration",
                    "-of", "json",
                    audio_path
                ],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return float(data["format"]["duration"])
        except Exception as e:
            logger.error(f"Failed to get audio duration: {e}")
        return None

    def detect_silence(self, audio_path: str) -> List[Tuple[float, float]]:
        """Detect silence ranges in audio using ffmpeg.

        Returns:
            List of (start, end) tuples for silence ranges
        """
        silence_ranges = []

        try:
            # Use ffmpeg silencedetect filter
            result = subprocess.run(
                [
                    self._ffmpeg_path,
                    "-i", audio_path,
                    "-af", f"silencedetect=noise={self.SILENCE_THRESHOLD_DB}dB:d={self.MIN_SILENCE_DURATION}",
                    "-f", "null",
                    "-"
                ],
                capture_output=True,
                text=True,
                timeout=120
            )

            # Parse output for silence ranges
            output = result.stderr
            silence_start = None

            for line in output.split("\n"):
                if "silence_start:" in line:
                    try:
                        silence_start = float(line.split("silence_start:")[1].strip().split()[0])
                    except (IndexError, ValueError):
                        pass
                elif "silence_end:" in line and silence_start is not None:
                    try:
                        parts = line.split("silence_end:")[1].strip().split()
                        silence_end = float(parts[0])
                        silence_ranges.append((silence_start, silence_end))
                        silence_start = None
                    except (IndexError, ValueError):
                        pass

            logger.info(f"Found {len(silence_ranges)} silence ranges")

        except Exception as e:
            logger.error(f"Silence detection failed: {e}")

        return silence_ranges

    def detect_beats(self, audio_path: str) -> List[float]:
        """Detect beat positions in audio.

        Uses librosa if available, otherwise returns empty list.
        """
        if not LIBROSA_AVAILABLE:
            logger.warning("Beat detection requires librosa - install with: pip install librosa")
            return []

        try:
            # Load audio
            y, sr = librosa.load(audio_path, sr=22050)

            # Detect beats
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            beat_times = librosa.frames_to_time(beat_frames, sr=sr)

            logger.info(f"Detected {len(beat_times)} beats at ~{tempo:.0f} BPM")
            return beat_times.tolist()

        except Exception as e:
            logger.error(f"Beat detection failed: {e}")
            return []

    def analyze_amplitude(self, audio_path: str, resolution: float = 0.1) -> List[Tuple[float, float]]:
        """Analyze amplitude over time using ffmpeg.

        Args:
            audio_path: Path to audio file
            resolution: Time resolution in seconds

        Returns:
            List of (time, amplitude) tuples
        """
        amplitudes = []

        try:
            # Extract amplitude data using ffmpeg
            with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
                temp_file = f.name

            # Get volume levels
            result = subprocess.run(
                [
                    self._ffmpeg_path,
                    "-i", audio_path,
                    "-af", f"astats=metadata=1:reset={int(1/resolution)},ametadata=print:key=lavfi.astats.Overall.RMS_level:file={temp_file}",
                    "-f", "null",
                    "-"
                ],
                capture_output=True,
                text=True,
                timeout=300
            )

            # Parse output
            if os.path.exists(temp_file):
                with open(temp_file, "r") as f:
                    time = 0.0
                    for line in f:
                        if "lavfi.astats.Overall.RMS_level=" in line:
                            try:
                                level = float(line.split("=")[1].strip())
                                amplitudes.append((time, level))
                                time += resolution
                            except (IndexError, ValueError):
                                pass
                os.unlink(temp_file)

            logger.info(f"Analyzed {len(amplitudes)} amplitude samples")

        except Exception as e:
            logger.error(f"Amplitude analysis failed: {e}")

        return amplitudes

    def find_cut_points(
        self,
        audio_path: str,
        target_duration: float = 25.0,
        use_beats: bool = True,
        use_silence: bool = True
    ) -> List[CutPoint]:
        """Find optimal cut points in audio.

        Args:
            audio_path: Path to audio file
            target_duration: Target segment duration
            use_beats: Use beat detection for cut points
            use_silence: Use silence detection for cut points

        Returns:
            List of CutPoint objects sorted by time
        """
        duration = self.get_audio_duration(audio_path)
        if not duration:
            return []

        cut_points = []

        # Get silence ranges
        silence_ranges = []
        if use_silence:
            silence_ranges = self.detect_silence(audio_path)

            # Add cut points at silence positions (prefer middle of silence)
            for start, end in silence_ranges:
                mid = (start + end) / 2
                silence_duration = end - start

                # Score based on silence duration (longer = better)
                score = min(1.0, silence_duration / 0.5)
                cut_points.append(CutPoint(
                    time=mid,
                    score=score,
                    reason=f"silence ({silence_duration:.2f}s)"
                ))

        # Get beats
        beats = []
        if use_beats and LIBROSA_AVAILABLE:
            beats = self.detect_beats(audio_path)

            # Add cut points at beat positions
            for beat_time in beats:
                # Check if near a silence (boost score if so)
                near_silence = any(
                    start - 0.2 <= beat_time <= end + 0.2
                    for start, end in silence_ranges
                )

                score = 0.7 if near_silence else 0.4
                cut_points.append(CutPoint(
                    time=beat_time,
                    score=score,
                    reason="beat" + (" + silence" if near_silence else "")
                ))

        # Add evenly spaced fallback points
        num_fallback = int(duration / target_duration)
        for i in range(1, num_fallback + 1):
            time = i * target_duration
            if time < duration - 5:  # Not too close to end
                cut_points.append(CutPoint(
                    time=time,
                    score=0.2,
                    reason="interval"
                ))

        # Sort by time and remove duplicates (keep highest score)
        cut_points.sort(key=lambda x: x.time)

        # Merge nearby cut points
        merged = []
        for cp in cut_points:
            if not merged or cp.time - merged[-1].time > 0.5:
                merged.append(cp)
            elif cp.score > merged[-1].score:
                merged[-1] = cp

        logger.info(f"Found {len(merged)} potential cut points")
        return merged

    def create_segments(
        self,
        audio_path: str,
        min_duration: float = None,
        max_duration: float = None,
        overlap: float = None,
        cut_points: List[CutPoint] = None
    ) -> List[AudioSegment]:
        """Create optimal segments for lipsync generation.

        Args:
            audio_path: Path to audio file
            min_duration: Minimum segment duration
            max_duration: Maximum segment duration
            overlap: Overlap between segments for crossfade
            cut_points: Pre-computed cut points (or auto-detect)

        Returns:
            List of AudioSegment objects
        """
        min_duration = min_duration or self.MIN_SEGMENT_DURATION
        max_duration = max_duration or self.MAX_SEGMENT_DURATION
        overlap = overlap if overlap is not None else self.DEFAULT_OVERLAP

        duration = self.get_audio_duration(audio_path)
        if not duration:
            return []

        # Get cut points if not provided
        if cut_points is None:
            cut_points = self.find_cut_points(audio_path, target_duration=max_duration - overlap)

        segments = []
        current_start = 0.0
        segment_index = 0

        while current_start < duration - min_duration / 2:
            # Find best cut point in valid range
            target_end = current_start + max_duration - overlap
            min_end = current_start + min_duration

            # Filter cut points in valid range
            valid_cuts = [
                cp for cp in cut_points
                if min_end <= cp.time <= target_end
            ]

            if valid_cuts:
                # Pick highest scoring cut point
                best_cut = max(valid_cuts, key=lambda x: x.score)
                end_time = best_cut.time
                cut_reason = best_cut.reason
            else:
                # No good cut point - use max duration
                end_time = min(current_start + max_duration - overlap, duration)
                cut_reason = "max_duration"

            # Create segment
            segment = AudioSegment(
                index=segment_index,
                start_time=current_start,
                end_time=end_time,
                duration=end_time - current_start,
                overlap_before=overlap if segment_index > 0 else 0,
                overlap_after=overlap if end_time < duration - 1 else 0,
                cut_reason=cut_reason
            )
            segments.append(segment)

            # Move to next segment (with overlap)
            current_start = end_time - overlap
            segment_index += 1

            # Safety check
            if segment_index > 100:
                logger.warning("Too many segments - stopping")
                break

        logger.info(f"Created {len(segments)} segments for {duration:.1f}s audio")
        return segments

    def analyze(
        self,
        audio_path: str,
        target_segment_duration: float = 25.0,
        overlap: float = 2.0
    ) -> AnalysisResult:
        """Full audio analysis with cut points and segments.

        Args:
            audio_path: Path to audio file
            target_segment_duration: Target duration per segment
            overlap: Overlap between segments

        Returns:
            AnalysisResult with all analysis data
        """
        duration = self.get_audio_duration(audio_path)
        if not duration:
            raise ValueError(f"Could not read audio file: {audio_path}")

        # Detect silence
        silence_ranges = self.detect_silence(audio_path)

        # Detect beats (if librosa available)
        beats = self.detect_beats(audio_path) if LIBROSA_AVAILABLE else []

        # Find cut points
        cut_points = self.find_cut_points(
            audio_path,
            target_duration=target_segment_duration,
            use_beats=LIBROSA_AVAILABLE,
            use_silence=True
        )

        # Create segments
        segments = self.create_segments(
            audio_path,
            max_duration=target_segment_duration + overlap,
            overlap=overlap,
            cut_points=cut_points
        )

        return AnalysisResult(
            duration=duration,
            sample_rate=44100,  # Assumed
            cut_points=cut_points,
            segments=segments,
            beats=beats,
            silence_ranges=silence_ranges
        )

    def export_segments(
        self,
        audio_path: str,
        segments: List[AudioSegment],
        output_dir: str,
        format: str = "wav"
    ) -> List[str]:
        """Export audio segments to separate files.

        Args:
            audio_path: Source audio file
            segments: List of segments to export
            output_dir: Output directory
            format: Output format (wav, mp3)

        Returns:
            List of output file paths
        """
        os.makedirs(output_dir, exist_ok=True)
        output_files = []

        base_name = Path(audio_path).stem

        for segment in segments:
            output_path = os.path.join(
                output_dir,
                f"{base_name}_seg{segment.index:03d}.{format}"
            )

            # Include overlap in export
            start = segment.generation_start
            duration = segment.generation_duration

            try:
                result = subprocess.run(
                    [
                        self._ffmpeg_path,
                        "-y",
                        "-i", audio_path,
                        "-ss", str(start),
                        "-t", str(duration),
                        "-acodec", "pcm_s16le" if format == "wav" else "libmp3lame",
                        output_path
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                if result.returncode == 0:
                    output_files.append(output_path)
                    logger.info(f"Exported segment {segment.index}: {output_path}")
                else:
                    logger.error(f"Failed to export segment {segment.index}: {result.stderr}")

            except Exception as e:
                logger.error(f"Failed to export segment {segment.index}: {e}")

        return output_files

    def format_segments_table(self, segments: List[AudioSegment]) -> List[List[str]]:
        """Format segments for Gradio dataframe display.

        Returns:
            List of rows for dataframe
        """
        rows = []
        for seg in segments:
            rows.append([
                f"{seg.index + 1}",
                f"{seg.start_time:.1f}s",
                f"{seg.end_time:.1f}s",
                f"{seg.duration:.1f}s",
                f"{seg.generation_duration:.1f}s",
                seg.cut_reason
            ])
        return rows


__all__ = [
    "AudioAnalyzerService",
    "CutPoint",
    "AudioSegment",
    "AnalysisResult",
    "LIBROSA_AVAILABLE",
]
