"""Image Importer Addon - Import existing images to create storyboards."""
import json
import os
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr

from addons.base_addon import BaseAddon
from addons.components import format_project_status_extended, project_status_md
from infrastructure.config_manager import ConfigManager
from infrastructure.project_store import ProjectStore
from infrastructure.logger import get_logger
from infrastructure.job_status_store import JobStatusStore
from services.image_import_service import ImageImportService, ImportedImage
from services.image_analyzer_service import ImageAnalyzerService

logger = get_logger(__name__)


class ImageImporterAddon(BaseAddon):
    """Addon to import existing images and generate storyboards."""

    def __init__(self):
        super().__init__(
            name="Image Importer",
            description="Import existing images to create storyboards for video generation",
            category="project"
        )
        self.config = ConfigManager()
        self.project_manager = ProjectStore(self.config)
        self.import_service = ImageImportService()
        self.analyzer_service = ImageAnalyzerService(self.config)
        self._job_store = JobStatusStore()
        self._scanned_images: List[ImportedImage] = []

    def get_tab_name(self) -> str:
        return "📥 Import"

    def render(self) -> gr.Blocks:
        project = self.project_manager.get_active_project(refresh=True)

        with gr.Blocks() as interface:
            # Unified header: Tab name left, project status right
            project_status = gr.HTML(format_project_status_extended(
                self.project_manager, self.config, "📥 Image Importer"
            ))

            gr.Markdown(
                "Import existing images and automatically create a storyboard. "
                "The images will be used as keyframes and can be animated directly in the Video Generator."
            )

            # State
            images_state = gr.State([])

            # Step 1: Select Images
            with gr.Group():
                gr.Markdown("## 1️⃣ Select images")

                with gr.Row():
                    folder_input = gr.Textbox(
                        label="Folder Path",
                        placeholder="/path/to/your/images",
                        info="Path to a folder with images (PNG, JPG, WEBP)"
                    )
                    scan_btn = gr.Button("🔍 Scan Folder", variant="secondary")

                # Alternative: File upload
                with gr.Accordion("Or: Upload Images", open=False):
                    file_upload = gr.File(
                        label="Upload Images",
                        file_count="multiple",
                        file_types=["image"],
                    )
                    upload_btn = gr.Button("📤 Use Uploaded Images", variant="secondary")

                scan_status = gr.Markdown("")

            # Step 2: Preview & Order
            with gr.Group():
                gr.Markdown("## 2️⃣ Preview & Order")
                gr.Markdown("*Images will become shots in the displayed order.*")

                images_gallery = gr.Gallery(
                    label="Found Images",
                    columns=4,
                    height="auto",
                    object_fit="contain",
                    show_label=True,
                )

                images_table = gr.Dataframe(
                    headers=["#", "Filename", "Resolution", "Suggested Name"],
                    datatype=["number", "str", "str", "str"],
                    column_count=(4, "fixed"),
                    interactive=False,
                    label="Image Details",
                )

                # Delete images section
                with gr.Row():
                    delete_dropdown = gr.Dropdown(
                        label="Remove Image",
                        choices=[],
                        interactive=True,
                        info="Select an image to remove"
                    )
                    delete_btn = gr.Button("🗑️ Remove", variant="secondary", size="sm")

            # Step 3: Settings
            with gr.Group():
                gr.Markdown("## 3️⃣ Import Settings")

                with gr.Row():
                    project_name_input = gr.Textbox(
                        label="Project Name",
                        value=project.get("name", "Imported Project") if project else "Imported Project",
                        info="Name in storyboard (metadata)"
                    )
                    storyboard_filename_input = gr.Textbox(
                        label="Storyboard Filename",
                        value="imported_storyboard",
                        info="Filename without .json extension"
                    )

                with gr.Row():
                    default_duration = gr.Slider(
                        minimum=1.0,
                        maximum=10.0,
                        value=3.0,
                        step=0.5,
                        label="Default Duration per Shot (sec)",
                    )

                with gr.Row():
                    rename_files = gr.Checkbox(
                        label="Rename Files",
                        value=True,
                        info="Rename files for workflow compatibility (recommended)"
                    )
                    use_image_resolution = gr.Checkbox(
                        label="Use Image Resolution",
                        value=False,
                        info="Use resolution from images instead of project default"
                    )

                # AI Analysis with Florence-2
                with gr.Accordion("🤖 AI Analysis (Florence-2)", open=True):
                    gr.Markdown(
                        "Automatic prompt generation with **Florence-2** via ComfyUI.\n\n"
                        "The generated descriptions will be used as prompts in the storyboard."
                    )

                    analyze_btn = gr.Button(
                        "🔍 Analyze Images with Florence-2",
                        variant="primary",
                        size="lg"
                    )
                    gr.Markdown(
                        "⚠️ **Do not refresh during analysis.** If you refresh, the job "
                        "continues in the backend but this page will lose tracking. "
                        "Check `logs/pipeline.log` for progress."
                    )
                    analyze_status = gr.Markdown("")
                    analyze_job_status = gr.Markdown(self._get_job_status_md("image_analysis"))

                    captions_display = gr.Markdown(
                        label="Generierte Prompts",
                        visible=False,
                    )

            # Step 4: Import
            with gr.Group():
                gr.Markdown("## 4️⃣ Start Import")

                import_btn = gr.Button(
                    "📥 Import Images & Create Storyboard",
                    variant="primary",
                    size="lg"
                )
                gr.Markdown(
                    "⚠️ **Do not refresh during import.** If you refresh, the job "
                    "continues in the backend but this page will lose tracking. "
                    "Check `logs/pipeline.log` for progress."
                )

                import_status = gr.Markdown("")
                import_result = gr.JSON(label="Import Result", visible=False)
                import_job_status = gr.Markdown(self._get_job_status_md("image_import"))

            # Helper function to update dropdown choices
            def update_dropdown_choices(state_data):
                if not state_data:
                    return gr.update(choices=[], value=None)
                choices = [f"{idx+1}. {img['filename']}" for idx, img in enumerate(state_data)]
                return gr.update(choices=choices, value=None)

            # Event Handlers
            scan_btn.click(
                fn=self.scan_folder,
                inputs=[folder_input],
                outputs=[scan_status, images_gallery, images_table, images_state]
            ).then(
                fn=update_dropdown_choices,
                inputs=[images_state],
                outputs=[delete_dropdown]
            )

            upload_btn.click(
                fn=self.process_uploaded_files,
                inputs=[file_upload],
                outputs=[scan_status, images_gallery, images_table, images_state]
            ).then(
                fn=update_dropdown_choices,
                inputs=[images_state],
                outputs=[delete_dropdown]
            )

            delete_btn.click(
                fn=self.delete_image,
                inputs=[delete_dropdown, images_state],
                outputs=[scan_status, images_gallery, images_table, images_state]
            ).then(
                fn=update_dropdown_choices,
                inputs=[images_state],
                outputs=[delete_dropdown]
            )

            analyze_btn.click(
                fn=self.analyze_images,
                inputs=[images_state],
                outputs=[analyze_status, captions_display, images_state, analyze_job_status]
            )

            import_btn.click(
                fn=self.import_images,
                inputs=[
                    images_state,
                    project_name_input,
                    storyboard_filename_input,
                    default_duration,
                    rename_files,
                    use_image_resolution,
                ],
                outputs=[import_status, import_result, import_job_status]
            )

            # Refresh project status on tab load
            interface.load(
                fn=self._on_tab_load,
                outputs=[project_status]
            )

        return interface

    def _on_tab_load(self):
        """Refresh project status when tab loads."""
        self.config.refresh()
        return project_status_md(self.project_manager, "📥 Image Importer")

    def scan_folder(self, folder_path: str) -> Tuple[str, List, List, List[Dict]]:
        """Scan folder for images."""
        if not folder_path or not folder_path.strip():
            return "❌ Please enter a folder path.", [], [], []

        folder_path = folder_path.strip()

        if not os.path.isdir(folder_path):
            return f"❌ Folder not found: `{folder_path}`", [], [], []

        images = self.import_service.scan_folder(folder_path)

        if not images:
            return f"⚠️ No images found in: `{folder_path}`", [], [], []

        self._scanned_images = images

        # Prepare gallery data
        gallery_data = [(img.original_path, f"{idx+1}. {img.filename}") for idx, img in enumerate(images)]

        # Prepare table data
        table_data = [
            [idx + 1, img.filename, f"{img.width}×{img.height}", img.suggested_filename_base]
            for idx, img in enumerate(images)
        ]

        # Prepare state data
        state_data = [
            {
                "original_path": img.original_path,
                "filename": img.filename,
                "width": img.width,
                "height": img.height,
                "suggested_filename_base": img.suggested_filename_base,
                "order": img.order,
            }
            for img in images
        ]

        status = f"✅ **{len(images)} images** found in `{folder_path}`"
        return status, gallery_data, table_data, state_data

    def process_uploaded_files(self, files) -> Tuple[str, List, List, List[Dict]]:
        """Process uploaded files."""
        if not files:
            return "❌ No files uploaded.", [], [], []

        images = []
        for idx, file in enumerate(files):
            try:
                img = self.import_service._load_image_metadata(file.name, idx)
                if img:
                    images.append(img)
            except Exception as e:
                logger.warning(f"Could not process uploaded file: {e}")

        if not images:
            return "⚠️ No valid images in the uploaded files.", [], [], []

        self._scanned_images = images

        # Prepare gallery data
        gallery_data = [(img.original_path, f"{idx+1}. {img.filename}") for idx, img in enumerate(images)]

        # Prepare table data
        table_data = [
            [idx + 1, img.filename, f"{img.width}×{img.height}", img.suggested_filename_base]
            for idx, img in enumerate(images)
        ]

        # Prepare state data
        state_data = [
            {
                "original_path": img.original_path,
                "filename": img.filename,
                "width": img.width,
                "height": img.height,
                "suggested_filename_base": img.suggested_filename_base,
                "order": img.order,
            }
            for img in images
        ]

        status = f"✅ **{len(images)} images** uploaded"
        return status, gallery_data, table_data, state_data

    def delete_image(self, selected_item: str, images_state: List[Dict]) -> Tuple[str, List, List, List[Dict]]:
        """Delete a selected image from the list."""
        if not selected_item:
            return "⚠️ No image selected to remove.", [], [], images_state

        if not images_state:
            return "⚠️ No images available.", [], [], []

        # Parse index from selection string (format: "1. filename.png")
        try:
            idx = int(selected_item.split(".")[0]) - 1
        except (ValueError, IndexError):
            return "❌ Invalid selection.", [], [], images_state

        if idx < 0 or idx >= len(images_state):
            return "❌ Index out of range.", [], [], images_state

        # Remove the image
        removed = images_state.pop(idx)
        logger.info(f"Removed image from import list: {removed['filename']}")

        # Update order indices
        for i, img in enumerate(images_state):
            img["order"] = i

        # Update internal list if it exists
        if self._scanned_images and idx < len(self._scanned_images):
            self._scanned_images.pop(idx)
            for i, img in enumerate(self._scanned_images):
                img.order = i

        if not images_state:
            return "✅ Image removed. No more images in the list.", [], [], []

        # Rebuild gallery and table data
        gallery_data = [(img["original_path"], f"{idx+1}. {img['filename']}") for idx, img in enumerate(images_state)]
        table_data = [
            [idx + 1, img["filename"], f"{img['width']}×{img['height']}", img["suggested_filename_base"]]
            for idx, img in enumerate(images_state)
        ]

        status = f"✅ **{removed['filename']}** removed. **{len(images_state)} images** remaining."
        return status, gallery_data, table_data, images_state

    def analyze_images(self, images_state: List[Dict]) -> Tuple[str, Any, List[Dict], str]:
        """Analyze images with Florence-2 to generate prompts."""
        if not images_state:
            return "❌ No images to analyze.", gr.update(visible=False), images_state, self._get_job_status_md("image_analysis")

        # Check if ComfyUI is available
        if not self.analyzer_service.is_available():
            return "❌ ComfyUI not reachable. Please start ComfyUI.", gr.update(visible=False), images_state, self._get_job_status_md("image_analysis")

        total = len(images_state)
        results = []
        captions_md_parts = ["### Generated Prompts\n"]
        self._job_store.set_status(
            None,
            "image_analysis",
            "running",
            message=f"Analyzing {total} images",
            metadata={"total": total},
        )

        for idx, img in enumerate(images_state):
            image_path = img["original_path"]
            filename = img["filename"]

            logger.info(f"Analyzing image {idx+1}/{total}: {filename}")

            result = self.analyzer_service.analyze_image(image_path)

            if result.success:
                # Update state with generated captions
                img["suggested_prompt"] = result.caption  # detailed caption
                img["suggested_description"] = result.description  # short caption
                captions_md_parts.append(
                    f"**{idx + 1}. {filename}**\n\n"
                    f"📝 **Description:** {result.description}\n\n"
                    f"🎨 **Prompt:** {result.caption}\n\n---\n"
                )
                results.append(True)
                logger.info(f"Captions generated for {filename}")
            else:
                captions_md_parts.append(f"**{idx + 1}. {filename}**\n\n❌ Error: {result.error}\n\n---\n")
                results.append(False)
                logger.warning(f"Failed to analyze {filename}: {result.error}")

        success_count = sum(results)
        status = f"✅ **{success_count}/{total} images** analyzed."
        if success_count < total:
            status += f" ({total - success_count} failed)"

        captions_md = "\n".join(captions_md_parts)
        if success_count == total:
            self._job_store.set_status(
                None,
                "image_analysis",
                "completed",
                message=f"Analyzed {success_count}/{total} images",
            )
        else:
            self._job_store.set_status(
                None,
                "image_analysis",
                "completed_with_issues",
                message=f"Analyzed {success_count}/{total} images",
            )
        return status, gr.update(value=captions_md, visible=True), images_state, self._get_job_status_md("image_analysis")

    def import_images(
        self,
        images_state: List[Dict],
        project_name: str,
        storyboard_filename: str,
        default_duration: float,
        rename_files: bool,
        use_image_resolution: bool,
    ) -> Tuple[str, Dict, str]:
        """Import images and create storyboard."""
        if not images_state:
            return "❌ No images to import. Please scan a folder first.", {}, self._get_job_status_md("image_import")

        project = self.project_manager.get_active_project(refresh=True)
        if not project:
            return "❌ No active project. Please create a project in the '📁 Project' tab.", {}, self._get_job_status_md("image_import")

        project_path = project.get("path")
        if not project_path:
            return "❌ Project path not found.", {}, self._get_job_status_md("image_import")

        # Reconstruct ImportedImage objects from state (including generated prompts)
        images = [
            ImportedImage(
                original_path=img["original_path"],
                filename=img["filename"],
                width=img["width"],
                height=img["height"],
                suggested_filename_base=img["suggested_filename_base"],
                suggested_prompt=img.get("suggested_prompt", ""),
                suggested_description=img.get("suggested_description", ""),
                order=img["order"],
            )
            for img in images_state
        ]

        try:
            self._job_store.set_status(
                project_path,
                "image_import",
                "running",
                message=f"Importing {len(images)} images",
                metadata={"total": len(images)},
            )
            # Step 1: Copy images to keyframes folder
            keyframes_dir = os.path.join(project_path, "keyframes")
            imported_files = self.import_service.import_images(images, keyframes_dir, rename=rename_files)

            # Step 2: Copy to selected folder as well (skip keyframe selector)
            selected_dir = os.path.join(project_path, "selected")
            os.makedirs(selected_dir, exist_ok=True)

            # Update paths for selected folder
            for img, keyframe_path in imported_files:
                selected_path = os.path.join(selected_dir, os.path.basename(keyframe_path))
                if not os.path.exists(selected_path):
                    import shutil
                    shutil.copy2(keyframe_path, selected_path)

            # Step 3: Create storyboard
            resolution = self.config.get_resolution_tuple()
            storyboard = self.import_service.create_storyboard_from_images(
                images=images,
                project_name=project_name or project.get("name", "Imported"),
                default_duration=default_duration,
                use_image_resolution=use_image_resolution,
                default_width=resolution[0],
                default_height=resolution[1],
            )

            # Step 4: Save storyboard
            storyboards_dir = os.path.join(project_path, "storyboards")
            os.makedirs(storyboards_dir, exist_ok=True)

            # Sanitize filename and add .json extension
            safe_filename = self.import_service._sanitize_filename(storyboard_filename) if storyboard_filename else f"imported_{len(images)}_shots"
            if not safe_filename.endswith(".json"):
                safe_filename = f"{safe_filename}.json"
            storyboard_path = os.path.join(storyboards_dir, safe_filename)

            storyboard_dict = self.import_service.storyboard_service.storyboard_to_dict(storyboard)
            with open(storyboard_path, "w", encoding="utf-8") as f:
                json.dump(storyboard_dict, f, indent=2, ensure_ascii=False)

            # Step 5: Create selected_keyframes.json
            # Update imported_files with selected paths
            updated_files = []
            for img, keyframe_path in imported_files:
                selected_path = os.path.join(selected_dir, os.path.basename(keyframe_path))
                # Create a fake tuple with the selected path
                updated_files.append((img, selected_path))

            selection_json = self.import_service.create_selection_json(updated_files, project_name)
            selection_path = os.path.join(selected_dir, "selected_keyframes.json")
            with open(selection_path, "w", encoding="utf-8") as f:
                json.dump(selection_json, f, indent=2, ensure_ascii=False)

            # Step 6: Set as current storyboard
            self.config.set("current_storyboard", storyboard_path)
            self.config.save()

            logger.info(f"Import complete: {len(images)} images -> {storyboard_path}")

            result = {
                "success": True,
                "images_imported": len(images),
                "storyboard_path": storyboard_path,
                "selection_path": selection_path,
                "keyframes_dir": keyframes_dir,
            }

            status_md = f"""### ✅ Import successful!

**{len(images)} images** were imported and a storyboard was created.

| Result | Path |
|--------|------|
| **Storyboard** | `{safe_filename}` |
| **Keyframes** | `{keyframes_dir}` |
| **Selection** | `selected_keyframes.json` |

#### Next Steps:
1. Open **📖 Storyboard** tab and adjust prompts
2. Open **🎥 Video Generator** tab and generate videos

*You can skip the Keyframe Generator and Selector!*
"""
            self._job_store.set_status(
                project_path,
                "image_import",
                "completed",
                message=f"Imported {len(images)} images",
            )
            return status_md, result, self._get_job_status_md("image_import")

        except Exception as e:
            logger.error(f"Import failed: {e}", exc_info=True)
            self._job_store.set_status(
                project_path,
                "image_import",
                "failed",
                message=str(e),
            )
            return f"❌ Import failed: {str(e)}", {"success": False, "error": str(e)}, self._get_job_status_md("image_import")

    def _get_job_status_md(self, job_type: str) -> str:
        """Return last job status for the given job type."""
        status = self._job_store.get_status(None, job_type)
        if not status:
            return ""
        updated = status.updated_at or "unknown time"
        message = status.message or "No details"
        return (
            f"**Last job:** `{status.status}`\n\n"
            f"{message}\n\n"
            f"_Last updated: {updated}_"
        )
