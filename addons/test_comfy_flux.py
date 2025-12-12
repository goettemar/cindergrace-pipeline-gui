"""Test addon for ComfyUI connection and Flux image generation"""
import os
import sys
import time
from datetime import datetime
from typing import List, Tuple, Optional
import gradio as gr

# Ensure parent directory is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from addons.base_addon import BaseAddon
from infrastructure.comfy_api import ComfyUIAPI
from infrastructure.config_manager import ConfigManager
from infrastructure.workflow_registry import WorkflowRegistry


class TestComfyFluxAddon(BaseAddon):
    """Test ComfyUI connection and generate test images with Flux"""

    def __init__(self):
        super().__init__(
            name="ComfyUI Test",
            description="Test ComfyUI connection and generate Flux images"
        )
        self.config = ConfigManager()
        self.api = None
        self.current_images = []
        self.workflow_registry = WorkflowRegistry()

    def get_tab_name(self) -> str:
        return "🧪 Test ComfyUI"

    def render(self) -> gr.Blocks:
        """Render the test addon UI"""

        with gr.Blocks() as interface:
            gr.Markdown("# 🔌 ComfyUI Connection & Flux Test")
            gr.Markdown("Test your local ComfyUI installation and generate test images with Flux")

            # Connection Section
            with gr.Group():
                gr.Markdown("## Connection Test")

                with gr.Row():
                    comfy_url = gr.Textbox(
                        value=self.config.get_comfy_url(),
                        label="ComfyUI URL",
                        placeholder="http://127.0.0.1:8188"
                    )
                    test_conn_btn = gr.Button("🔌 Test Connection", variant="secondary")

                connection_status = gr.Markdown("**Status:** 🔴 Not tested")

                with gr.Accordion("System Info", open=False):
                    system_info = gr.JSON(label="ComfyUI System Stats", value={})

            gr.Markdown("---")

            # Generation Section
            with gr.Group():
                gr.Markdown("## 🎨 Flux Test Generation")

                prompt = gr.Textbox(
                    value="gothic cathedral interior at night, moonlight through tall windows, scattered candles on marble floor, dust in air, cinematic, dark atmosphere, 16:9",
                    label="Prompt",
                    lines=3,
                    placeholder="Enter your prompt here..."
                )

                with gr.Row():
                    num_images = gr.Slider(
                        minimum=1,
                        maximum=10,
                        value=4,
                        step=1,
                        label="Number of Images",
                        info="Number of test images to generate"
                    )
                    start_seed = gr.Number(
                        value=1001,
                        label="Starting Seed",
                        precision=0,
                        info="Seed will increment for each image"
                    )

                workflow_dropdown = gr.Dropdown(
                    choices=self._get_available_workflows(),
                    value=self._get_default_workflow(),
                    label="Workflow Template",
                    info="Select one of your Flux workflow files"
                )

                refresh_workflows_btn = gr.Button("🔄 Refresh Workflows", size="sm")

                generate_btn = gr.Button(
                    "🎨 Generate Test Images",
                    variant="primary",
                    size="lg"
                )

            # Progress Section
            with gr.Group():
                status_text = gr.Markdown("**Ready** - Click 'Generate Test Images' to start")

            gr.Markdown("---")

            # Results Section
            with gr.Group():
                gr.Markdown("## 🖼️ Generated Images")

                image_gallery = gr.Gallery(
                    label="Results",
                    show_label=False,
                    columns=4,
                    rows=1,
                    height="auto",
                    object_fit="contain"
                )

                with gr.Row():
                    clear_btn = gr.Button("🗑️ Clear Gallery")
                    # download_btn = gr.Button("📦 Download All as ZIP")

            # Event Handlers
            test_conn_btn.click(
                fn=self.test_connection,
                inputs=[comfy_url],
                outputs=[connection_status, system_info]
            )

            generate_btn.click(
                fn=self.generate_test_images,
                inputs=[comfy_url, prompt, num_images, start_seed, workflow_dropdown],
                outputs=[image_gallery, status_text]
            )

            refresh_workflows_btn.click(
                fn=lambda: gr.update(choices=self._get_available_workflows()),
                outputs=[workflow_dropdown]
            )

            clear_btn.click(
                fn=lambda: ([], "**Ready** - Gallery cleared"),
                outputs=[image_gallery, status_text]
            )

        return interface

    def test_connection(
        self,
        comfy_url: str
    ) -> Tuple[str, dict]:
        """
        Test connection to ComfyUI

        Args:
            comfy_url: ComfyUI server URL

        Returns:
            Tuple of (status_markdown, system_info_dict)
        """
        try:
            api = ComfyUIAPI(comfy_url)
            result = api.test_connection()

            if result["connected"]:
                status_md = "**Status:** ✅ Connected successfully!"
                system_info = result["system"]
                self.api = api  # Store for later use
                return status_md, system_info
            else:
                status_md = f"**Status:** 🔴 Connection failed\n\n**Error:** {result['error']}"
                return status_md, {}

        except Exception as e:
            status_md = f"**Status:** 🔴 Connection failed\n\n**Error:** {str(e)}"
            return status_md, {}

    def generate_test_images(
        self,
        comfy_url: str,
        prompt: str,
        num_images: int,
        start_seed: int,
        workflow_file: str
    ) -> Tuple[List[str], str]:
        """
        Generate test images using Flux

        Args:
            comfy_url: ComfyUI server URL
            prompt: Text prompt for generation
            num_images: Number of images to generate
            start_seed: Starting seed value
            workflow_file: Workflow template filename

        Returns:
            Tuple of (image_list, status_text)
        """
        try:
            # Check if workflow file is selected
            if not workflow_file or workflow_file.startswith("No workflows"):
                return [], f"**❌ Error:** No workflow selected. Please add your ComfyUI workflow JSON files to `config/workflow_templates/` and click 🔄 Refresh Workflows."

            # Initialize API
            if self.api is None or self.api.server_url != comfy_url:
                self.api = ComfyUIAPI(comfy_url)

            # Test connection first
            conn_result = self.api.test_connection()
            if not conn_result["connected"]:
                return [], f"**❌ Error:** Connection failed - {conn_result['error']}"

            # Load workflow
            workflow_path = os.path.join(
                self.config.get_workflow_dir(),
                workflow_file
            )

            if not os.path.exists(workflow_path):
                return [], f"**❌ Error:** Workflow file not found: `{workflow_path}`\n\nPlease add workflow JSON files to `config/workflow_templates/`"

            workflow = self.api.load_workflow(workflow_path)

            # Generate images
            generated_images = []
            num_images = int(num_images)
            start_seed = int(start_seed)

            for i in range(num_images):
                current_seed = start_seed + i
                print(f"Generating image {i+1}/{num_images} (seed {current_seed})...")

                # Update workflow parameters
                updated_workflow = self.api.update_workflow_params(
                    workflow,
                    prompt=prompt,
                    seed=current_seed,
                    filename_prefix=f"test_{current_seed}"
                )

                # Queue job
                try:
                    prompt_id = self.api.queue_prompt(updated_workflow)

                    # Monitor progress
                    result = self.api.monitor_progress(
                        prompt_id,
                        callback=None,
                        timeout=300
                    )

                    if result["status"] == "success" and result["output_images"]:
                        generated_images.extend(result["output_images"])
                        print(f"✓ Generated image with seed {current_seed}")
                    else:
                        error_msg = result.get("error", "Unknown error")
                        print(f"✗ Failed to generate image with seed {current_seed}: {error_msg}")

                except Exception as e:
                    print(f"✗ Error generating image with seed {current_seed}: {e}")
                    continue

            # Return results
            if generated_images:
                status = f"**✅ Success!** Generated {len(generated_images)} image(s)"
                self.current_images = generated_images
                return generated_images, status
            else:
                return [], "**❌ Error:** No images were generated. Check ComfyUI console for errors."

        except Exception as e:
            return [], f"**❌ Error:** {str(e)}"

    def _get_available_workflows(self) -> List[str]:
        """
        Get list of available workflow files

        Returns:
            List of workflow filenames
        """
        workflows = self.workflow_registry.get_files(category="flux")
        return workflows if workflows else ["No workflows found - update workflow_presets.json"]

    def _get_default_workflow(self) -> Optional[str]:
        """Get default workflow (first available)"""
        return self.workflow_registry.get_default(category="flux")
