"""Addon for Character Dataset Generation using Qwen Image Edit.

This addon generates training datasets for LoRA training by creating
15 different views/poses from a single base character image.
"""
import os
import sys
from typing import List

import gradio as gr

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from addons.base_addon import BaseAddon
from addons.components import format_project_status
from infrastructure.config_manager import ConfigManager
from infrastructure.logger import get_logger
from services.character_trainer_service import (
    CharacterTrainerService,
    VIEW_PRESETS,
)

logger = get_logger(__name__)


class DatasetGeneratorAddon(BaseAddon):
    """Addon for generating character training datasets using Qwen Image Edit."""

    def __init__(self):
        super().__init__(
            name="Dataset Generator",
            description="Generate character training datasets with 15 views/poses",
            category="training"
        )
        self.config = ConfigManager()
        self.char_service = CharacterTrainerService(self.config)

    def get_tab_name(self) -> str:
        return "📸 Dataset"

    def render(self) -> gr.Blocks:
        with gr.Blocks() as interface:
            gr.HTML(format_project_status(
                tab_name="📸 Character Dataset Generator",
                no_project_relation=True
            ))

            gr.Markdown(
                "Automatically generate 15 different views/poses of a character "
                "for LoRA training using Qwen Image Edit."
            )

            with gr.Tabs():
                with gr.Tab("🎨 Create Dataset"):
                    self._render_generation_tab()

                with gr.Tab("📋 Views Reference"):
                    self._render_presets_reference_tab()

                with gr.Tab("💡 Resolution Guide"):
                    self._render_resolution_guide_tab()

        return interface

    def _render_generation_tab(self):
        """Render the dataset generation UI."""
        gr.Markdown("## 📸 Generate Training Dataset")
        gr.Markdown(
            "Upload a base image of your character and automatically generate 15 different "
            "views/poses with matching captions for LoRA training."
        )

        with gr.Row():
            # Left Column: Input
            with gr.Column(scale=1):
                with gr.Group():
                    gr.Markdown("### 📥 Input")

                    character_name = gr.Textbox(
                        label="Character Name / Trigger Word",
                        placeholder="e.g. 'elena_warrior' or 'max_detective'",
                        info="Used as trigger word for the LoRA"
                    )

                    base_image = gr.Image(
                        label="Base Image",
                        type="filepath",
                        height=300,
                        sources=["upload", "clipboard"]
                    )

                    gr.Markdown(
                        "*Tip: Use a clear image of your character with neutral "
                        "background for best results.*"
                    )

                with gr.Group():
                    gr.Markdown("### ⚙️ Workflow & Settings")

                    workflow_dropdown = gr.Dropdown(
                        label="Workflow",
                        choices=self._get_workflow_choices(),
                        value=self._get_default_workflow(),
                        info="Qwen Image Edit Workflow"
                    )

                    with gr.Row():
                        steps_slider = gr.Slider(
                            minimum=4,
                            maximum=20,
                            step=1,
                            value=8,
                            label="Steps",
                            info="More steps = better quality"
                        )
                        cfg_slider = gr.Slider(
                            minimum=0.5,
                            maximum=3.0,
                            step=0.1,
                            value=1.0,
                            label="CFG Scale"
                        )

            # Right Column: Preview & Progress
            with gr.Column(scale=1):
                with gr.Group():
                    gr.Markdown("### 🎬 Generation")

                    generate_dataset_btn = gr.Button(
                        "▶️ Generate 15 Views",
                        variant="primary",
                        size="lg"
                    )

                    dataset_status = gr.Markdown("**Status:** Ready")

                with gr.Group():
                    gr.Markdown("### 🖼️ Generated Views")

                    results_gallery = gr.Gallery(
                        label="Training Dataset",
                        columns=5,
                        rows=3,
                        height=350,
                        object_fit="cover",
                        allow_preview=True
                    )

                    dataset_output_dir = gr.Textbox(
                        label="Dataset Path",
                        interactive=False,
                        info="This path is required for LoRA training"
                    )

                    with gr.Row():
                        open_dataset_btn = gr.Button("📁 Open folder", size="sm")
                        copy_path_btn = gr.Button("📋 Copy path", size="sm")

        # Event handlers
        def generate_dataset(name, image_path, workflow, steps, cfg, progress=gr.Progress()):
            if not name or not name.strip():
                return "**Status:** ❌ Please enter a character name", [], ""

            if not image_path or not os.path.exists(image_path):
                return "**Status:** ❌ Please upload a base image", [], ""

            # Set workflow before generation
            workflow_file = self._get_workflow_file(workflow)
            if workflow_file:
                self.char_service.set_workflow(workflow_file)

            def progress_callback(pct, status):
                progress(pct, desc=status)

            progress(0, desc="Starting Generation...")

            result = self.char_service.generate_training_set(
                base_image_path=image_path,
                character_name=name.strip(),
                steps=int(steps),
                cfg=float(cfg),
                callback=progress_callback
            )

            if result.success:
                gallery_items = []

                # Base image
                base_path = os.path.join(result.output_dir, "00_base_image.png")
                if os.path.exists(base_path):
                    gallery_items.append((base_path, "Base"))

                # Generated views
                for view in result.views:
                    if view.success and view.image_path:
                        gallery_items.append((view.image_path, view.preset.name))

                status = (
                    f"**Status:** ✅ {result.successful_count}/15 views generated "
                    f"in {result.duration_seconds:.1f}s\n\n"
                    f"📁 Dataset ready for LoRA training!"
                )

                return status, gallery_items, result.output_dir
            else:
                return f"**Status:** ❌ {result.error}", [], ""

        def open_dataset_folder(path):
            if path and os.path.exists(path):
                os.system(f'xdg-open "{path}"')
            return "**Status:** 📁 Folder opened"

        generate_dataset_btn.click(
            fn=generate_dataset,
            inputs=[character_name, base_image, workflow_dropdown, steps_slider, cfg_slider],
            outputs=[dataset_status, results_gallery, dataset_output_dir]
        )

        open_dataset_btn.click(
            fn=open_dataset_folder,
            inputs=[dataset_output_dir],
            outputs=[dataset_status]
        )

    def _render_presets_reference_tab(self):
        """Render the presets reference tab."""
        gr.Markdown("## 📋 15 views for character training")
        gr.Markdown(
            "These views are automatically generated. "
            "Each image gets a matching caption for optimal LoRA training."
        )

        presets_data = []
        for i, preset in enumerate(VIEW_PRESETS):
            presets_data.append([
                i + 1,
                preset.name,
                preset.edit_prompt,
                preset.caption
            ])

        gr.Dataframe(
            headers=["#", "Name", "Qwen Edit Prompt", "LoRA Caption"],
            datatype=["number", "str", "str", "str"],
            value=presets_data,
            row_count=15,
            column_count=4,
            interactive=False,
            wrap=True
        )

        gr.Markdown("""
        ### 💡 Tips for good results

        **Base Image:**
        - Clear, neutral background
        - Good lighting
        - Character clearly visible

        **After Generation:**
        - Copy dataset path
        - Use in Character Trainer for LoRA training
        - Optional: Manually edit images
        """)

    def _render_resolution_guide_tab(self):
        """Render the resolution guide tab."""
        gr.Markdown("## 💡 Resolution Guide for LoRA Training")
        gr.Markdown(
            "The **resolution of your base image** determines the resolution of the generated dataset. "
            "Choose the resolution matching your planned training."
        )

        gr.Markdown("### 📊 Recommended resolutions by model & VRAM")

        # Resolution matrix data
        resolution_data = [
            ["FLUX", "16GB", "512 x 512", "Prodigy", "Standard for RTX 4080, 5060 Ti"],
            ["FLUX", "24GB", "768 x 768", "AdamW8bit", "Better details, RTX 4090, 3090"],
            ["SDXL", "8GB", "512 x 512", "Prodigy", "Minimum for RTX 3060, 4060 Ti"],
            ["SDXL", "16GB", "768 x 768", "AdamW8bit", "Good compromise"],
            ["SDXL", "24GB", "1024 x 1024", "AdamW8bit", "Native SDXL resolution (optimal)"],
            ["SD3", "8GB", "512 x 512", "Prodigy", "Minimum for RTX 3060, 4060 Ti"],
            ["SD3", "16GB", "768 x 768", "AdamW8bit", "Good compromise"],
            ["SD3", "24GB", "1024 x 1024", "AdamW8bit", "Native SD3 resolution (optimal)"],
        ]

        gr.Dataframe(
            headers=["Model", "VRAM", "Base Image Resolution", "Optimizer", "Note"],
            datatype=["str", "str", "str", "str", "str"],
            value=resolution_data,
            interactive=False,
            wrap=True
        )

        gr.Markdown("### 🎯 Native Model Resolutions")

        native_data = [
            ["FLUX.1", "512 - 1024", "Flexible, but 512px saves VRAM"],
            ["SDXL", "1024 x 1024", "Natively trained on 1024px"],
            ["SD3", "1024 x 1024", "Natively trained on 1024px"],
        ]

        gr.Dataframe(
            headers=["Model", "Native Resolution", "Note"],
            datatype=["str", "str", "str"],
            value=native_data,
            interactive=False,
            wrap=True
        )

        gr.Markdown("### 🎬 Video Generation with WAN")
        gr.Markdown(
            "If you want to use the LoRA for **video generation with WAN**, "
            "different resolutions apply! WAN requires 16:9 or 9:16 format."
        )

        wan_data = [
            ["WAN i2v", "1280 x 720", "16:9 Landscape", "720p - Standard for Video"],
            ["WAN i2v", "720 x 1280", "9:16 Portrait", "720p Portrait"],
            ["WAN i2v", "1920 x 1080", "16:9 Landscape", "1080p - Best quality"],
            ["WAN i2v", "1080 x 1920", "9:16 Portrait", "1080p Portrait"],
            ["WAN i2v", "832 x 480", "16:9 Landscape", "⚠️ Quick test only (stutters!)"],
        ]

        gr.Dataframe(
            headers=["Workflow", "Resolution", "Format", "Note"],
            datatype=["str", "str", "str", "str"],
            value=wan_data,
            interactive=False,
            wrap=True
        )

        gr.Markdown("### 🔄 Which Model for Which Purpose?")

        usecase_data = [
            ["Images Only", "SDXL / SD3", "1024 x 1024", "Square, native resolution"],
            ["Images Only", "FLUX", "512 - 1024", "Flexible, square"],
            ["Video (WAN)", "FLUX", "1280 x 720", "16:9, matches WAN 720p"],
            ["Video (WAN)", "FLUX", "1920 x 1080", "16:9, matches WAN 1080p"],
            ["Video (WAN)", "SDXL / SD3", "❌", "Square - doesn't match WAN"],
        ]

        gr.Dataframe(
            headers=["Goal", "Model", "Recommended Resolution", "Note"],
            datatype=["str", "str", "str", "str"],
            value=usecase_data,
            interactive=False,
            wrap=True
        )

        gr.Markdown("""
        ### ⚠️ Important Notes

        **For LoRA Training (Images):**
        - The base image should be **square** (1:1)
        - The resolution of the base image = resolution of generated views
        - SDXL/SD3 native: 1024x1024

        **For Video Generation (WAN):**
        - WAN requires **16:9 or 9:16** format
        - Only **FLUX** is flexible enough here
        - Train with 1280x720 or 1920x1080 base images

        **Quality vs. VRAM:**
        - Higher resolution = better details, but more VRAM
        - 720p is a good compromise for video LoRAs
        - 832x480 only for quick tests (video stutters!)

        **Workflow Recommendation:**
        1. Decide: Images or Video?
        2. Choose model and resolution accordingly
        3. Generate base image at target resolution
        4. Use Dataset Generator → Character Trainer
        """)

    def _get_workflow_choices(self) -> List[str]:
        """Get available workflow choices for dropdown."""
        workflows = self.char_service.get_available_workflows()
        if not workflows:
            return ["No gcl_* workflows found"]
        return [display for display, _ in workflows]

    def _get_default_workflow(self) -> str:
        """Get default workflow choice."""
        workflows = self.char_service.get_available_workflows()
        if workflows:
            return workflows[0][0]  # First display name
        return ""

    def _get_workflow_file(self, display_name: str) -> str:
        """Get workflow filename from display name."""
        workflows = self.char_service.get_available_workflows()
        for display, filename in workflows:
            if display == display_name:
                return filename
        return self.char_service.DEFAULT_WORKFLOW


__all__ = ["DatasetGeneratorAddon"]
