"""Lipsync Addon - Generate lip-synced videos from audio and character images."""
import os
import tempfile
from typing import List, Optional, Tuple

import gradio as gr

from addons.base_addon import BaseAddon
from addons.components import format_project_status
from infrastructure.config_manager import ConfigManager
from infrastructure.logger import get_logger
from infrastructure.workflow_registry import WorkflowRegistry, PREFIX_LIPSYNC
from services.lipsync_service import (
    LipsyncService,
    LipsyncJob,
    BatchSegment,
    BatchResult,
    RESOLUTION_PRESETS,
)
from infrastructure.workflow_registry import PREFIX_KEYFRAME
from services.character_lora_service import CharacterLoraService
from services.audio_analyzer_service import (
    AudioAnalyzerService,
    AudioSegment,
    LIBROSA_AVAILABLE,
)

logger = get_logger(__name__)


# Resolution choices for dropdown
RESOLUTION_CHOICES = [
    ("480p (832×480)", "480p"),
    ("720p (1280×720)", "720p"),
    ("1080p (1920×1080)", "1080p"),
    ("480p Portrait (480×832)", "480p_portrait"),
    ("720p Portrait (720×1280)", "720p_portrait"),
    ("640×640 Square", "640x640"),
]

# Default prompts
DEFAULT_PROMPT = "Person singing emotionally, looking at camera, natural lip movements, expressive face"
DEFAULT_NEGATIVE = (
    "blurry, low quality, static, deformed face, wrong lip sync, "
    "unnatural movements, distorted audio, glitchy"
)


class LipsyncAddon(BaseAddon):
    """Addon for generating lip-synced videos using Wan 2.2 is2v."""

    def __init__(self):
        super().__init__(
            name="Lipsync Studio",
            description="Generate lip-synced videos from audio and character images",
            category="production"
        )
        self.config = ConfigManager()
        self.lipsync_service = LipsyncService(self.config)
        self.character_lora_service = CharacterLoraService(self.config)
        self.workflow_registry = WorkflowRegistry()
        self.audio_analyzer = AudioAnalyzerService(self.config)

        # State
        self._current_image_path: Optional[str] = None
        self._current_audio_path: Optional[str] = None
        self._trimmed_audio_path: Optional[str] = None
        self._segments: List[AudioSegment] = []
        self._exported_segments: List[str] = []

    def _get_available_workflows(self) -> list:
        """Get list of available lipsync workflows for dropdown."""
        return self.workflow_registry.get_dropdown_choices(PREFIX_LIPSYNC)

    def _get_default_workflow(self) -> Optional[str]:
        """Get default lipsync workflow."""
        return self.workflow_registry.get_default(PREFIX_LIPSYNC)

    def get_tab_name(self) -> str:
        return "🎤 Lipsync"

    def render(self) -> gr.Blocks:
        with gr.Blocks() as interface:
            # Unified header: Tab name left, no project relation
            gr.HTML(format_project_status(tab_name="🎤 Lipsync Studio", no_project_relation=True))

            gr.Markdown(
                "Create lip-synced videos from audio and character images. "
                "Uses Wan 2.2 Sound-to-Video for realistic mouth movements."
            )

            # Status bar
            status_md = gr.Markdown("**Status:** Ready")

            with gr.Tabs():
                # ==================== Tab 1: Character Image ====================
                with gr.Tab("🖼️ Character Image"):
                    self._render_image_tab()

                # ==================== Tab 2: Audio ====================
                with gr.Tab("🎵 Audio"):
                    self._render_audio_tab()

                # ==================== Tab 3: Segmentation (for long audio) ====================
                with gr.Tab("✂️ Segmentation"):
                    self._render_segmentation_tab()

                # ==================== Tab 4: Generation ====================
                with gr.Tab("🎬 Generation"):
                    self._render_generation_tab()

            # Store references for event handlers
            self.status_md = status_md

        return interface

    def _render_image_tab(self):
        """Render the character image selection tab."""
        gr.Markdown("## 🖼️ Select Character Image")
        gr.Markdown(
            "Upload an image of your character or generate one with Flux. "
            "The image should clearly show the face (frontal view preferred)."
        )

        with gr.Row():
            with gr.Column(scale=1):
                with gr.Group():
                    gr.Markdown("### Option A: Upload Image")
                    image_upload = gr.Image(
                        label="Character Image",
                        type="filepath",
                        sources=["upload"],
                        height=300
                    )

                with gr.Group():
                    gr.Markdown("### Option B: Generate with Flux")

                    # Flux workflow dropdown
                    flux_workflow_dropdown = gr.Dropdown(
                        label="Flux Workflow",
                        choices=self._get_flux_workflows(),
                        value=self._get_default_flux_workflow(),
                        interactive=True
                    )

                    # Character LoRA dropdown
                    character_dropdown = gr.Dropdown(
                        label="Character LoRA (optional)",
                        choices=self._get_character_choices(),
                        value=None,
                        interactive=True
                    )
                    refresh_chars_btn = gr.Button("🔄 Refresh LoRAs", size="sm")

                    flux_prompt = gr.Textbox(
                        label="Flux Prompt",
                        placeholder="Portrait of [character], looking at camera, neutral expression, frontal view",
                        value="Portrait photo, looking at camera, neutral expression, frontal view, studio lighting",
                        lines=2,
                        interactive=True
                    )
                    flux_negative = gr.Textbox(
                        label="Negative Prompt",
                        value="blurry, low quality, deformed, ugly, distorted",
                        lines=1,
                        interactive=True
                    )
                    with gr.Row():
                        flux_width = gr.Number(label="Width", value=768, precision=0)
                        flux_height = gr.Number(label="Height", value=1024, precision=0)
                    generate_flux_btn = gr.Button(
                        "🎨 Generate with Flux",
                        variant="primary",
                        interactive=True
                    )
                    flux_status = gr.Markdown("")

            with gr.Column(scale=1):
                gr.Markdown("### Preview")
                image_preview = gr.Image(
                    label="Current Image",
                    type="filepath",
                    interactive=False,
                    height=400
                )
                image_status = gr.Markdown("*No image loaded*")

        # Event handlers
        def on_image_upload(image_path):
            if image_path:
                self._current_image_path = image_path
                return (
                    image_path,
                    f"**Image loaded:** {os.path.basename(image_path)}"
                )
            return None, "*No image loaded*"

        def refresh_characters():
            choices = self._get_character_choices()
            return gr.update(choices=choices)

        def on_generate_flux(workflow, prompt_text, neg_prompt, width, height, lora_name):
            """Generate character image with Flux."""
            if not workflow:
                yield None, "*No workflow selected*", "❌ Select a workflow"
                return

            yield None, "*Generating...*", "⏳ Generating image with Flux..."

            success, result = self.lipsync_service.generate_character_image(
                prompt=prompt_text,
                negative_prompt=neg_prompt,
                width=int(width),
                height=int(height),
                workflow_file=workflow,
                lora_name=lora_name if lora_name else None,
                progress_callback=None
            )

            if success:
                self._current_image_path = result
                yield (
                    result,
                    f"**Generated:** {os.path.basename(result)}",
                    "✅ Image generated!"
                )
            else:
                yield None, "*Generation failed*", f"❌ {result}"

        image_upload.change(
            fn=on_image_upload,
            inputs=[image_upload],
            outputs=[image_preview, image_status]
        )

        refresh_chars_btn.click(
            fn=refresh_characters,
            inputs=[],
            outputs=[character_dropdown]
        )

        generate_flux_btn.click(
            fn=on_generate_flux,
            inputs=[flux_workflow_dropdown, flux_prompt, flux_negative, flux_width, flux_height, character_dropdown],
            outputs=[image_preview, image_status, flux_status]
        )

    def _render_audio_tab(self):
        """Render the audio processing tab."""
        gr.Markdown("## 🎵 Prepare Audio")
        gr.Markdown(
            "Upload an audio file and trim it to the desired length. "
            f"**Max. duration: ~{self.lipsync_service.MAX_DURATION_SECONDS:.0f} seconds** "
            "(hardware-dependent, possibly only ~10s)."
        )

        with gr.Row():
            with gr.Column(scale=1):
                with gr.Group():
                    gr.Markdown("### Upload Audio")
                    audio_upload = gr.Audio(
                        label="Audio File (MP3/WAV)",
                        type="filepath",
                        sources=["upload"]
                    )
                    audio_info = gr.Markdown("*No audio file loaded*")

                with gr.Group():
                    gr.Markdown("### Trim")
                    with gr.Row():
                        trim_start = gr.Number(
                            label="Start (seconds)",
                            value=0.0,
                            minimum=0.0,
                            precision=1
                        )
                        trim_end = gr.Number(
                            label="End (seconds)",
                            value=10.0,
                            minimum=0.1,
                            precision=1
                        )
                    trim_btn = gr.Button("✂️ Trim Audio", variant="primary")
                    trim_status = gr.Markdown("")

            with gr.Column(scale=1):
                gr.Markdown("### Preview")
                audio_preview = gr.Audio(
                    label="Trimmed Audio",
                    type="filepath",
                    interactive=False
                )
                duration_info = gr.Markdown("*No trimmed audio*")

        # Event handlers
        def on_audio_upload(audio_path):
            if not audio_path:
                return "*No audio file loaded*", 0.0, 10.0

            self._current_audio_path = audio_path
            info = self.lipsync_service.get_audio_info(audio_path)

            if info:
                duration = info.duration
                info_text = (
                    f"**File:** {os.path.basename(audio_path)}\n\n"
                    f"**Duration:** {duration:.1f}s | "
                    f"**Format:** {info.format.upper()} | "
                    f"**Sample Rate:** {info.sample_rate}Hz"
                )
                # Set trim end to min(duration, max_duration)
                end_val = min(duration, self.lipsync_service.MAX_DURATION_SECONDS)
                return info_text, 0.0, end_val
            else:
                return f"**File:** {os.path.basename(audio_path)}\n\n*Info not available*", 0.0, 10.0

        def on_trim_audio(audio_path, start, end):
            if not audio_path:
                return None, "", "*Please upload audio first*"

            # Create temp file for trimmed audio
            temp_dir = tempfile.gettempdir()
            output_path = os.path.join(temp_dir, "lipsync_trimmed.wav")

            success, message = self.lipsync_service.trim_audio(
                input_path=audio_path,
                output_path=output_path,
                start_time=start,
                end_time=end,
                max_duration=self.lipsync_service.MAX_DURATION_SECONDS
            )

            if success:
                self._trimmed_audio_path = output_path
                duration = end - start
                if duration > self.lipsync_service.MAX_DURATION_SECONDS:
                    duration = self.lipsync_service.MAX_DURATION_SECONDS
                duration_text = f"**Duration:** {duration:.1f}s (ready for generation)"
                return output_path, "✅ Audio trimmed!", duration_text
            else:
                return None, f"❌ {message}", "*Error trimming audio*"

        audio_upload.change(
            fn=on_audio_upload,
            inputs=[audio_upload],
            outputs=[audio_info, trim_start, trim_end]
        )

        trim_btn.click(
            fn=on_trim_audio,
            inputs=[audio_upload, trim_start, trim_end],
            outputs=[audio_preview, trim_status, duration_info]
        )

    def _render_segmentation_tab(self):
        """Render the segmentation tab for long audio files."""
        gr.Markdown("## ✂️ Smart Audio Segmentation")
        gr.Markdown(
            "Analyze long audio files and automatically find optimal cut points. "
            "Use this for songs or audio longer than 14 seconds."
        )

        # Feature info
        librosa_status = "✅ Beat detection available" if LIBROSA_AVAILABLE else "⚠️ Beat detection unavailable (install librosa)"
        gr.Markdown(f"**Features:** Silence detection, {librosa_status}")

        with gr.Row():
            with gr.Column(scale=1):
                with gr.Group():
                    gr.Markdown("### Audio Source")
                    audio_for_analysis = gr.Audio(
                        label="Audio File (MP3/WAV)",
                        type="filepath",
                        sources=["upload"]
                    )
                    audio_duration_info = gr.Markdown("*Upload an audio file*")

                with gr.Group():
                    gr.Markdown("### Segmentation Settings")

                    target_duration = gr.Slider(
                        label="Target Segment Duration (seconds)",
                        minimum=10,
                        maximum=30,
                        value=25,
                        step=1,
                        info="Aim for segments around this length"
                    )

                    overlap_duration = gr.Slider(
                        label="Overlap Duration (seconds)",
                        minimum=0,
                        maximum=5,
                        value=2,
                        step=0.5,
                        info="Overlap for crossfade between segments"
                    )

                    with gr.Row():
                        analyze_btn = gr.Button("🔍 Analyze Audio", variant="primary")
                        export_btn = gr.Button("💾 Export Segments", variant="secondary")

                    analysis_status = gr.Markdown("")

            with gr.Column(scale=1):
                gr.Markdown("### Analysis Results")

                with gr.Accordion("📊 Cut Points", open=False):
                    cut_points_info = gr.Markdown("*Run analysis first*")

                gr.Markdown("### Segments")
                segments_table = gr.Dataframe(
                    headers=["#", "Start", "End", "Duration", "Gen. Duration", "Cut Reason"],
                    datatype=["str", "str", "str", "str", "str", "str"],
                    label="Segments for Generation",
                    interactive=False,
                    wrap=True
                )

                segments_summary = gr.Markdown("")

        # Event handlers
        def on_audio_for_analysis(audio_path):
            if not audio_path:
                return "*Upload an audio file*"

            duration = self.audio_analyzer.get_audio_duration(audio_path)
            if duration:
                minutes = int(duration // 60)
                seconds = duration % 60
                return f"**Duration:** {minutes}:{seconds:05.2f} ({duration:.1f}s total)"
            return "*Could not read audio info*"

        def on_analyze(audio_path, target_dur, overlap_dur):
            if not audio_path:
                return "❌ Please upload an audio file first", "*Run analysis first*", [], ""

            try:
                # Run analysis
                result = self.audio_analyzer.analyze(
                    audio_path,
                    target_segment_duration=target_dur,
                    overlap=overlap_dur
                )

                # Store segments
                self._segments = result.segments

                # Format cut points info
                cut_info_lines = [f"**Found {len(result.cut_points)} potential cut points:**\n"]
                for i, cp in enumerate(result.cut_points[:20]):  # Show first 20
                    cut_info_lines.append(f"- {cp.time:.1f}s: {cp.reason} (score: {cp.score:.2f})")
                if len(result.cut_points) > 20:
                    cut_info_lines.append(f"\n*...and {len(result.cut_points) - 20} more*")

                if result.beats:
                    cut_info_lines.insert(1, f"\n**Detected ~{len(result.beats)} beats**\n")
                if result.silence_ranges:
                    cut_info_lines.insert(1, f"**Found {len(result.silence_ranges)} silence ranges**\n")

                cut_info = "\n".join(cut_info_lines)

                # Format segments table
                table_data = self.audio_analyzer.format_segments_table(result.segments)

                # Summary
                total_gen_time = sum(s.generation_duration for s in result.segments)
                summary = (
                    f"**{len(result.segments)} Segments** | "
                    f"Audio: {result.duration:.1f}s | "
                    f"Total generation time: {total_gen_time:.1f}s"
                )

                return (
                    f"✅ Analysis complete! Found {len(result.segments)} optimal segments.",
                    cut_info,
                    table_data,
                    summary
                )

            except Exception as e:
                logger.error(f"Analysis failed: {e}")
                return f"❌ Analysis failed: {e}", "*Error*", [], ""

        def on_export(audio_path):
            if not audio_path:
                return "❌ No audio file loaded"

            if not self._segments:
                return "❌ Run analysis first"

            try:
                # Export to temp directory
                output_dir = tempfile.mkdtemp(prefix="lipsync_segments_")

                files = self.audio_analyzer.export_segments(
                    audio_path,
                    self._segments,
                    output_dir,
                    format="wav"
                )

                self._exported_segments = files

                return (
                    f"✅ Exported {len(files)} segments to:\n`{output_dir}`\n\n"
                    "Use these files in the Generation tab for batch processing."
                )

            except Exception as e:
                logger.error(f"Export failed: {e}")
                return f"❌ Export failed: {e}"

        audio_for_analysis.change(
            fn=on_audio_for_analysis,
            inputs=[audio_for_analysis],
            outputs=[audio_duration_info]
        )

        analyze_btn.click(
            fn=on_analyze,
            inputs=[audio_for_analysis, target_duration, overlap_duration],
            outputs=[analysis_status, cut_points_info, segments_table, segments_summary]
        )

        export_btn.click(
            fn=on_export,
            inputs=[audio_for_analysis],
            outputs=[analysis_status]
        )

    def _render_generation_tab(self):
        """Render the generation tab."""
        gr.Markdown("## 🎬 Generate Lipsync Video")
        gr.Markdown(
            "Combine image and audio into a lip-synced video. "
            "The prompt describes the desired movement/emotion."
        )

        with gr.Row():
            with gr.Column(scale=1):
                with gr.Group():
                    gr.Markdown("### Workflow")

                    with gr.Row():
                        workflow_dropdown = gr.Dropdown(
                            label="Lipsync Workflow",
                            choices=self._get_available_workflows(),
                            value=self._get_default_workflow(),
                            interactive=True,
                            scale=3
                        )
                        refresh_workflow_btn = gr.Button("🔄", scale=0, size="sm")

                with gr.Group():
                    gr.Markdown("### Settings")

                    prompt = gr.Textbox(
                        label="Prompt (Bewegung/Emotion)",
                        value=DEFAULT_PROMPT,
                        lines=2,
                        placeholder="Person singing emotionally..."
                    )

                    negative_prompt = gr.Textbox(
                        label="Negative Prompt",
                        value=DEFAULT_NEGATIVE,
                        lines=2
                    )

                    with gr.Row():
                        resolution = gr.Dropdown(
                            label="Resolution",
                            choices=RESOLUTION_CHOICES,
                            value="720p",
                            interactive=True
                        )
                        steps = gr.Slider(
                            label="Steps",
                            minimum=2,
                            maximum=20,
                            value=4,
                            step=1,
                            info="4 steps with LoRA speedup recommended"
                        )

                    with gr.Row():
                        cfg = gr.Slider(
                            label="CFG",
                            minimum=0.5,
                            maximum=5.0,
                            value=1.0,
                            step=0.1
                        )
                        fps = gr.Slider(
                            label="FPS",
                            minimum=12,
                            maximum=24,
                            value=16,
                            step=1
                        )

                    output_name = gr.Textbox(
                        label="Output Name",
                        value="lipsync_output",
                        placeholder="Name for the output file"
                    )

                with gr.Group():
                    gr.Markdown("### Generation Mode")

                    batch_mode = gr.Checkbox(
                        label="🔄 Batch Mode (use exported segments)",
                        value=False,
                        info="Process all segments from Segmentation tab"
                    )

                    use_frame_chaining = gr.Checkbox(
                        label="🔗 LastFrame Chaining",
                        value=True,
                        info="Use last frame of segment N as start for N+1"
                    )

                    concat_output = gr.Checkbox(
                        label="📼 Concatenate Output",
                        value=True,
                        info="Merge all segments into one video"
                    )

                with gr.Group():
                    gr.Markdown("### Generation")
                    generate_btn = gr.Button(
                        "🎬 Lipsync Video generieren",
                        variant="primary",
                        size="lg"
                    )
                    generate_batch_btn = gr.Button(
                        "🎬 Batch Generate (All Segments)",
                        variant="secondary",
                        size="lg"
                    )
                    progress_bar = gr.Markdown("")
                    generation_status = gr.Markdown("")

            with gr.Column(scale=1):
                gr.Markdown("### Preview")

                # Input summary
                with gr.Accordion("📋 Input Summary", open=True):
                    input_summary = gr.Markdown("*Load image and audio in the previous tabs*")

                # Output video
                output_video = gr.Video(
                    label="Generated Video",
                    height=400
                )
                output_path_info = gr.Markdown("")

        # Event handlers
        def update_summary():
            """Update the input summary."""
            lines = []

            if self._current_image_path:
                lines.append(f"**Image:** {os.path.basename(self._current_image_path)}")
            else:
                lines.append("**Image:** ❌ Not loaded")

            if self._trimmed_audio_path and os.path.isfile(self._trimmed_audio_path):
                info = self.lipsync_service.get_audio_info(self._trimmed_audio_path)
                if info:
                    lines.append(f"**Audio:** {info.duration:.1f}s (trimmed)")
                else:
                    lines.append("**Audio:** ✅ Trimmed")
            elif self._current_audio_path:
                lines.append("**Audio:** ⚠️ Not yet trimmed")
            else:
                lines.append("**Audio:** ❌ Not loaded")

            return "\n\n".join(lines)

        def on_generate(workflow_file, prompt_text, neg_prompt, res_preset, steps_val, cfg_val, fps_val, name):
            # Validate workflow
            if not workflow_file:
                yield "", "❌ Please select a workflow", None, ""
                return

            # Validate inputs
            if not self._current_image_path or not os.path.isfile(self._current_image_path):
                yield "", "❌ Please upload an image first (Tab 1)", None, ""
                return

            audio_path = self._trimmed_audio_path or self._current_audio_path
            if not audio_path or not os.path.isfile(audio_path):
                yield "", "❌ Please upload and trim audio first (Tab 2)", None, ""
                return

            # Get resolution
            width, height = self.lipsync_service.get_resolution(res_preset)

            # Create job
            job = LipsyncJob(
                image_path=self._current_image_path,
                audio_path=audio_path,
                prompt=prompt_text,
                negative_prompt=neg_prompt,
                width=width,
                height=height,
                output_name=name or "lipsync_output",
                steps=int(steps_val),
                cfg=float(cfg_val),
                fps=int(fps_val)
            )

            yield "⏳ Starting Generation...", "", None, ""

            # Progress callback
            def progress_cb(pct, status):
                pass  # Gradio doesn't support live progress in generators well

            # Generate with selected workflow
            success, result = self.lipsync_service.generate_lipsync(
                job, progress_cb, workflow_file=workflow_file
            )

            if success:
                if os.path.isfile(result):
                    yield (
                        "✅ **Generation complete!**",
                        "",
                        result,
                        f"**Output:** {result}"
                    )
                else:
                    yield (
                        f"✅ {result}",
                        "",
                        None,
                        "Video in ComfyUI output folder"
                    )
            else:
                yield "", f"❌ **Error:** {result}", None, ""

        def on_refresh_workflows():
            choices = self._get_available_workflows()
            default = self._get_default_workflow()
            return gr.update(choices=choices, value=default)

        def on_generate_batch(workflow_file, prompt_text, neg_prompt, res_preset, steps_val, cfg_val, fps_val, name, use_chaining, do_concat):
            """Generate lipsync for all exported segments."""
            # Validate
            if not workflow_file:
                yield "❌ Please select a workflow", "", None, ""
                return

            if not self._current_image_path or not os.path.isfile(self._current_image_path):
                yield "❌ Please upload an image first (Tab 1)", "", None, ""
                return

            if not self._exported_segments:
                yield "❌ No segments exported. Go to Segmentation tab and export segments first.", "", None, ""
                return

            yield f"⏳ Starting batch generation ({len(self._exported_segments)} segments)...", "", None, ""

            # Create BatchSegments from exported files
            segments = []
            for i, seg_path in enumerate(self._exported_segments):
                if os.path.isfile(seg_path):
                    segments.append(BatchSegment(
                        audio_path=seg_path,
                        start_time=0,
                        end_time=0,
                        segment_index=i
                    ))

            if not segments:
                yield "❌ No valid segment files found", "", None, ""
                return

            # Get resolution
            width, height = self.lipsync_service.get_resolution(res_preset)

            # Run batch generation
            result = self.lipsync_service.generate_batch_lipsync(
                base_image_path=self._current_image_path,
                segments=segments,
                prompt=prompt_text,
                negative_prompt=neg_prompt,
                width=width,
                height=height,
                workflow_file=workflow_file,
                output_prefix=name or "lipsync_batch",
                steps=int(steps_val),
                cfg=float(cfg_val),
                fps=int(fps_val),
                use_last_frame_chaining=use_chaining,
                progress_callback=None
            )

            if result.success:
                output_video_path = None

                # Concatenate if requested
                if do_concat and len(result.videos) > 1:
                    yield f"⏳ Concatenating {len(result.videos)} videos...", "", None, ""

                    import tempfile
                    concat_path = os.path.join(tempfile.gettempdir(), f"{name or 'lipsync_batch'}_full.mp4")
                    success, concat_result = self.lipsync_service.concatenate_videos(
                        result.videos,
                        concat_path
                    )

                    if success:
                        output_video_path = concat_result
                    else:
                        yield (
                            f"✅ Generated {result.completed_segments}/{result.total_segments} segments",
                            f"⚠️ Concat failed: {concat_result}",
                            result.videos[-1] if result.videos else None,
                            f"**Videos:** {len(result.videos)} segments generated"
                        )
                        return
                elif result.videos:
                    output_video_path = result.videos[-1]

                yield (
                    f"✅ **Batch complete!** {result.completed_segments}/{result.total_segments} segments",
                    "",
                    output_video_path,
                    f"**Output:** {output_video_path}" if output_video_path else ""
                )
            else:
                errors = "\n".join(result.errors[:3])
                yield (
                    f"⚠️ Completed {result.completed_segments}/{result.total_segments}",
                    f"❌ Errors:\n{errors}",
                    result.videos[-1] if result.videos else None,
                    ""
                )

        # Wire up refresh button
        refresh_workflow_btn.click(
            fn=on_refresh_workflows,
            outputs=[workflow_dropdown]
        )

        # Wire up generate button
        generate_btn.click(
            fn=on_generate,
            inputs=[workflow_dropdown, prompt, negative_prompt, resolution, steps, cfg, fps, output_name],
            outputs=[progress_bar, generation_status, output_video, output_path_info]
        )

        # Wire up batch generate button
        generate_batch_btn.click(
            fn=on_generate_batch,
            inputs=[workflow_dropdown, prompt, negative_prompt, resolution, steps, cfg, fps, output_name, use_frame_chaining, concat_output],
            outputs=[progress_bar, generation_status, output_video, output_path_info]
        )

        # Update summary when tab is shown (approximation via interval)
        interface = gr.Blocks()
        # Note: Can't easily detect tab switch, so summary updates on generate

    def _get_character_choices(self) -> list:
        """Get dropdown choices for character LoRAs."""
        try:
            loras = self.character_lora_service.scan_loras(force_refresh=True)
            return [lora.id for lora in loras]
        except Exception as e:
            logger.warning(f"Failed to scan LoRAs: {e}")
            return []

    def _get_flux_workflows(self) -> list:
        """Get list of available Flux/keyframe workflows for dropdown."""
        return self.workflow_registry.get_dropdown_choices(PREFIX_KEYFRAME)

    def _get_default_flux_workflow(self) -> Optional[str]:
        """Get default Flux workflow."""
        return self.workflow_registry.get_default(PREFIX_KEYFRAME)
