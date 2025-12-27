"""Addon for First/Last Frame Video Generation."""
import os
import sys
import subprocess
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from addons.base_addon import BaseAddon
from addons.components import format_project_status
from infrastructure.config_manager import ConfigManager
from infrastructure.comfy_api import ComfyUIAPI
from infrastructure.workflow_registry import WorkflowRegistry, PREFIX_VIDEO_FIRSTLAST
from infrastructure.logger import get_logger
from services.firstlast_video_service import FirstLastVideoService

logger = get_logger(__name__)

# Resolution choices for Wan 2.2
RESOLUTION_CHOICES = [
    ("1280×720 (Landscape)", (1280, 720)),
    ("720×1280 (Portrait)", (720, 1280)),
    ("832×480 (Landscape)", (832, 480)),
    ("480×832 (Portrait)", (480, 832)),
    ("640×640 (Square)", (640, 640)),
]


class FirstLastVideoAddon(BaseAddon):
    """Addon for generating First/Last Frame transition videos."""

    def __init__(self):
        super().__init__(
            name="First/Last Frame Video",
            description="Generate transition videos between keyframes",
            category="production"
        )
        self.config = ConfigManager()
        self.service = FirstLastVideoService(self.config)
        self.workflow_registry = WorkflowRegistry()

    def get_tab_name(self) -> str:
        return "🎞️ Transition"

    def render(self) -> gr.Blocks:
        with gr.Blocks() as interface:
            # Unified header: Tab name left, no project relation
            gr.HTML(format_project_status(tab_name="🎞️ First/Last Frame Video", no_project_relation=True))

            gr.Markdown(
                "Create transition videos between images. "
                "Upload images, group them into clips, and generate smooth morphing videos."
            )

            # State for images and clips
            images_state = gr.State([])  # List of {"path": str, "name": str}
            clips_state = gr.State([[]])  # List of lists (clip groups)

            with gr.Row():
                # Left Column: Image Upload & Management
                with gr.Column(scale=1):
                    with gr.Group():
                        gr.Markdown("## 📤 Upload Images")
                        image_upload = gr.File(
                            label="Select images",
                            file_count="multiple",
                            file_types=["image"],
                            type="filepath"
                        )
                        upload_btn = gr.Button("📥 Add Images", variant="secondary")

                    with gr.Group():
                        gr.Markdown("## 🖼️ Image Order")
                        gr.Markdown(
                            "*Click on an image to select it. "
                            "Use the buttons to change the order or insert clip separators.*"
                        )

                        images_gallery = gr.Gallery(
                            label="Images",
                            columns=4,
                            rows=2,
                            height=200,
                            object_fit="cover",
                            allow_preview=True
                        )

                        selected_index = gr.State(-1)

                        with gr.Row():
                            move_up_btn = gr.Button("⬆️ Move Up", size="sm")
                            move_down_btn = gr.Button("⬇️ Move Down", size="sm")
                            add_separator_btn = gr.Button("➖ Insert Separator", size="sm", variant="secondary")
                            remove_btn = gr.Button("🗑️ Remove", size="sm", variant="stop")

                        clear_all_btn = gr.Button("🗑️ Clear All Images", variant="stop", size="sm")

                # Right Column: Clip Preview & Settings
                with gr.Column(scale=1):
                    with gr.Group():
                        gr.Markdown("## 📋 Clip Structure")
                        clips_preview = gr.Markdown("*No images uploaded yet*")

                    with gr.Group():
                        gr.Markdown("## ⚙️ Settings")

                        # Workflow Selection
                        workflow_choices = self.workflow_registry.get_dropdown_choices(PREFIX_VIDEO_FIRSTLAST)
                        default_workflow = self.workflow_registry.get_default(PREFIX_VIDEO_FIRSTLAST)

                        with gr.Row():
                            workflow_dropdown = gr.Dropdown(
                                choices=workflow_choices,
                                value=default_workflow,
                                label="Workflow"
                            )
                        with gr.Row():
                            set_default_btn = gr.Button("⭐ Set as Default", size="sm")
                            rescan_btn = gr.Button("🔄 Scan", size="sm")
                        workflow_status = gr.Markdown("")

                        prompt_input = gr.Textbox(
                            label="Prompt",
                            placeholder="Describe the transition (e.g. 'smooth morphing transformation')",
                            lines=2,
                            value="smooth cinematic transition, high quality"
                        )

                        with gr.Row():
                            resolution_dropdown = gr.Dropdown(
                                choices=[label for label, _ in RESOLUTION_CHOICES],
                                value=RESOLUTION_CHOICES[0][0],
                                label="Resolution"
                            )
                            frames_slider = gr.Slider(
                                minimum=33,
                                maximum=129,
                                step=8,
                                value=81,
                                label="Frames",
                                info="81 frames ≈ 5s at 16fps"
                            )

                        with gr.Row():
                            fps_slider = gr.Slider(
                                minimum=8,
                                maximum=24,
                                step=1,
                                value=16,
                                label="FPS"
                            )
                            steps_slider = gr.Slider(
                                minimum=10,
                                maximum=30,
                                step=1,
                                value=20,
                                label="Steps"
                            )

            # Generation Section
            with gr.Group():
                gr.Markdown("## 🎬 Generation")

                with gr.Row():
                    generate_btn = gr.Button("▶️ Generate Videos", variant="primary", size="lg")
                    open_folder_btn = gr.Button("📁 Open Output Folder", variant="secondary")

                status_box = gr.Markdown("**Status:** Ready")
                progress_bar = gr.Progress()

                with gr.Row():
                    last_video = gr.Video(label="Last generated video", visible=True)

            # Event Handlers
            def add_images(files, current_images, current_clips):
                """Add uploaded images to the list."""
                if not files:
                    return current_images, current_clips, self._render_gallery(current_images), self._render_clips_preview(current_clips, current_images)

                new_images = list(current_images) if current_images else []

                for f in files:
                    if isinstance(f, str):
                        path = f
                    else:
                        path = f.name if hasattr(f, 'name') else str(f)

                    if os.path.exists(path):
                        new_images.append({
                            "path": path,
                            "name": os.path.basename(path)
                        })

                # Initialize clips if empty
                if not current_clips or current_clips == [[]]:
                    new_clips = [list(range(len(new_images)))]
                else:
                    # Add new images to last clip
                    new_clips = [list(clip) for clip in current_clips]
                    start_idx = len(current_images) if current_images else 0
                    for i in range(len(files)):
                        new_clips[-1].append(start_idx + i)

                gallery_data = self._render_gallery(new_images)
                clips_md = self._render_clips_preview(new_clips, new_images)

                return new_images, new_clips, gallery_data, clips_md

            def move_image_up(images, clips, selected_idx):
                """Move selected image up in the list."""
                if selected_idx <= 0 or selected_idx >= len(images):
                    return images, clips, self._render_gallery(images), self._render_clips_preview(clips, images)

                new_images = list(images)
                new_images[selected_idx], new_images[selected_idx - 1] = new_images[selected_idx - 1], new_images[selected_idx]

                # Update clip indices
                new_clips = self._update_clip_indices_after_swap(clips, selected_idx, selected_idx - 1)

                return new_images, new_clips, self._render_gallery(new_images), self._render_clips_preview(new_clips, new_images)

            def move_image_down(images, clips, selected_idx):
                """Move selected image down in the list."""
                if selected_idx < 0 or selected_idx >= len(images) - 1:
                    return images, clips, self._render_gallery(images), self._render_clips_preview(clips, images)

                new_images = list(images)
                new_images[selected_idx], new_images[selected_idx + 1] = new_images[selected_idx + 1], new_images[selected_idx]

                # Update clip indices
                new_clips = self._update_clip_indices_after_swap(clips, selected_idx, selected_idx + 1)

                return new_images, new_clips, self._render_gallery(new_images), self._render_clips_preview(new_clips, new_images)

            def add_separator(images, clips, selected_idx):
                """Add a clip separator after the selected image."""
                if selected_idx < 0 or selected_idx >= len(images) - 1:
                    return clips, self._render_clips_preview(clips, images)

                # Find which clip contains this index and split it
                new_clips = []
                for clip in clips:
                    if selected_idx in clip:
                        split_pos = clip.index(selected_idx) + 1
                        if split_pos < len(clip):
                            new_clips.append(clip[:split_pos])
                            new_clips.append(clip[split_pos:])
                        else:
                            new_clips.append(clip)
                    else:
                        new_clips.append(clip)

                return new_clips, self._render_clips_preview(new_clips, images)

            def remove_image(images, clips, selected_idx):
                """Remove selected image."""
                if selected_idx < 0 or selected_idx >= len(images):
                    return images, clips, self._render_gallery(images), self._render_clips_preview(clips, images), -1

                new_images = [img for i, img in enumerate(images) if i != selected_idx]

                # Update clips - remove the index and shift higher indices down
                new_clips = []
                for clip in clips:
                    new_clip = []
                    for idx in clip:
                        if idx < selected_idx:
                            new_clip.append(idx)
                        elif idx > selected_idx:
                            new_clip.append(idx - 1)
                    if new_clip:
                        new_clips.append(new_clip)

                if not new_clips:
                    new_clips = [[]]

                return new_images, new_clips, self._render_gallery(new_images), self._render_clips_preview(new_clips, new_images), -1

            def clear_all():
                """Clear all images."""
                return [], [[]], [], "*No images uploaded yet*", -1

            def on_gallery_select(evt: gr.SelectData):
                """Handle gallery selection."""
                return evt.index

            def generate_videos(images, clips, prompt, resolution_label, frames, fps, steps, workflow_file, progress=gr.Progress()):
                """Generate all transition videos."""
                if not images or not clips:
                    return "**Status:** ❌ No images available", None

                # Get resolution
                resolution = (1280, 720)
                for label, res in RESOLUTION_CHOICES:
                    if label == resolution_label:
                        resolution = res
                        break

                width, height = resolution

                # Build clip groups with actual paths
                clip_paths = []
                for clip in clips:
                    if len(clip) >= 2:
                        paths = [images[idx]["path"] for idx in clip if idx < len(images)]
                        if len(paths) >= 2:
                            clip_paths.append(paths)

                if not clip_paths:
                    return "**Status:** ❌ No valid clips (at least 2 images per clip required)", None

                total_transitions = sum(len(c) - 1 for c in clip_paths)

                def progress_callback(pct, status):
                    progress(pct, desc=status)

                progress(0, desc="Starting Generation...")

                result = self.service.generate_all_clips(
                    clips=clip_paths,
                    prompt=prompt,
                    width=width,
                    height=height,
                    frames=int(frames),
                    fps=int(fps),
                    steps=int(steps),
                    callback=progress_callback,
                    workflow_file=workflow_file,
                )

                if result.success:
                    successful = sum(1 for c in result.clips if c.success)
                    total = len(result.clips)

                    # Find last video
                    last_video_path = None
                    for clip in reversed(result.clips):
                        for trans in reversed(clip.transitions):
                            if trans.success and trans.video_path:
                                last_video_path = trans.video_path
                                break
                        if last_video_path:
                            break

                    status = f"**Status:** ✅ {successful}/{total} clips generated ({result.total_transitions} transitions) in {result.duration_seconds:.1f}s"
                    return status, last_video_path
                else:
                    return f"**Status:** ❌ Error: {result.error}", None

            def open_output_folder():
                """Open the output folder."""
                output_dir = self.service._get_output_dir()
                os.makedirs(output_dir, exist_ok=True)
                subprocess.run(["xdg-open", output_dir], check=False)
                return f"**Status:** 📁 Folder opened: {output_dir}"

            def set_as_default(workflow_file):
                """Set selected workflow as default."""
                if not workflow_file:
                    return "**⚠️ No workflow selected**"
                if self.workflow_registry.set_default(PREFIX_VIDEO_FIRSTLAST, workflow_file):
                    display_name = self.workflow_registry.get_display_name(workflow_file)
                    logger.info(f"Set default First-Last workflow: {workflow_file}")
                    return f"**✅ Default set:** {display_name}"
                else:
                    return "**❌ Error setting default**"

            def rescan_workflows():
                """Rescan filesystem for workflows and update cache."""
                count, _ = self.workflow_registry.rescan(PREFIX_VIDEO_FIRSTLAST)
                choices = self.workflow_registry.get_dropdown_choices(PREFIX_VIDEO_FIRSTLAST)
                default = self.workflow_registry.get_default(PREFIX_VIDEO_FIRSTLAST)
                status = f"**✅ Scan complete:** {count} First/Last Workflows"
                return gr.update(choices=choices, value=default), status

            # Wire up events
            upload_btn.click(
                fn=add_images,
                inputs=[image_upload, images_state, clips_state],
                outputs=[images_state, clips_state, images_gallery, clips_preview]
            )

            image_upload.change(
                fn=add_images,
                inputs=[image_upload, images_state, clips_state],
                outputs=[images_state, clips_state, images_gallery, clips_preview]
            )

            images_gallery.select(
                fn=on_gallery_select,
                outputs=[selected_index]
            )

            move_up_btn.click(
                fn=move_image_up,
                inputs=[images_state, clips_state, selected_index],
                outputs=[images_state, clips_state, images_gallery, clips_preview]
            )

            move_down_btn.click(
                fn=move_image_down,
                inputs=[images_state, clips_state, selected_index],
                outputs=[images_state, clips_state, images_gallery, clips_preview]
            )

            add_separator_btn.click(
                fn=add_separator,
                inputs=[images_state, clips_state, selected_index],
                outputs=[clips_state, clips_preview]
            )

            remove_btn.click(
                fn=remove_image,
                inputs=[images_state, clips_state, selected_index],
                outputs=[images_state, clips_state, images_gallery, clips_preview, selected_index]
            )

            clear_all_btn.click(
                fn=clear_all,
                outputs=[images_state, clips_state, images_gallery, clips_preview, selected_index]
            )

            generate_btn.click(
                fn=generate_videos,
                inputs=[images_state, clips_state, prompt_input, resolution_dropdown, frames_slider, fps_slider, steps_slider, workflow_dropdown],
                outputs=[status_box, last_video]
            )

            open_folder_btn.click(
                fn=open_output_folder,
                outputs=[status_box]
            )

            set_default_btn.click(
                fn=set_as_default,
                inputs=[workflow_dropdown],
                outputs=[workflow_status]
            )

            rescan_btn.click(
                fn=rescan_workflows,
                outputs=[workflow_dropdown, workflow_status]
            )

        return interface

    def _render_gallery(self, images: List[Dict]) -> List[Tuple[str, str]]:
        """Render gallery data from images list."""
        if not images:
            return []
        return [(img["path"], img["name"]) for img in images]

    def _render_clips_preview(self, clips: List[List[int]], images: List[Dict]) -> str:
        """Render markdown preview of clip structure."""
        if not images or not clips or clips == [[]]:
            return "*No images uploaded yet*"

        lines = ["### Clip Overview\n"]

        for clip_idx, clip in enumerate(clips):
            if not clip:
                continue

            clip_images = [images[i]["name"] for i in clip if i < len(images)]
            num_transitions = max(0, len(clip_images) - 1)

            lines.append(f"**Clip {clip_idx + 1}** ({num_transitions} Transition{'s' if num_transitions != 1 else ''})")

            # Show images with arrows
            if clip_images:
                image_chain = " → ".join([f"`{name[:15]}...`" if len(name) > 15 else f"`{name}`" for name in clip_images])
                lines.append(f"  {image_chain}")

            lines.append("")

        total_transitions = sum(max(0, len(c) - 1) for c in clips)
        lines.append(f"---\n**Total:** {len(clips)} clip(s), {total_transitions} transition(s)")

        return "\n".join(lines)

    def _update_clip_indices_after_swap(self, clips: List[List[int]], idx1: int, idx2: int) -> List[List[int]]:
        """Update clip indices after swapping two images."""
        new_clips = []
        for clip in clips:
            new_clip = []
            for idx in clip:
                if idx == idx1:
                    new_clip.append(idx2)
                elif idx == idx2:
                    new_clip.append(idx1)
                else:
                    new_clip.append(idx)
            new_clips.append(new_clip)
        return new_clips


__all__ = ["FirstLastVideoAddon"]
