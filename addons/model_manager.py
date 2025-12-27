"""Model Manager Tool - Phase 2 UI with statistics, duplicates, exports, and advanced filters."""
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

import gradio as gr
import pandas as pd

try:
    import plotly.graph_objects as go
except ImportError:  # pragma: no cover - plotly optional in runtime
    go = None

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from addons.base_addon import BaseAddon
from addons.components import format_project_status
from infrastructure.config_manager import ConfigManager
from infrastructure.logger import get_logger
from services.model_manager import (
    WorkflowScanner,
    ModelScanner,
    ModelClassifier,
    ArchiveManager,
    ModelStatus,
    DuplicateDetector,
    StorageAnalyzer,
    WorkflowMapper,
    ReportExporter,
    ModelFilter,
    ModelDownloader,
    DownloadStatus,
)

logger = get_logger(__name__)


class ModelManagerAddon(BaseAddon):
    """Model Manager - Analyze and manage ComfyUI models"""

    def __init__(self):
        super().__init__(
            name="Model Manager",
            description="Analyze workflows, classify models, and manage model files",
            category="tools"
        )
        self.config = ConfigManager()

        # Paths
        self.comfyui_root = None
        self.workflows_dir = None
        self.models_dir = None
        self.archive_dir = None

        # Services (lazy)
        self.workflow_scanner = None
        self.model_scanner = None
        self.classifier = None
        self.archive_manager = None
        self.duplicate_detector = None
        self.storage_analyzer = None
        self.workflow_mapper = None
        self.report_exporter = None

        # Cached data
        self.last_classification = None
        self.last_duplicates = []

        # Downloader
        self.model_downloader = None

        # Workflow templates directory
        self.workflow_templates_dir = Path(__file__).parent.parent / "config" / "workflow_templates"

    def get_tab_name(self) -> str:
        return "🗂️ Models"

    # ------------------------------------------------------------------ #
    # Workflow Model Requirements (.models configurator)
    # ------------------------------------------------------------------ #
    def _get_workflow_choices(self) -> List[str]:
        """Get list of available workflows from templates directory."""
        if not self.workflow_templates_dir.exists():
            return []
        workflows = []
        for f in sorted(self.workflow_templates_dir.glob("*.json")):
            workflows.append(f.stem)
        return workflows

    def _get_models_file_path(self, workflow_name: str) -> Path:
        """Get the .models file path for a workflow."""
        return self.workflow_templates_dir / f"{workflow_name}.models"

    def _load_models_file(self, workflow_name: str) -> Tuple[str, str]:
        """Load .models file content for a workflow.

        Returns:
            Tuple of (content, status_message)
        """
        if not workflow_name:
            return "", "Wähle einen Workflow aus"

        models_path = self._get_models_file_path(workflow_name)

        if models_path.exists():
            try:
                content = models_path.read_text(encoding="utf-8")
                model_count = len([l for l in content.strip().split("\n") if l.strip() and not l.strip().startswith("#")])
                return content, f"✅ {model_count} Modell(e) konfiguriert"
            except Exception as e:
                logger.error(f"Failed to load {models_path}: {e}")
                return "", f"❌ Fehler beim Laden: {e}"
        else:
            # Create default template
            default_content = f"# Modelle für {workflow_name}\n# Pfade relativ zu ComfyUI/models/\n\n"
            return default_content, "📝 Neue .models Datei (noch nicht gespeichert)"

    def _save_models_file(self, workflow_name: str, content: str) -> str:
        """Save .models file content for a workflow."""
        if not workflow_name:
            return "❌ Kein Workflow ausgewählt"

        models_path = self._get_models_file_path(workflow_name)

        try:
            models_path.write_text(content, encoding="utf-8")
            model_count = len([l for l in content.strip().split("\n") if l.strip() and not l.strip().startswith("#")])
            logger.info(f"Saved {models_path} with {model_count} models")
            return f"✅ Gespeichert: {models_path.name} ({model_count} Modell(e))"
        except Exception as e:
            logger.error(f"Failed to save {models_path}: {e}")
            return f"❌ Fehler beim Speichern: {e}"

    def _get_available_models_for_dropdown(self) -> List[str]:
        """Get list of available models from ComfyUI for dropdown selection."""
        if not self.last_classification:
            return ["-- Zuerst 'Analyze Models' ausführen --"]

        models = []
        for status, model_list in self.last_classification.items():
            for model in model_list:
                # Format: type/filename (e.g., checkpoints/model.safetensors)
                model_path = f"{model['type']}/{model['filename']}"
                if model_path not in models:
                    models.append(model_path)

        return sorted(models) if models else ["-- Keine Modelle gefunden --"]

    def _add_model_to_content(self, workflow_name: str, current_content: str, model_to_add: str) -> Tuple[str, str]:
        """Add a model path to the .models content."""
        if not model_to_add or model_to_add.startswith("--"):
            return current_content, "⚠️ Kein Modell ausgewählt"

        # Check if already in content
        lines = current_content.strip().split("\n") if current_content.strip() else []
        for line in lines:
            if line.strip() == model_to_add:
                return current_content, f"⚠️ Modell bereits vorhanden: {model_to_add}"

        # Add to content
        if current_content.strip():
            new_content = current_content.rstrip() + "\n" + model_to_add + "\n"
        else:
            new_content = f"# Modelle für {workflow_name}\n# Pfade relativ zu ComfyUI/models/\n\n{model_to_add}\n"

        return new_content, f"✅ Hinzugefügt: {model_to_add}"

    def _remove_model_from_content(self, current_content: str, model_to_remove: str) -> Tuple[str, str]:
        """Remove a model path from the .models content."""
        if not model_to_remove or model_to_remove.startswith("--"):
            return current_content, "⚠️ Kein Modell zum Entfernen ausgewählt"

        lines = current_content.split("\n")
        new_lines = []
        removed = False

        for line in lines:
            if line.strip() == model_to_remove:
                removed = True
            else:
                new_lines.append(line)

        if removed:
            return "\n".join(new_lines), f"✅ Entfernt: {model_to_remove}"
        else:
            return current_content, f"⚠️ Modell nicht gefunden: {model_to_remove}"

    def _get_models_in_content(self, content: str) -> List[str]:
        """Get list of model paths from .models content for removal dropdown."""
        if not content:
            return ["-- Keine Modelle --"]

        models = []
        for line in content.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                models.append(line)

        return models if models else ["-- Keine Modelle --"]

    def render(self) -> gr.Blocks:
        """Render the Model Manager UI"""

        with gr.Blocks() as interface:
            # Unified header: Tab name left, no project relation
            gr.HTML(format_project_status(
                tab_name="🗂️ Model Manager",
                no_project_relation=True,
                include_remote_warning=True,
            ))

            gr.Markdown("Analyze workflows, classify models, and manage your ComfyUI model files")

            status_text = gr.Markdown("**Status:** Ready - Configure paths and click 'Analyze'")

            # Settings
            with gr.Accordion("⚙️ Settings", open=False):
                gr.Markdown("### Directory Configuration")

                comfyui_root_input = gr.Textbox(
                    label="ComfyUI Installation Path",
                    value=self.config.get_comfy_root() or "",
                    placeholder="/path/to/ComfyUI",
                    info="Root directory of your ComfyUI installation (set in ⚙️ Settings)"
                )

                workflows_dir_input = gr.Textbox(
                    label="Workflows Directory",
                    value=self.config.get("model_manager_workflows_dir") or "",
                    placeholder="/path/to/ComfyUI/user/default/workflows",
                    info="Directory containing your ComfyUI workflow JSON files"
                )

                archive_dir_input = gr.Textbox(
                    label="Archive Directory",
                    value=self.config.get("model_manager_archive_dir") or "",
                    placeholder="/path/to/model-archive",
                    info="Directory for archived (unused) models"
                )

                save_settings_btn = gr.Button("💾 Save Settings", variant="secondary")

            # Analysis & Statistics
            with gr.Accordion("📊 Analysis & Statistics", open=False):
                analyze_btn = gr.Button("🔍 Analyze Models", variant="primary", size="lg")

                stats_markdown = gr.Markdown("Click 'Analyze Models' to start")
                workflow_stats = gr.JSON(label="Workflow Statistics", value={})

                with gr.Row():
                    storage_pie = gr.Plot(label="Used vs Unused vs Missing")
                    size_by_type_bar = gr.Plot(label="Size by Model Type")

                with gr.Row():
                    largest_table = gr.Dataframe(
                        headers=["Filename", "Type", "Status", "Size", "Workflows"],
                        interactive=False,
                        label="Top 10 Largest Models",
                    )
                    histogram_table = gr.Dataframe(
                        headers=["Bucket", "Count", "Total Size"],
                        interactive=False,
                        label="Size Distribution",
                    )

            # Model Management
            with gr.Accordion("🗂️ Model Management", open=False):
                gr.Markdown("### Filter & View Models")

                with gr.Row():
                    status_filter = gr.Dropdown(
                        choices=["All", "Used", "Unused", "Missing"],
                        value="All",
                        label="Status Filter"
                    )
                    type_filter = gr.Dropdown(
                        choices=["All", "checkpoints", "loras", "vae", "controlnet", "upscale_models", "clip", "unet", "style_models", "embeddings"],
                        value="All",
                        label="Type Filter"
                    )
                    search_box = gr.Textbox(
                        label="Search",
                        placeholder="Filter by filename...",
                        scale=2
                    )

                gr.Markdown("### Advanced Filters")
                with gr.Row():
                    size_min = gr.Slider(0, 50, value=0, step=0.5, label="Min Size (GB)")
                    size_max = gr.Slider(0, 50, value=50, step=0.5, label="Max Size (GB)")
                    workflow_min = gr.Slider(0, 10, value=0, step=1, label="Min Workflow Count")
                    workflow_max = gr.Slider(0, 50, value=50, step=1, label="Max Workflow Count")
                with gr.Row():
                    date_after = gr.Textbox(label="Modified After (YYYY-MM-DD)", placeholder="Optional")
                    date_before = gr.Textbox(label="Modified Before (YYYY-MM-DD)", placeholder="Optional")
                    filename_regex = gr.Textbox(label="Filename Regex", placeholder="e.g. .*safetensors$")
                with gr.Row():
                    apply_filters_btn = gr.Button("Apply Advanced Filters", variant="secondary")
                    clear_filters_btn = gr.Button("Clear All Filters", variant="secondary")

                refresh_btn = gr.Button("🔄 Refresh List", variant="secondary")

                filter_inputs = [
                    status_filter,
                    type_filter,
                    search_box,
                    size_min,
                    size_max,
                    workflow_min,
                    workflow_max,
                    date_after,
                    date_before,
                    filename_regex,
                ]

                models_dataframe = gr.Dataframe(
                    headers=["Select", "Filename", "Type", "Status", "Size", "Workflows", "Path"],
                    datatype=["bool", "str", "str", "str", "str", "str", "str"],
                    column_count=(7, "fixed"),
                    label="Models",
                    interactive=True,
                    wrap=True
                )

                gr.Markdown("### Batch Actions")

                with gr.Row():
                    move_to_archive_btn = gr.Button(
                        "📦 Move Selected to Archive",
                        variant="secondary"
                    )
                    restore_from_archive_btn = gr.Button(
                        "↩️ Restore Selected from Archive",
                        variant="secondary"
                    )

                batch_status = gr.Markdown("")

            # Duplicate Detection
            with gr.Accordion("🔍 Duplicate Detection", open=False):
                scan_duplicates_btn = gr.Button("Scan for Duplicates", variant="secondary")
                keep_best_btn = gr.Button("Keep Best (auto-select unused duplicates)", variant="secondary")
                delete_confirm = gr.Checkbox(label="Confirm deletion/archiving of selected duplicates", value=False)
                delete_duplicates_btn = gr.Button("Delete Selected Duplicates", variant="stop")
                duplicates_status = gr.Markdown("")
                duplicates_table = gr.Dataframe(
                    headers=["Select", "Group", "Filename", "Type", "Status", "Size", "Path"],
                    datatype=["bool", "number", "str", "str", "str", "str", "str"],
                    column_count=(7, "fixed"),
                    label="Duplicate Groups",
                    interactive=True,
                    wrap=True
                )

            # Export
            with gr.Accordion("📄 Export Reports", open=False):
                export_format = gr.Dropdown(choices=["CSV", "JSON", "HTML"], value="JSON", label="Export Format")
                export_path = gr.Textbox(label="Export Path", placeholder="/tmp/model_report.json")
                export_full_btn = gr.Button("Export Full Analysis", variant="secondary")
                export_filtered_btn = gr.Button("Export Filtered Models", variant="secondary")
                export_summary_btn = gr.Button("Export Summary", variant="secondary")
                export_status = gr.Markdown("")

            # Workflow References
            with gr.Accordion("📝 Workflow References", open=False):
                workflow_model_dropdown = gr.Dropdown(choices=[], label="Select Model", interactive=True)
                workflow_details_table = gr.Dataframe(
                    headers=["Workflow", "Model Type", "Node ID", "Node Type"],
                    label="Workflow Usage",
                    interactive=False,
                )
                most_used_table = gr.Dataframe(
                    headers=["Filename", "Workflow Count"],
                    label="Most Used Models",
                    interactive=False,
                )
                single_use_table = gr.Dataframe(
                    headers=["Filename", "Workflow Count"],
                    label="Single-Use Models",
                    interactive=False,
                )
                workflow_complexity_table = gr.Dataframe(
                    headers=["Workflow", "Model Count"],
                    label="Workflow Complexity",
                    interactive=False,
                )

            # Download Missing Models
            with gr.Accordion("⬇️ Download Missing Models", open=False):
                gr.Markdown("Search and download missing models from Civitai and Huggingface")

                with gr.Row():
                    civitai_key_input = gr.Textbox(
                        label="Civitai API Key",
                        value=self.config.get_civitai_api_key(),
                        placeholder="Optional - for higher rate limits",
                        type="password",
                        scale=2
                    )
                    hf_token_input = gr.Textbox(
                        label="Huggingface Token",
                        value=self.config.get_huggingface_token(),
                        placeholder="Optional - for private repos",
                        type="password",
                        scale=2
                    )
                    parallel_downloads = gr.Slider(
                        minimum=1,
                        maximum=5,
                        value=self.config.get_max_parallel_downloads(),
                        step=1,
                        label="Parallel Downloads",
                        scale=1
                    )

                save_download_settings_btn = gr.Button("💾 Save Download Settings", variant="secondary", size="sm")

                gr.Markdown("---")

                with gr.Row():
                    search_missing_btn = gr.Button("🔍 Search Missing Models", variant="primary")
                    download_all_btn = gr.Button("⬇️ Download All Found", variant="secondary")
                    cancel_downloads_btn = gr.Button("⏹️ Cancel Downloads", variant="stop")

                gr.Markdown(
                    "⚠️ **Do not refresh during downloads.** If you refresh, downloads "
                    "continue in the backend but this page will lose tracking. "
                    "Check `logs/pipeline.log` for progress."
                )

                download_status_text = gr.Markdown("**Status:** Run 'Analyze Models' first to identify missing models")

                download_progress = gr.Progress()

                download_table = gr.Dataframe(
                    headers=["Filename", "Type", "Status", "Source", "Size", "Progress"],
                    datatype=["str", "str", "str", "str", "str", "str"],
                    column_count=(6, "fixed"),
                    label="Download Queue",
                    interactive=False,
                    wrap=True
                )

            # Workflow Model Requirements (.models Configurator)
            with gr.Accordion("📋 Workflow Model Requirements", open=False):
                gr.Markdown("""### Workflow-Modelle konfigurieren

Hier kannst du die benötigten Modelle für jeden Workflow festlegen.
Diese Informationen werden im Keyframe Generator verwendet, um die richtigen Modelle anzuzeigen.

**Format:** `model_type/filename` (z.B. `checkpoints/flux1-dev.safetensors`)
""")

                with gr.Row():
                    wf_models_workflow_dropdown = gr.Dropdown(
                        choices=self._get_workflow_choices(),
                        label="Workflow auswählen",
                        info="Workflows aus config/workflow_templates/",
                        scale=2,
                    )
                    wf_models_refresh_workflows_btn = gr.Button("🔄", scale=0, size="sm")

                wf_models_status = gr.Markdown("Wähle einen Workflow aus")

                wf_models_content = gr.TextArea(
                    label=".models Datei Inhalt",
                    placeholder="# Kommentare beginnen mit #\n# Modellpfade relativ zu ComfyUI/models/\n\ncheckpoints/model.safetensors",
                    lines=8,
                    interactive=True,
                )

                gr.Markdown("### Modell hinzufügen")
                gr.Markdown("*Tipp: Führe zuerst 'Analyze Models' aus, um verfügbare Modelle zu sehen.*")

                with gr.Row():
                    wf_models_add_dropdown = gr.Dropdown(
                        choices=self._get_available_models_for_dropdown(),
                        label="Modell aus ComfyUI hinzufügen",
                        scale=3,
                    )
                    wf_models_add_btn = gr.Button("➕ Hinzufügen", variant="secondary", scale=1)

                gr.Markdown("### Modell entfernen")

                with gr.Row():
                    wf_models_remove_dropdown = gr.Dropdown(
                        choices=["-- Keine Modelle --"],
                        label="Modell zum Entfernen auswählen",
                        scale=3,
                    )
                    wf_models_remove_btn = gr.Button("➖ Entfernen", variant="secondary", scale=1)

                with gr.Row():
                    wf_models_save_btn = gr.Button("💾 Speichern", variant="primary", size="lg")

                wf_models_save_status = gr.Markdown("")

            # Event Handlers
            save_settings_btn.click(
                fn=self.save_settings,
                inputs=[comfyui_root_input, workflows_dir_input, archive_dir_input],
                outputs=[status_text]
            )

            analyze_btn.click(
                fn=self.analyze_models,
                inputs=[comfyui_root_input, workflows_dir_input, archive_dir_input],
                outputs=[
                    status_text,
                    stats_markdown,
                    workflow_stats,
                    models_dataframe,
                    storage_pie,
                    size_by_type_bar,
                    largest_table,
                    histogram_table,
                    workflow_model_dropdown,
                ]
            )

            refresh_btn.click(
                fn=self.filter_models,
                inputs=filter_inputs,
                outputs=[models_dataframe]
            )

            for comp in [status_filter, type_filter, search_box]:
                comp.change(
                    fn=self.filter_models,
                    inputs=filter_inputs,
                    outputs=[models_dataframe]
                )

            apply_filters_btn.click(
                fn=self.filter_models,
                inputs=filter_inputs,
                outputs=[models_dataframe]
            )

            clear_filters_btn.click(
                fn=self.clear_filters,
                inputs=[status_filter, type_filter, search_box],
                outputs=[status_filter, type_filter, search_box, size_min, size_max, workflow_min, workflow_max, date_after, date_before, filename_regex, models_dataframe]
            )

            move_to_archive_btn.click(
                fn=self.move_selected_to_archive,
                inputs=[models_dataframe],
                outputs=[batch_status, models_dataframe]
            )

            restore_from_archive_btn.click(
                fn=self.restore_selected_from_archive,
                inputs=[models_dataframe],
                outputs=[batch_status, models_dataframe]
            )

            scan_duplicates_btn.click(
                fn=self.scan_duplicates,
                inputs=[],
                outputs=[duplicates_status, duplicates_table]
            )

            keep_best_btn.click(
                fn=self.keep_best_duplicates,
                inputs=[duplicates_table],
                outputs=[duplicates_table]
            )

            delete_duplicates_btn.click(
                fn=self.delete_selected_duplicates,
                inputs=[duplicates_table, delete_confirm],
                outputs=[duplicates_status, duplicates_table]
            )

            export_full_btn.click(
                fn=self.export_full_analysis,
                inputs=[export_format, export_path],
                outputs=[export_status]
            )

            export_filtered_btn.click(
                fn=self.export_filtered_models,
                inputs=[export_format, export_path, *filter_inputs],
                outputs=[export_status]
            )

            export_summary_btn.click(
                fn=self.export_summary,
                inputs=[export_format, export_path],
                outputs=[export_status]
            )

            workflow_model_dropdown.change(
                fn=self.show_workflow_usage,
                inputs=[workflow_model_dropdown],
                outputs=[workflow_details_table]
            )

            # Populate most used/single use on demand
            analyze_btn.click(
                fn=self.populate_workflow_tables,
                inputs=[],
                outputs=[most_used_table, single_use_table, workflow_complexity_table]
            )

            # Download Event Handlers
            save_download_settings_btn.click(
                fn=self.save_download_settings,
                inputs=[civitai_key_input, hf_token_input, parallel_downloads],
                outputs=[download_status_text]
            )

            search_missing_btn.click(
                fn=self.search_missing_models,
                inputs=[civitai_key_input, hf_token_input, parallel_downloads],
                outputs=[download_status_text, download_table]
            )

            download_all_btn.click(
                fn=self.download_all_found,
                inputs=[],
                outputs=[download_status_text, download_table]
            )

            cancel_downloads_btn.click(
                fn=self.cancel_downloads,
                inputs=[],
                outputs=[download_status_text]
            )

            # Workflow Model Requirements Event Handlers
            def on_workflow_select(workflow_name):
                content, status = self._load_models_file(workflow_name)
                remove_choices = self._get_models_in_content(content)
                return content, status, gr.update(choices=remove_choices, value=None)

            def on_refresh_workflows():
                choices = self._get_workflow_choices()
                logger.info(f"Workflow Model Requirements - Refresh: {len(choices)} workflows found")
                for c in choices:
                    logger.debug(f"  - {c}")
                return gr.update(choices=choices, value=None)

            def on_add_model(workflow_name, content, model_to_add):
                new_content, status = self._add_model_to_content(workflow_name, content, model_to_add)
                remove_choices = self._get_models_in_content(new_content)
                return new_content, status, gr.update(choices=remove_choices, value=None)

            def on_remove_model(content, model_to_remove):
                new_content, status = self._remove_model_from_content(content, model_to_remove)
                remove_choices = self._get_models_in_content(new_content)
                return new_content, status, gr.update(choices=remove_choices, value=None)

            def on_save_models(workflow_name, content):
                return self._save_models_file(workflow_name, content)

            def on_content_change(content):
                """Update remove dropdown when content changes."""
                remove_choices = self._get_models_in_content(content)
                return gr.update(choices=remove_choices, value=None)

            def refresh_add_dropdown():
                """Refresh add dropdown with available models after analysis."""
                return gr.update(choices=self._get_available_models_for_dropdown(), value=None)

            wf_models_workflow_dropdown.change(
                fn=on_workflow_select,
                inputs=[wf_models_workflow_dropdown],
                outputs=[wf_models_content, wf_models_status, wf_models_remove_dropdown]
            )

            wf_models_refresh_workflows_btn.click(
                fn=on_refresh_workflows,
                outputs=[wf_models_workflow_dropdown]
            )

            wf_models_add_btn.click(
                fn=on_add_model,
                inputs=[wf_models_workflow_dropdown, wf_models_content, wf_models_add_dropdown],
                outputs=[wf_models_content, wf_models_save_status, wf_models_remove_dropdown]
            )

            wf_models_remove_btn.click(
                fn=on_remove_model,
                inputs=[wf_models_content, wf_models_remove_dropdown],
                outputs=[wf_models_content, wf_models_save_status, wf_models_remove_dropdown]
            )

            wf_models_save_btn.click(
                fn=on_save_models,
                inputs=[wf_models_workflow_dropdown, wf_models_content],
                outputs=[wf_models_save_status]
            )

            wf_models_content.change(
                fn=on_content_change,
                inputs=[wf_models_content],
                outputs=[wf_models_remove_dropdown]
            )

            # Update add dropdown after analysis
            analyze_btn.click(
                fn=refresh_add_dropdown,
                outputs=[wf_models_add_dropdown]
            )

        return interface

    # ------------------------------------------------------------------ #
    # Core logic
    # ------------------------------------------------------------------ #
    def _init_services(self, comfyui_root: str, workflows_dir: str, archive_dir: str):
        """Initialize all services using provided paths."""
        self.comfyui_root = comfyui_root
        self.workflows_dir = workflows_dir
        self.archive_dir = archive_dir
        self.models_dir = os.path.join(comfyui_root, "models")

        self.workflow_scanner = WorkflowScanner(workflows_dir)
        self.model_scanner = ModelScanner(self.models_dir)
        self.classifier = ModelClassifier(self.workflow_scanner, self.model_scanner)
        self.archive_manager = ArchiveManager(archive_dir, self.models_dir)
        self.duplicate_detector = DuplicateDetector()
        self.storage_analyzer = StorageAnalyzer(self.classifier)
        self.workflow_mapper = WorkflowMapper(self.workflow_scanner)
        self.report_exporter = ReportExporter({
            "comfyui_root": comfyui_root,
            "workflows_dir": workflows_dir,
            "archive_dir": archive_dir,
        })

    def save_settings(
        self,
        comfyui_root: str,
        workflows_dir: str,
        archive_dir: str
    ) -> str:
        """Save directory settings"""
        try:
            self.comfyui_root = comfyui_root
            self.workflows_dir = workflows_dir
            self.archive_dir = archive_dir

            # Save to config file for persistence
            self.config.set("model_manager_workflows_dir", workflows_dir)
            self.config.set("model_manager_archive_dir", archive_dir)

            # Reset services to use new paths
            self.workflow_scanner = None
            self.model_scanner = None
            self.classifier = None
            self.archive_manager = None
            self.duplicate_detector = None
            self.storage_analyzer = None
            self.workflow_mapper = None
            self.report_exporter = None
            self.last_classification = None
            self.last_duplicates = []

            logger.info(f"Settings saved: ComfyUI={comfyui_root}, Workflows={workflows_dir}, Archive={archive_dir}")

            return "**✅ Settings saved successfully!** Click 'Analyze Models' to scan with new paths."

        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            return f"**❌ Error:** {str(e)}"

    def analyze_models(
        self,
        comfyui_root: str,
        workflows_dir: str,
        archive_dir: str
    ) -> Tuple[str, str, Dict, List, Any, Any, List, List, Dict]:
        """Analyze models and return statistics"""
        try:
            self._init_services(comfyui_root, workflows_dir, archive_dir)

            # Run classification
            logger.info("Starting model analysis...")
            self.last_classification = self.classifier.classify_all_models()
            stats = self.classifier.get_statistics()
            overview = self.storage_analyzer.get_storage_overview()

            # Charts
            storage_fig = self._build_storage_pie(overview)
            type_fig = self._build_type_bar(overview)

            # Tables
            largest_models = self.storage_analyzer.get_largest_models(10)
            histogram = self.storage_analyzer.get_size_distribution()["buckets"]

            # Workflow statistics
            all_workflows = self.workflow_scanner.scan_all_workflows()
            workflow_stats = {
                "total_workflows": len(all_workflows),
                "workflows_with_models": len([w for w in all_workflows.values() if w]),
                "total_model_references": sum(len(models) for models in all_workflows.values()),
            }

            # Format statistics markdown
            stats_md = f"""### 📊 Analysis Results

**Total Models:**
- ✅ **Used:** {stats['total_used']} models ({stats['used_size']})
- 📦 **Unused:** {stats['total_unused']} models ({stats['unused_size']})
- ❌ **Missing:** {stats['total_missing']} models

**Potential Savings:** {stats['potential_savings']} (by archiving unused models)

**Breakdown by Type:**
"""

            for status in ['used', 'unused', 'missing']:
                if stats['by_type'][status]:
                    stats_md += f"\n*{status.capitalize()}:* "
                    items = [f"{type_name}: {count}" for type_name, count in stats['by_type'][status].items()]
                    stats_md += ", ".join(items)

            models_data = self._get_all_models_for_table()
            model_choices = [m["filename"] for models in self.last_classification.values() for m in models]

            logger.info("Analysis complete!")

            return (
                "**✅ Analysis complete!** Use filters to view specific models.",
                stats_md,
                workflow_stats,
                models_data,
                storage_fig,
                type_fig,
                self._models_table_rows(largest_models),
                self._histogram_rows(histogram),
                gr.update(choices=sorted(set(model_choices)), value=None)
            )

        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=True)
            return (
                f"**❌ Error:** {str(e)}",
                "Analysis failed",
                {},
                [],
                None,
                None,
                [],
                [],
                gr.update(choices=[], value=None)
            )

    def filter_models(
        self,
        status_filter: str,
        type_filter: str,
        search_text: str,
        size_min_gb: float,
        size_max_gb: float,
        workflow_min: int,
        workflow_max: int,
        date_after: str,
        date_before: str,
        filename_regex: str,
    ) -> List:
        """Filter models based on criteria"""
        if self.last_classification is None:
            return []

        all_models = []
        for status, models in self.last_classification.items():
            all_models.extend(models)

        mf = ModelFilter(all_models)

        if status_filter != "All":
            status_map = {
                "Used": ModelStatus.USED,
                "Unused": ModelStatus.UNUSED,
                "Missing": ModelStatus.MISSING,
            }
            mf.by_status(status_map[status_filter])

        if type_filter != "All":
            mf.filters.append(lambda m: m["type"] == type_filter)

        if search_text:
            search_lower = search_text.lower()
            mf.filters.append(lambda m: search_lower in m["filename"].lower())

        # Advanced filters
        min_bytes = int(size_min_gb * 1024 * 1024 * 1024)
        max_bytes = int(size_max_gb * 1024 * 1024 * 1024)
        mf.by_size_range(min_bytes=min_bytes, max_bytes=max_bytes if size_max_gb > 0 else None)
        mf.by_workflow_count(min_count=workflow_min, max_count=workflow_max if workflow_max > 0 else None)

        after_dt = datetime.fromisoformat(date_after) if date_after else None
        before_dt = datetime.fromisoformat(date_before) if date_before else None
        if after_dt or before_dt:
            mf.by_modified_date(after=after_dt, before=before_dt)

        if filename_regex:
            mf.by_filename_pattern(filename_regex)

        filtered = mf.apply()
        return self._models_to_table(filtered)

    def clear_filters(self, status_filter, type_filter, search_box):
        """Reset filters to defaults."""
        self.last_duplicates = []
        return (
            gr.update(value="All"),
            gr.update(value="All"),
            gr.update(value=""),
            gr.update(value=0),
            gr.update(value=50),
            gr.update(value=0),
            gr.update(value=50),
            gr.update(value=""),
            gr.update(value=""),
            gr.update(value=""),
            self._get_all_models_for_table(),
        )

    def _get_all_models_for_table(self) -> List:
        """Get all models formatted for dataframe"""
        if self.last_classification is None:
            return []

        all_models = []
        for status, models in self.last_classification.items():
            all_models.extend(models)

        return self._models_to_table(all_models)

    def _models_to_table(self, models: List[Dict]) -> List:
        """Convert model list to table format"""
        table_data = []

        for model in models:
            model_status = model.get("status", ModelStatus.UNUSED)

            status_display = {
                ModelStatus.USED: "✅ Used",
                ModelStatus.UNUSED: "📦 Unused",
                ModelStatus.MISSING: "❌ Missing",
            }
            status = status_display.get(model_status, "Unknown")

            if model_status == ModelStatus.MISSING and self.archive_manager:
                filename = model["filename"]
                model_type = model["type"]
                if self.archive_manager.check_if_in_archive(filename, model_type):
                    status = "❌ Missing (📦 In Archive)"

            workflow_count = model.get("workflow_count", 0)
            workflow_str = f"{workflow_count} workflow(s)" if workflow_count > 0 else "None"

            table_data.append([
                False,
                model["filename"],
                model["type"],
                status,
                model.get("size") or ModelScanner._format_size(model.get("size_bytes", 0)),
                workflow_str,
                model.get("path") or "N/A"
            ])

        return table_data

    def _models_table_rows(self, models: List[Dict]) -> List:
        """Rows for largest models table (without path for compact display)."""
        rows = []
        for model in models:
            rows.append([
                model.get("filename"),
                model.get("type"),
                model.get("status", ""),
                model.get("size") or ModelScanner._format_size(model.get("size_bytes", 0)),
                model.get("workflow_count", 0),
            ])
        return rows

    def _histogram_rows(self, buckets: List[Dict]) -> List:
        return [[b["bucket"], b["count"], b["total_formatted"]] for b in buckets]

    def move_selected_to_archive(self, models_table) -> Tuple[str, List]:
        """Move selected models to archive"""
        # Handle pandas DataFrame or list
        if isinstance(models_table, pd.DataFrame):
            if models_table.empty:
                return "**⚠️ No models to process**", []
            models_list = models_table.values.tolist()
        else:
            if not models_table:
                return "**⚠️ No models to process**", models_table or []
            models_list = models_table

        selected = [row for row in models_list if row[0]]

        if not selected:
            return "**⚠️ No models selected**", models_table

        to_move = []
        for row in selected:
            filename = row[1]
            model_type = row[2]
            status = row[3]
            path = row[6]

            if path != "N/A" and status != "❌ Missing":
                to_move.append({"path": path, "type": model_type})

        if not to_move:
            return "**⚠️ No valid models to move (selected models may be missing)**", models_table

        results = self.archive_manager.batch_move_to_archive(to_move, dry_run=False)

        msg = f"**✅ Moved {len(results['success'])} model(s) to archive**"
        if results['failed']:
            msg += f"\n\n**⚠️ Failed:** {len(results['failed'])} model(s)\n"
            msg += "\n".join(results['failed'][:5])

        refreshed_table = self.filter_models("All", "All", "", 0, 50, 0, 50, "", "", "")

        return msg, refreshed_table

    def restore_selected_from_archive(self, models_table) -> Tuple[str, List]:
        """Restore selected models from archive"""
        # Handle pandas DataFrame or list
        if isinstance(models_table, pd.DataFrame):
            if models_table.empty:
                return "**⚠️ No models to process**", []
            models_list = models_table.values.tolist()
        else:
            if not models_table:
                return "**⚠️ No models to process**", models_table or []
            models_list = models_table

        selected = [row for row in models_list if row[0]]

        if not selected:
            return "**⚠️ No models selected**", models_table

        to_restore = []
        for row in selected:
            filename = row[1]
            model_type = row[2]
            status = row[3]

            if status.startswith("❌ Missing"):
                if self.archive_manager.check_if_in_archive(filename, model_type):
                    to_restore.append({"filename": filename, "type": model_type})

        if not to_restore:
            return "**⚠️ No models to restore (models must be missing and in archive)**", models_table

        results = self.archive_manager.batch_restore_from_archive(to_restore, dry_run=False)

        msg = f"**✅ Restored {len(results['success'])} model(s) from archive**"
        if results['failed']:
            msg += f"\n\n**⚠️ Failed:** {len(results['failed'])} model(s)\n"
            msg += "\n".join(results['failed'][:5])

        refreshed_table = self.filter_models("All", "All", "", 0, 50, 0, 50, "", "", "")

        return msg, refreshed_table

    # ------------------------------------------------------------------ #
    # Duplicates
    # ------------------------------------------------------------------ #
    def scan_duplicates(self) -> Tuple[str, List]:
        if not self.last_classification:
            return "**⚠️ Run analysis first**", []

        # Build models_by_type from classifier output (used + unused only)
        models_by_type = {}
        for status in [ModelStatus.USED, ModelStatus.UNUSED]:
            for model in self.last_classification.get(status, []):
                models_by_type.setdefault(model["type"], []).append(model)

        duplicates = self.duplicate_detector.find_duplicates(models_by_type)
        self.last_duplicates = duplicates

        table = self._duplicates_to_table(duplicates)
        msg = f"Found {len(duplicates)} duplicate group(s)"
        return f"**✅ Duplicate scan complete. {msg}.**", table

    def _duplicates_to_table(self, duplicates: List[Dict]) -> List:
        rows = []
        for idx, group in enumerate(duplicates, start=1):
            for file in group["files"]:
                suggested = group.get("suggested_keep")
                rows.append([
                    False,
                    idx,
                    file.get("filename"),
                    file.get("type"),
                    file.get("status"),
                    ModelScanner._format_size(file.get("size_bytes", 0)),
                    file.get("path")
                ])
                # Flag suggested keep entry
                if suggested and suggested.get("path") == file.get("path"):
                    rows[-1][0] = False
        return rows

    def keep_best_duplicates(self, table: List) -> List:
        """Auto-select duplicates to delete (keep used)."""
        if not self.last_duplicates:
            return table

        updated = []
        for row in table:
            selected, group_idx, filename, model_type, status, size, path = row
            group = self.last_duplicates[int(group_idx) - 1]
            suggested = group.get("suggested_keep")
            # Select if not suggested keep and status is unused
            # Status is a display string like "📦 Unused", not the enum
            is_unused = "Unused" in str(status)
            should_select = suggested and suggested.get("path") != path and is_unused
            updated.append([
                bool(should_select),
                group_idx,
                filename,
                model_type,
                status,
                size,
                path
            ])
        return updated

    def delete_selected_duplicates(self, table: List, confirm: bool) -> Tuple[str, List]:
        if not table:
            return "**⚠️ No duplicates to process**", table
        if not confirm:
            return "**⚠️ Please confirm deletion/archiving**", table

        selected = [row for row in table if row[0]]
        if not selected:
            return "**⚠️ No duplicates selected**", table

        failures = []
        success = []
        for row in selected:
            _, _, filename, model_type, status, _, path = row
            if not path or path == "N/A":
                failures.append(f"{filename}: missing path")
                continue
            ok, msg = self.archive_manager.move_to_archive(path, model_type, dry_run=False)
            if ok:
                success.append(filename)
            else:
                failures.append(f"{filename}: {msg}")

        refreshed = [r for r in table if r[1] not in {row[1] for row in selected}]
        message = f"**✅ Archived {len(success)} duplicate(s)**"
        if failures:
            message += f"\n\n**⚠️ Failed:** {len(failures)}\n" + "\n".join(failures[:5])
        return message, refreshed

    # ------------------------------------------------------------------ #
    # Exports
    # ------------------------------------------------------------------ #
    def export_full_analysis(self, fmt: str, path: str) -> str:
        if not self.last_classification:
            return "**⚠️ Run analysis first**"
        data = []
        for models in self.last_classification.values():
            data.extend(models)
        return self._export_data(fmt, path, data)

    def export_filtered_models(
        self,
        fmt: str,
        path: str,
        status_filter: str,
        type_filter: str,
        search_text: str,
        size_min: float,
        size_max: float,
        workflow_min: int,
        workflow_max: int,
        date_after: str,
        date_before: str,
        filename_regex: str,
    ) -> str:
        filtered_table = self.filter_models(
            status_filter,
            type_filter,
            search_text,
            size_min,
            size_max,
            workflow_min,
            workflow_max,
            date_after,
            date_before,
            filename_regex,
        )
        # Convert table back to dicts for export
        data = []
        for row in filtered_table:
            data.append({
                "filename": row[1],
                "type": row[2],
                "status": row[3],
                "size": row[4],
                "workflows": row[5],
                "path": row[6],
            })
        return self._export_data(fmt, path, data)

    def export_summary(self, fmt: str, path: str) -> str:
        if not self.last_classification:
            return "**⚠️ Run analysis first**"
        stats = self.classifier.get_statistics()
        if fmt == "CSV":
            path = self.report_exporter.export_to_csv([stats], path)
        elif fmt == "JSON":
            path = self.report_exporter.export_summary(stats, path)
        else:
            path = self.report_exporter.export_to_html([stats], path, title="Model Summary")
        return f"**✅ Exported summary to {path}**"

    def _export_data(self, fmt: str, path: str, data: List[Dict]) -> str:
        try:
            if fmt == "CSV":
                export_path = self.report_exporter.export_to_csv(data, path)
            elif fmt == "HTML":
                export_path = self.report_exporter.export_to_html(data, path)
            else:
                export_path = self.report_exporter.export_to_json(data, path)
            return f"**✅ Exported to {export_path}**"
        except Exception as e:
            logger.error(f"Export failed: {e}")
            return f"**❌ Export failed:** {e}"

    # ------------------------------------------------------------------ #
    # Workflow references
    # ------------------------------------------------------------------ #
    def show_workflow_usage(self, filename: str) -> List:
        if not filename or not self.workflow_mapper:
            return []
        details = self.workflow_mapper.get_model_usage_details(filename)
        return [[d["workflow"], d["model_type"], d["node_id"], d["node_type"]] for d in details]

    def populate_workflow_tables(self):
        if not self.workflow_mapper:
            return [], [], []
        most_used = self.workflow_mapper.get_most_used_models()
        least_used = self.workflow_mapper.get_least_used_models()
        complexity = self.workflow_mapper.get_workflow_complexity()

        most_used_rows = [[m["filename"], m["workflow_count"]] for m in most_used]
        least_used_rows = [[m["filename"], m["workflow_count"]] for m in least_used]
        complexity_rows = [[wf, count] for wf, count in complexity.items()]
        return most_used_rows, least_used_rows, complexity_rows

    # ------------------------------------------------------------------ #
    # Visualization helpers
    # ------------------------------------------------------------------ #
    def _build_storage_pie(self, overview: Dict):
        if go is None:
            return None
        fig = go.Figure(data=[go.Pie(
            labels=["Used", "Unused", "Missing"],
            values=[overview["totals"]["used"], overview["totals"]["unused"], overview["counts"]["missing"]],
            hole=0.3
        )])
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=10))
        return fig

    def _build_type_bar(self, overview: Dict):
        if go is None:
            return None
        labels = []
        used = []
        unused = []
        for t, data in overview["by_type"].items():
            labels.append(t)
            used.append(data["used"]["size_bytes"])
            unused.append(data["unused"]["size_bytes"])

        fig = go.Figure()
        fig.add_bar(x=labels, y=used, name="Used")
        fig.add_bar(x=labels, y=unused, name="Unused")
        fig.update_layout(barmode="stack", margin=dict(l=10, r=10, t=10, b=10))
        return fig

    # ------------------------------------------------------------------ #
    # Download functionality
    # ------------------------------------------------------------------ #
    def save_download_settings(
        self,
        civitai_key: str,
        hf_token: str,
        parallel_downloads: int
    ) -> str:
        """Save download settings to config"""
        try:
            self.config.set_civitai_api_key(civitai_key)
            self.config.set_huggingface_token(hf_token)
            self.config.set_max_parallel_downloads(int(parallel_downloads))

            # Reinitialize downloader with new settings if it exists
            if self.model_downloader:
                self.model_downloader = ModelDownloader(
                    models_root=self.models_dir,
                    civitai_api_key=civitai_key,
                    huggingface_token=hf_token,
                    max_parallel_downloads=int(parallel_downloads),
                )

            return "**✅ Download settings saved!**"
        except Exception as e:
            logger.error(f"Failed to save download settings: {e}")
            return f"**❌ Error:** {str(e)}"

    def _init_downloader(self, civitai_key: str, hf_token: str, parallel: int):
        """Initialize or reinitialize the model downloader"""
        if not self.models_dir:
            raise ValueError("Models directory not set. Run 'Analyze Models' first.")

        self.model_downloader = ModelDownloader(
            models_root=self.models_dir,
            civitai_api_key=civitai_key,
            huggingface_token=hf_token,
            max_parallel_downloads=int(parallel),
        )

    def search_missing_models(
        self,
        civitai_key: str,
        hf_token: str,
        parallel_downloads: int
    ) -> Tuple[str, List]:
        """Search for all missing models on Civitai and Huggingface"""
        if not self.last_classification:
            return "**⚠️ Run 'Analyze Models' first to identify missing models**", []

        missing_models = self.last_classification.get(ModelStatus.MISSING, [])
        if not missing_models:
            return "**✅ No missing models found!**", []

        try:
            # Initialize downloader
            self._init_downloader(civitai_key, hf_token, parallel_downloads)

            # Search for all missing models
            logger.info(f"Searching for {len(missing_models)} missing models...")

            for model in missing_models:
                self.model_downloader.add_to_queue(
                    filename=model["filename"],
                    model_type=model["type"],
                    auto_search=True
                )

            # Get results
            stats = self.model_downloader.get_statistics()
            queue_status = self.model_downloader.get_queue_status()

            # Format table
            table_data = self._download_queue_to_table(queue_status)

            status_msg = f"""**✅ Search complete!**

- **Found:** {stats['found']} models
- **Not Found:** {stats['not_found']} models
- **Pending:** {stats['pending']} models

Click 'Download All Found' to start downloading."""

            return status_msg, table_data

        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            return f"**❌ Error:** {str(e)}", []

    def download_all_found(self) -> Tuple[str, List]:
        """Download all models that were found"""
        if not self.model_downloader:
            return "**⚠️ Run 'Search Missing Models' first**", []

        stats = self.model_downloader.get_statistics()
        if stats['found'] == 0:
            return "**⚠️ No models found to download**", []

        try:
            logger.info(f"Starting download of {stats['found']} models...")

            # Start downloads in background thread
            import threading

            def run_downloads():
                self.model_downloader.start_downloads()

            download_thread = threading.Thread(target=run_downloads, daemon=True)
            download_thread.start()

            # Wait a moment for downloads to start
            import time
            time.sleep(1)

            # Get updated status
            queue_status = self.model_downloader.get_queue_status()
            table_data = self._download_queue_to_table(queue_status)

            new_stats = self.model_downloader.get_statistics()
            status_msg = f"""**⬇️ Downloads started!**

- **Downloading:** {new_stats['downloading']}
- **Completed:** {new_stats['completed']}
- **Failed:** {new_stats['failed']}

Downloads are running in the background. Refresh to see progress."""

            return status_msg, table_data

        except Exception as e:
            logger.error(f"Download failed: {e}", exc_info=True)
            return f"**❌ Error:** {str(e)}", []

    def cancel_downloads(self) -> str:
        """Cancel all running downloads"""
        if not self.model_downloader:
            return "**⚠️ No downloads to cancel**"

        try:
            self.model_downloader.cancel_downloads()
            return "**⏹️ Downloads cancelled**"
        except Exception as e:
            logger.error(f"Cancel failed: {e}")
            return f"**❌ Error:** {str(e)}"

    def _download_queue_to_table(self, queue_status: Dict) -> List:
        """Convert download queue to table format"""
        table_data = []

        status_icons = {
            "pending": "⏳",
            "searching": "🔍",
            "found": "✅",
            "not_found": "❌",
            "downloading": "⬇️",
            "completed": "✅",
            "failed": "❌",
            "cancelled": "⏹️",
        }

        for task_id, task in queue_status.items():
            status = task.get("status", "pending")
            icon = status_icons.get(status, "")
            progress = task.get("progress", 0)
            progress_str = f"{progress:.0f}%" if status == "downloading" else ""

            table_data.append([
                task.get("filename", ""),
                task.get("model_type", ""),
                f"{icon} {status}",
                task.get("source", "").upper() if task.get("source") else "-",
                task.get("size", "-"),
                progress_str,
            ])

        return table_data
