"""Keyframe Selector Addon - Phase 2 of CINDERGRACE Pipeline"""
import os
import sys
import json
from typing import Dict, List, Tuple, Any

import gradio as gr

# Ensure parent directory is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from addons.base_addon import BaseAddon
from infrastructure.config_manager import ConfigManager
from infrastructure.project_store import ProjectStore
from infrastructure.logger import get_logger
from infrastructure.error_handler import handle_errors
from domain.storyboard_service import StoryboardService
from services.selection_service import SelectionService

logger = get_logger(__name__)


class KeyframeSelectorAddon(BaseAddon):
    """Select best keyframe variants per shot and export selections"""

    def __init__(self):
        super().__init__(
            name="Keyframe Selector",
            description="Review generated keyframes and pick the best variant per shot"
        )
        self.config = ConfigManager()
        self.project_manager = ProjectStore(self.config)
        self.selection_service = SelectionService(self.project_manager)

    def get_tab_name(self) -> str:
        return "✅ Keyframe Selector"

    def _auto_load_storyboard(self) -> Dict[str, Any]:
        """Auto-load storyboard during render() - returns initial UI data."""
        defaults = {
            "storyboard_json": "{}",
            "status": "**Status:** Storyboard noch nicht geladen",
            "shot_ids": [],
            "storyboard_state": {},
            "summary": "Noch keine Keyframes ausgewählt.",
            "preview": {},
            "selections_state": {},
            "variants_state": {},
        }

        try:
            self.config.refresh()
            storyboard_file = self.config.get_current_storyboard()
            if not storyboard_file:
                logger.debug("Keyframe Selector: No storyboard configured for auto-load")
                return defaults

            storyboard, error = self._load_storyboard_model(storyboard_file)
            if error or not storyboard:
                logger.warning(f"Keyframe Selector: Could not auto-load storyboard: {error}")
                return defaults

            shots = storyboard.shots
            shot_ids = [shot.shot_id or f"{idx+1:03d}" for idx, shot in enumerate(shots)]
            project_name = storyboard.project or "Unbekanntes Projekt"

            defaults["storyboard_json"] = json.dumps(storyboard.raw, indent=2)
            defaults["status"] = f"**✅ Storyboard geladen:** {project_name} – {len(shots)} Shots"
            defaults["shot_ids"] = shot_ids
            defaults["storyboard_state"] = storyboard.raw
            defaults["summary"] = self._format_selection_summary({}, storyboard.raw)
            defaults["preview"] = self._build_preview_payload(storyboard.raw, {})

            logger.info(f"Keyframe Selector: Auto-loaded storyboard '{storyboard_file}' with {len(shots)} shots")
        except Exception as e:
            logger.error(f"Keyframe Selector: Error in auto-load: {e}", exc_info=True)

        return defaults

    def render(self) -> gr.Blocks:
        """Render selector UI"""
        # Auto-load storyboard during render (not via interface.load)
        auto_loaded = self._auto_load_storyboard()

        storyboard_state = gr.State(auto_loaded["storyboard_state"])
        variants_state = gr.State(auto_loaded["variants_state"])
        selections_state = gr.State(auto_loaded["selections_state"])

        with gr.Blocks() as interface:
            gr.Markdown("# ✅ Keyframe Selector - Phase 2")
            gr.Markdown(
                "Lade ein Storyboard, überprüfe alle Varianten der generierten Keyframes "
                "und speichere die beste Auswahl pro Shot."
            )

            with gr.Group():
                gr.Markdown("## 🗂️ Projekt")
                project_status = gr.Markdown(self._project_status_md())
                refresh_project_btn = gr.Button("🔄 Projektstatus aktualisieren", size="sm")

            with gr.Accordion("📁 Storyboard", open=False):
                storyboard_info_md = gr.Markdown(self._current_storyboard_md())
                load_storyboard_btn = gr.Button("📖 Storyboard laden (aus Projekt-Tab)", variant="secondary")

                storyboard_info = gr.Code(
                    label="Storyboard-Details",
                    language="json",
                    value=auto_loaded["storyboard_json"],
                    lines=14,
                    max_lines=20,
                    interactive=False,
                )

            status_text = gr.Markdown(auto_loaded["status"])

            # Main content: Left sidebar (20%) + Right content (80%)
            with gr.Row():
                # Left sidebar - Shot selection and actions
                with gr.Column(scale=1, min_width=200):
                    gr.Markdown("### 🎬 Shot-Auswahl")
                    refresh_shot_btn = gr.Button("🗂️ Keyframes aktualisieren", variant="secondary", size="sm")
                    shot_dropdown = gr.Dropdown(
                        choices=auto_loaded["shot_ids"],
                        value=auto_loaded["shot_ids"][0] if auto_loaded["shot_ids"] else None,
                        label="Shot auswählen",
                        info="Wähle einen Shot",
                        interactive=True,
                    )
                    gr.Markdown("---")
                    save_selection_btn = gr.Button("💾 Auswahl speichern", variant="primary")
                    clear_selection_btn = gr.Button("🧹 Auswahl entfernen", variant="secondary")

                # Right content - Shot overview and variants
                with gr.Column(scale=4):
                    gr.Markdown("### 🖼️ Shot-Überblick")
                    shot_info = gr.Markdown("Kein Shot ausgewählt.")

                    keyframe_gallery = gr.Gallery(
                        label="Varianten",
                        show_label=True,
                        columns=4,
                        height="auto",
                        object_fit="contain",
                    )

                    variant_radio = gr.Radio(
                        choices=[],
                        label="Beste Variante auswählen",
                        info="Wähle die beste Variante für diesen Shot",
                    )

            with gr.Group():
                gr.Markdown("## 📊 Auswahlübersicht & Export")
                selection_summary = gr.Markdown(auto_loaded["summary"])
                selection_json = gr.JSON(label="Export-Vorschau", value=auto_loaded["preview"])

                export_btn = gr.Button("📤 Auswahl exportieren", variant="primary")

            # Event wiring
            load_storyboard_btn.click(
                fn=self.load_storyboard_from_config,
                outputs=[
                    storyboard_info,
                    status_text,
                    shot_dropdown,
                    storyboard_state,
                    selection_summary,
                    selection_json,
                    selections_state,
                    variants_state,
                ],
            )

            shot_dropdown.change(
                fn=self.load_shot_preview,
                inputs=[storyboard_state, shot_dropdown, variants_state, selections_state],
                outputs=[shot_info, keyframe_gallery, variant_radio, status_text, variants_state],
            )

            refresh_shot_btn.click(
                fn=self.load_shot_preview,
                inputs=[storyboard_state, shot_dropdown, variants_state, selections_state],
                outputs=[shot_info, keyframe_gallery, variant_radio, status_text, variants_state],
            )

            save_selection_btn.click(
                fn=self.save_selection,
                inputs=[shot_dropdown, variant_radio, storyboard_state, variants_state, selections_state],
                outputs=[status_text, selection_summary, selection_json, selections_state],
            )

            clear_selection_btn.click(
                fn=self.clear_selection,
                inputs=[shot_dropdown, storyboard_state, selections_state],
                outputs=[status_text, selection_summary, selection_json, selections_state],
            )

            export_btn.click(
                fn=self.export_selections,
                inputs=[storyboard_state, selections_state],
                outputs=[status_text, selection_json],
            )

            refresh_project_btn.click(
                fn=lambda: self._project_status_md(),
                outputs=[project_status],
            )

            # Note: Auto-load is now done synchronously during render() via _auto_load_storyboard()
            # The interface.load() event only fires on full page load, not on tab switch

        return interface

    @handle_errors("Storyboard laden fehlgeschlagen", return_tuple=True)
    def _load_storyboard_model(self, storyboard_file: str):
        storyboard = StoryboardService.load_from_config(self.config, filename=storyboard_file)
        StoryboardService.apply_resolution_from_config(storyboard, self.config)
        storyboard.raw["storyboard_file"] = storyboard_file
        return storyboard

    def load_storyboard(self, storyboard_file: str) -> Tuple[str, str, Any, Dict[str, Any], str, Dict[str, Any], Dict[str, Any], Dict[str, Dict[str, Any]]]:
        if not storyboard_file or storyboard_file.startswith("No storyboard"):
            empty_summary = self._format_selection_summary({}, {})
            empty_preview = self._build_preview_payload({}, {})
            return (
                "{}",
                "**❌ Fehler:** Keine Storyboard-Datei ausgewählt",
                gr.update(choices=[]),
                {},
                empty_summary,
                empty_preview,
                {},
                {},
            )

        storyboard, error = self._load_storyboard_model(storyboard_file)
        if error:
            empty_summary = self._format_selection_summary({}, {})
            empty_preview = self._build_preview_payload({}, {})
            return (
                "{}",
                error,
                gr.update(choices=[]),
                {},
                empty_summary,
                empty_preview,
                {},
                {},
            )

        shots = storyboard.shots
        shot_ids = [shot.shot_id or f"{idx+1:03d}" for idx, shot in enumerate(shots)]
        dropdown_update = gr.update(choices=shot_ids, value=shot_ids[0] if shot_ids else None)
        project_name = storyboard.project or "Unbekanntes Projekt"
        status = f"**✅ Storyboard geladen:** {project_name} – {len(shots)} Shots"
        storyboard_json = json.dumps(storyboard.raw, indent=2)
        summary = self._format_selection_summary({}, storyboard.raw)
        preview = self._build_preview_payload(storyboard.raw, {})

        return (
            storyboard_json,
            status,
            dropdown_update,
            storyboard.raw,
            summary,
            preview,
            {},
            {},
        )

    def load_storyboard_from_config(
        self
    ) -> Tuple[str, str, Any, Dict[str, Any], str, Dict[str, Any], Dict[str, Any], Dict[str, Dict[str, Any]]]:
        """Wrapper to load storyboard selected in project tab.

        Refactored to use centralized StoryboardService.
        """
        self.config.refresh()
        storyboard_file = self.config.get_current_storyboard()
        if not storyboard_file:
            logger.warning("No storyboard selected in project tab")
            empty_summary = self._format_selection_summary({}, {})
            empty_preview = self._build_preview_payload({}, {})
            return (
                "{}",
                "**❌ Fehler:** Kein Storyboard gesetzt. Bitte im Tab '📁 Projekt' auswählen.",
                gr.update(choices=[]),
                {},
                empty_summary,
                empty_preview,
                {},
                {},
            )
        return self.load_storyboard(storyboard_file)

    def load_shot_preview(
        self,
        storyboard_state: Dict[str, Any],
        shot_id: str,
        variants_state: Dict[str, Dict[str, Dict[str, Any]]],
        selections_state: Dict[str, Dict[str, Any]],
    ) -> Tuple[str, List[Tuple[str, str]], Any, str, Dict[str, Dict[str, Dict[str, Any]]]]:
        """Load gallery + variant list for selected shot"""
        if not storyboard_state:
            return "Bitte zuerst ein Storyboard laden.", [], gr.update(choices=[]), "**❌ Fehler:** Kein Storyboard", variants_state

        project = self.project_manager.get_active_project(refresh=True)
        if not project:
            return (
                "Kein aktives Projekt ausgewählt.",
                [],
                gr.update(choices=[]),
                "**❌ Fehler:** Bitte zuerst im Tab '📁 Projekt' ein Projekt wählen.",
                variants_state,
            )

        shot = self._get_shot_by_id(storyboard_state, shot_id)
        if not shot:
            return f"Shot `{shot_id}` nicht gefunden.", [], gr.update(choices=[]), "**❌ Fehler:** Ungültiger Shot", variants_state

        filename_base = shot.get("filename_base", shot_id)
        keyframes = self.selection_service.collect_keyframes(project, filename_base)

        if not keyframes:
            info = self._format_shot_markdown(shot, available=False)
            status = f"**⚠️ Hinweis:** Keine Keyframes für `{filename_base}` gefunden."
            variants_state = variants_state or {}
            variants_state[shot_id] = {}
            return info, [], gr.update(choices=[], value=None), status, variants_state

        # Gradio 4.x format: list of paths (strings)
        gallery_items = [item["path"] for item in keyframes]

        options_map = {item["label"]: item for item in keyframes}
        variants_state = variants_state or {}
        variants_state[shot_id] = options_map

        existing_selection = selections_state.get(shot_id) if selections_state else None
        default_value = None
        if existing_selection:
            label_match = next(
                (label for label, data in options_map.items() if data["filename"] == existing_selection["selected_file"]),
                None,
            )
            default_value = label_match

        info = self._format_shot_markdown(shot, available=True, total=len(keyframes))
        status = f"**ℹ️ {shot_id}:** {len(keyframes)} Varianten geladen."

        return info, gallery_items, gr.update(choices=list(options_map.keys()), value=default_value), status, variants_state

    def save_selection(
        self,
        shot_id: str,
        selected_option: str,
        storyboard_state: Dict[str, Any],
        variants_state: Dict[str, Dict[str, Dict[str, Any]]],
        selections_state: Dict[str, Dict[str, Any]],
    ) -> Tuple[str, str, Dict[str, Any], Dict[str, Dict[str, Any]]]:
        """Persist selected variant for a shot"""
        current_summary = self._format_selection_summary(selections_state, storyboard_state)
        current_preview = self._build_preview_payload(storyboard_state, selections_state)
        if not shot_id:
            return "**❌ Fehler:** Kein Shot ausgewählt.", current_summary, current_preview, selections_state

        options = (variants_state or {}).get(shot_id, {})
        if not options:
            return f"**❌ Fehler:** Für `{shot_id}` sind keine Varianten geladen.", current_summary, current_preview, selections_state

        # Check if user selected a variant
        if not selected_option:
            return (
                "**⚠️ Hinweis:** Bitte zuerst eine Variante aus der Liste oben auswählen, "
                "bevor du die Auswahl speicherst.",
                current_summary,
                current_preview,
                selections_state,
            )

        choice = options.get(selected_option)
        if not choice:
            return (
                "**⚠️ Hinweis:** Die gewählte Variante ist ungültig. "
                "Bitte eine Variante aus der Liste 'Beste Variante auswählen' wählen.",
                current_summary,
                current_preview,
                selections_state,
            )

        shot = self._get_shot_by_id(storyboard_state, shot_id) or {}

        selection_record = {
            "shot_id": shot_id,
            "filename_base": shot.get("filename_base", shot_id),
            "selected_variant": choice["variant"],
            "selected_file": choice["filename"],
            "source_path": choice["path"],
        }

        selections_state = selections_state or {}
        selections_state[shot_id] = selection_record

        summary = self._format_selection_summary(selections_state, storyboard_state)
        preview = self._build_preview_payload(storyboard_state, selections_state)

        status = f"**✅ Gespeichert:** Shot {shot_id} → {choice['filename']}"
        return status, summary, preview, selections_state

    def clear_selection(
        self,
        shot_id: str,
        storyboard_state: Dict[str, Any],
        selections_state: Dict[str, Dict[str, Any]],
    ) -> Tuple[str, str, Dict[str, Any], Dict[str, Dict[str, Any]]]:
        """Remove a saved selection for the active shot"""
        if not shot_id:
            return (
                "**❌ Fehler:** Kein Shot ausgewählt.",
                self._format_selection_summary(selections_state, storyboard_state),
                self._build_preview_payload(storyboard_state, selections_state),
                selections_state,
            )

        if selections_state and shot_id in selections_state:
            selections_state.pop(shot_id, None)
            status = f"**🧹 Entfernt:** Auswahl für Shot {shot_id} gelöscht."
        else:
            status = f"**ℹ️ Hinweis:** Keine gespeicherte Auswahl für Shot {shot_id}."

        summary = self._format_selection_summary(selections_state, storyboard_state)
        preview = self._build_preview_payload(storyboard_state, selections_state)
        return status, summary, preview, selections_state

    def export_selections(
        self,
        storyboard_state: Dict[str, Any],
        selections_state: Dict[str, Dict[str, Any]],
    ) -> Tuple[str, Dict[str, Any]]:
        """Write JSON export + copy files into the active project/selected folder"""
        if not storyboard_state:
            return "**❌ Fehler:** Bitte zuerst ein Storyboard laden.", {}

        if not selections_state:
            return "**❌ Fehler:** Keine Auswahlen gespeichert.", {}

        project = self.project_manager.get_active_project(refresh=True)
        if not project:
            return "**❌ Fehler:** Kein aktives Projekt. Bitte im Tab '📁 Projekt' auswählen.", {}

        export_payload = self.selection_service.export_selections(project, storyboard_state, selections_state)
        copied = export_payload.pop("_copied", 0)
        export_path = export_payload.pop("_path", "n/a")
        status = (
            f"**✅ Export abgeschlossen:** {len(export_payload.get('selections', []))} Shots, "
            f"{copied} Dateien kopiert → `{export_path}`"
        )
        return status, export_payload

    def _format_shot_markdown(self, shot: Dict[str, Any], available: bool, total: int = 0) -> str:
        """Readable shot metadata block"""
        lines = [
            f"### Shot {shot.get('shot_id', 'N/A')} – {shot.get('filename_base', 'ohne Dateiname')}",
            f"- **Beschreibung:** {shot.get('description', 'Keine Beschreibung')}",
            f"- **Prompt:** {shot.get('prompt', 'Kein Prompt')[:160]}{'…' if len(shot.get('prompt', '')) > 160 else ''}",
            f"- **Auflösung:** {shot.get('width', 1024)}×{shot.get('height', 576)}",
            f"- **Kamera:** {shot.get('camera_movement', 'n/a')}",
        ]
        if available:
            lines.append(f"- **Varianten gefunden:** {total}")
        else:
            lines.append("- **Varianten gefunden:** 0")
        return "\n".join(lines)

    def _project_status_md(self) -> str:
        project = self.project_manager.get_active_project(refresh=True)
        if not project:
            return "**❌ Kein aktives Projekt:** Bitte im Tab `📁 Projekt` anlegen oder auswählen."
        return (
            f"**Aktives Projekt:** {project.get('name')} (`{project.get('slug')}`)\n"
            f"- Pfad: `{project.get('path')}`"
        )

    def _get_available_storyboards(self) -> List[str]:
        """List storyboard files from config/ and active project folders"""
        directories = self._storyboard_search_dirs()
        storyboards: List[str] = []
        seen = set()

        for directory in directories:
            if not os.path.exists(directory):
                continue
            for filename in sorted(os.listdir(directory)):
                if not filename.endswith('.json'):
                    continue
                if 'storyboard' not in filename.lower():
                    continue
                full_path = os.path.join(directory, filename)
                if full_path in seen:
                    continue
                storyboards.append(full_path)
                seen.add(full_path)

        return storyboards if storyboards else ["No storyboards found - add JSON files to config/ or project folder"]

    def _get_default_storyboard(self) -> str:
        storyboards = self._get_available_storyboards()
        return storyboards[0] if storyboards else None

    def _storyboard_search_dirs(self) -> List[str]:
        """Return directories that may contain storyboard files."""
        dirs: List[str] = []
        config_dir = self.config.config_dir
        if config_dir and os.path.isdir(config_dir):
            dirs.append(config_dir)

        project = self.project_manager.get_active_project(refresh=True)
        if project:
            project_root = project.get("path")
            for candidate in (project_root, os.path.join(project_root, "storyboards")):
                if candidate and os.path.isdir(candidate):
                    dirs.append(candidate)

        # remove duplicates while preserving order
        unique_dirs: List[str] = []
        for directory in dirs:
            if directory not in unique_dirs:
                unique_dirs.append(directory)
        return unique_dirs

    def _get_shot_by_id(self, storyboard: Dict[str, Any], shot_id: str) -> Dict[str, Any]:
        for shot in storyboard.get("shots", []):
            if shot.get("shot_id") == shot_id:
                return shot
        return {}

    def _current_storyboard_md(self) -> str:
        self.config.refresh()
        storyboard = self.config.get_current_storyboard()
        if not storyboard:
            return "**❌ Kein Storyboard gesetzt:** Bitte im Tab `📁 Projekt` auswählen."
        return f"**Storyboard:** `{storyboard}` (aus Tab 📁 Projektverwaltung)"

    def _format_selection_summary(
        self, selections: Dict[str, Dict[str, Any]], storyboard: Dict[str, Any]
    ) -> str:
        if not selections:
            total = len(storyboard.get("shots", [])) if storyboard else 0
            return f"Noch keine Keyframes ausgewählt. ({total} Shots insgesamt)"

        lines = ["### Aktuelle Auswahl"]
        for shot_id in sorted(selections.keys()):
            entry = selections[shot_id]
            lines.append(
                f"- Shot `{shot_id}` → **{entry['selected_file']}** (Var {entry['selected_variant']})"
            )
        return "\n".join(lines)

    def _build_preview_payload(
        self, storyboard: Dict[str, Any], selections: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        project = storyboard.get("project", "Unbekanntes Projekt") if storyboard else "Unbekanntes Projekt"
        shots = storyboard.get("shots", []) if storyboard else []
        all_shot_ids = {s.get("shot_id") for s in shots}
        selected_shot_ids = set(selections.keys()) if selections else set()
        missing_shot_ids = sorted(all_shot_ids - selected_shot_ids)

        payload = {
            "project": project,
            "total_shots": len(shots),
            "selected_shots": len(selected_shot_ids),
            "missing_shots": missing_shot_ids,
            "selections": [],
        }

        for shot_id in sorted(selections.keys()) if selections else []:
            entry = selections[shot_id]
            payload["selections"].append(
                {
                    "shot_id": entry["shot_id"],
                    "filename_base": entry["filename_base"],
                    "selected_variant": entry["selected_variant"],
                    "selected_file": entry["selected_file"],
                    "source_path": entry["source_path"],
                }
            )

        return payload

    # Removed: _apply_global_resolution() - now using StoryboardService.apply_resolution_from_config()


__all__ = ["KeyframeSelectorAddon"]
