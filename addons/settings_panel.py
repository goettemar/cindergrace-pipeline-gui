"""Global settings addon for configuring ComfyUI + workflow presets"""
import os
import sys
import gradio as gr

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from addons.base_addon import BaseAddon
from addons.components import format_project_status
from infrastructure.config_manager import ConfigManager
from infrastructure.workflow_registry import WorkflowRegistry, PREFIX_KEYFRAME, PREFIX_KEYFRAME_LORA, PREFIX_VIDEO, PREFIX_VIDEO_FIRSTLAST, PREFIX_LIPSYNC
from infrastructure.comfy_api.client import ComfyUIAPI
from infrastructure.logger import get_logger
from domain.validators import SettingsInput

logger = get_logger(__name__)


class SettingsAddon(BaseAddon):
    """Provide a central settings tab for general config + workflow presets"""

    def __init__(self):
        super().__init__(
            name="Settings",
            description="Global configuration for ComfyUI + workflow presets"
        )
        self.config = ConfigManager()
        self.registry = WorkflowRegistry()

    def get_tab_name(self) -> str:
        return "⚙️ Settings"

    def _get_backend_choices(self):
        """Get list of backend choices for dropdown."""
        backends = self.config.get_backends()
        choices = []
        for backend_id, backend in backends.items():
            backend_type = "☁️" if backend.get("type") == "remote" else "🖥️"
            choices.append((f"{backend_type} {backend.get('name', backend_id)}", backend_id))
        return choices

    def render(self) -> gr.Blocks:
        with gr.Blocks() as interface:
            # Unified header: Tab name left, no project relation
            gr.HTML(format_project_status(tab_name="⚙️ Pipeline Settings", no_project_relation=True))

            # Backend Selection Section
            with gr.Group():
                gr.Markdown("## 🔌 ComfyUI Backend")
                gr.Markdown(
                    "Wähle zwischen lokalem ComfyUI und Cloud-Backends (z.B. Google Colab). "
                    "Bei Colab: Starte das Notebook und kopiere die Cloudflare-URL hierher."
                )

                with gr.Row():
                    backend_dropdown = gr.Dropdown(
                        choices=self._get_backend_choices(),
                        value=self.config.get_active_backend_id(),
                        label="Aktives Backend",
                        scale=2
                    )
                    switch_btn = gr.Button("🔄 Wechseln", variant="primary", scale=1)
                    test_btn = gr.Button("🧪 Testen", scale=1)

                backend_status = gr.Markdown("")

                # Current backend info
                active = self.config.get_active_backend()
                with gr.Row():
                    current_url = gr.Textbox(
                        value=active.get("url", ""),
                        label="Aktive URL",
                        interactive=False
                    )
                    current_type = gr.Textbox(
                        value="Cloud/Remote" if active.get("type") == "remote" else "Lokal",
                        label="Typ",
                        interactive=False,
                        scale=0
                    )

            # Add/Edit Backend Section
            with gr.Accordion("➕ Backend hinzufügen / bearbeiten", open=False):
                gr.Markdown(
                    "**Colab-URL:** Nach Start des Colab-Notebooks erscheint eine URL wie "
                    "`https://xxx-xxx.trycloudflare.com`. Diese hier eintragen."
                )

                new_backend_name = gr.Textbox(
                    label="Name",
                    placeholder="z.B. Colab T4 GPU"
                )

                with gr.Row():
                    new_backend_url = gr.Textbox(
                        label="ComfyUI URL",
                        placeholder="https://xxx.trycloudflare.com",
                        scale=2
                    )
                    new_backend_type = gr.Radio(
                        choices=[("🖥️ Lokal", "local"), ("☁️ Remote/Colab", "remote")],
                        value="remote",
                        label="Typ"
                    )

                new_comfy_root = gr.Textbox(
                    label="ComfyUI Pfad (nur für lokale Backends)",
                    placeholder="/home/user/ComfyUI",
                    visible=False
                )

                # Show/hide comfy_root based on type
                new_backend_type.change(
                    fn=lambda t: gr.update(visible=(t == "local")),
                    inputs=[new_backend_type],
                    outputs=[new_comfy_root]
                )

                with gr.Row():
                    add_backend_btn = gr.Button("➕ Hinzufügen", variant="primary")
                    remove_backend_btn = gr.Button("🗑️ Ausgewähltes entfernen", variant="stop")

                add_status = gr.Markdown("")

            # Local Backend Settings (legacy compatibility)
            with gr.Accordion("🖥️ Lokales Backend bearbeiten", open=False):
                local_url = gr.Textbox(
                    value=self.config.get_backends().get("local", {}).get("url", "http://127.0.0.1:8188"),
                    label="Lokale ComfyUI URL"
                )
                local_root = gr.Textbox(
                    value=self.config.get_backends().get("local", {}).get("comfy_root", ""),
                    label="ComfyUI Installationspfad",
                    info="Wird für Modell-Validierung genutzt"
                )
                save_local_btn = gr.Button("💾 Lokal-Backend speichern", variant="primary")
                local_status = gr.Markdown("")

            # Workflow Overview Section (dynamic, prefix-based)
            with gr.Group():
                gr.Markdown("## 🧩 Workflows")
                gr.Markdown(
                    "Workflows werden automatisch aus `config/workflow_templates/` geladen.\n\n"
                    "**Präfixe:** `gcp_` = Keyframe, `gcv_` = Video, `gcvfl_` = First-Last, `gcl_` = Lipsync"
                )

                workflow_status = gr.Markdown(value=self._get_workflow_status())
                refresh_workflows_btn = gr.Button("🔄 Workflows neu scannen", size="sm")

            # Google Cloud TTS Section
            with gr.Group():
                gr.Markdown("## 🎙️ Text-to-Speech (Google Cloud)")
                gr.Markdown(
                    "Für den TTS-Tab wird ein Google Cloud API Key benötigt. "
                    "[API Key erstellen](https://console.cloud.google.com/apis/credentials)"
                )

                google_tts_key = gr.Textbox(
                    value=self.config.get("google_tts_api_key", ""),
                    label="Google Cloud API Key",
                    type="password",
                    placeholder="AIza...",
                    info="Cloud Text-to-Speech API muss im Projekt aktiviert sein"
                )

                save_tts_btn = gr.Button("💾 API Key speichern", variant="primary")
                tts_status = gr.Markdown(self._get_tts_status())

            # Event handlers
            switch_btn.click(
                fn=self.switch_backend,
                inputs=[backend_dropdown],
                outputs=[backend_status, current_url, current_type]
            )

            test_btn.click(
                fn=self.test_connection,
                inputs=[],
                outputs=[backend_status]
            )

            add_backend_btn.click(
                fn=self.add_backend,
                inputs=[new_backend_name, new_backend_url, new_backend_type, new_comfy_root],
                outputs=[add_status, backend_dropdown]
            )

            remove_backend_btn.click(
                fn=self.remove_backend,
                inputs=[backend_dropdown],
                outputs=[add_status, backend_dropdown]
            )

            save_local_btn.click(
                fn=self.save_local_backend,
                inputs=[local_url, local_root],
                outputs=[local_status]
            )

            refresh_workflows_btn.click(
                fn=self._get_workflow_status,
                outputs=[workflow_status]
            )

            save_tts_btn.click(
                fn=self.save_tts_key,
                inputs=[google_tts_key],
                outputs=[tts_status]
            )

        return interface

    def _get_tts_status(self) -> str:
        """Get TTS configuration status."""
        key = self.config.get("google_tts_api_key", "")
        if key and len(key) > 10:
            return "✅ **API Key konfiguriert** - TTS ist bereit"
        return "⚠️ **Nicht konfiguriert** - Bitte API Key eintragen"

    def save_tts_key(self, api_key: str) -> str:
        """Save Google Cloud TTS API key."""
        try:
            if not api_key or not api_key.strip():
                self.config.set("google_tts_api_key", "")
                return "⚠️ **API Key entfernt**"

            api_key = api_key.strip()
            self.config.set("google_tts_api_key", api_key)
            logger.info("Google TTS API key saved")
            return "✅ **API Key gespeichert** - TTS ist jetzt bereit"
        except Exception as e:
            logger.error(f"Failed to save TTS API key: {e}")
            return f"❌ **Fehler:** {e}"

    def switch_backend(self, backend_id: str):
        """Switch to selected backend."""
        try:
            if self.config.set_active_backend(backend_id):
                backend = self.config.get_active_backend()
                url = backend.get("url", "")
                backend_type = "Cloud/Remote" if backend.get("type") == "remote" else "Lokal"
                logger.info(f"Switched to backend: {backend_id}")
                return (
                    f"**✅ Gewechselt zu:** {backend.get('name', backend_id)}",
                    url,
                    backend_type
                )
            else:
                return ("**❌ Backend nicht gefunden**", "", "")
        except Exception as e:
            logger.error(f"Failed to switch backend: {e}")
            return (f"**❌ Fehler:** {e}", "", "")

    def test_connection(self):
        """Test connection to active backend."""
        try:
            url = self.config.get_comfy_url()
            api = ComfyUIAPI(url)
            result = api.test_connection()

            if result.get("status") == "connected":
                backend = self.config.get_active_backend()
                return (
                    f"**✅ Verbunden mit {backend.get('name', 'Backend')}**\n\n"
                    f"- URL: `{url}`\n"
                    f"- ComfyUI läuft"
                )
            else:
                return f"**❌ Keine Verbindung:** {result.get('error', 'Unbekannter Fehler')}"
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return f"**❌ Verbindungsfehler:** {e}"

    def add_backend(self, name: str, url: str, backend_type: str, comfy_root: str):
        """Add a new backend configuration."""
        try:
            if not name or not name.strip():
                return ("**❌ Name erforderlich**", gr.update())

            if not url or not url.strip():
                return ("**❌ URL erforderlich**", gr.update())

            # Clean up inputs and auto-generate ID from name
            name = name.strip()
            backend_id = name.lower().replace(" ", "_").replace("-", "_")
            # Remove special characters
            backend_id = "".join(c for c in backend_id if c.isalnum() or c == "_")
            url = url.strip()

            # Validate URL format
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url

            self.config.add_backend(
                backend_id=backend_id,
                name=name,
                url=url,
                backend_type=backend_type,
                comfy_root=comfy_root if backend_type == "local" else ""
            )

            logger.info(f"Added backend: {backend_id} ({name})")
            return (
                f"**✅ Backend hinzugefügt:** {name}",
                gr.update(choices=self._get_backend_choices())
            )
        except Exception as e:
            logger.error(f"Failed to add backend: {e}")
            return (f"**❌ Fehler:** {e}", gr.update())

    def remove_backend(self, backend_id: str):
        """Remove a backend configuration."""
        try:
            if backend_id == "local":
                return ("**❌ Lokales Backend kann nicht entfernt werden**", gr.update())

            if self.config.remove_backend(backend_id):
                logger.info(f"Removed backend: {backend_id}")
                return (
                    f"**✅ Backend entfernt:** {backend_id}",
                    gr.update(choices=self._get_backend_choices(), value="local")
                )
            else:
                return ("**❌ Backend nicht gefunden**", gr.update())
        except Exception as e:
            logger.error(f"Failed to remove backend: {e}")
            return (f"**❌ Fehler:** {e}", gr.update())

    def save_local_backend(self, url: str, comfy_root: str):
        """Update local backend settings."""
        try:
            validated = SettingsInput(
                comfy_url=url,
                comfy_root=comfy_root
            )

            self.config.update_backend(
                backend_id="local",
                url=validated.comfy_url,
                comfy_root=validated.comfy_root
            )

            logger.info(f"Updated local backend: URL={validated.comfy_url}")
            return "**✅ Lokales Backend aktualisiert**"
        except Exception as e:
            logger.error(f"Failed to save local backend: {e}")
            return f"**❌ Fehler:** {e}"

    def save_settings(self, comfy_url: str, comfy_root: str) -> str:
        """Legacy method for backward compatibility."""
        try:
            validated = SettingsInput(
                comfy_url=comfy_url,
                comfy_root=comfy_root
            )
        except Exception as exc:
            return f"**❌ Fehler:** {exc}"

        if hasattr(self.config, "update_backend"):
            return self.save_local_backend(validated.comfy_url, validated.comfy_root)

        self.config.set("comfy_url", validated.comfy_url)
        self.config.set("comfy_root", validated.comfy_root)
        return "**✅ Gespeichert**"

    def save_presets(self, content: str) -> str:
        """Legacy method for saving workflow presets JSON."""
        return self.registry.save_raw(content)

    def _get_workflow_status(self) -> str:
        """Get formatted workflow status for display."""
        kf_workflows = self.registry.get_files(PREFIX_KEYFRAME)
        kf_lora_workflows = self.registry.get_files(PREFIX_KEYFRAME_LORA)
        vid_workflows = self.registry.get_files(PREFIX_VIDEO)
        vid_fl_workflows = self.registry.get_files(PREFIX_VIDEO_FIRSTLAST)
        lip_workflows = self.registry.get_files(PREFIX_LIPSYNC)

        kf_default = self.registry.get_default(PREFIX_KEYFRAME)
        vid_default = self.registry.get_default(PREFIX_VIDEO)
        vid_fl_default = self.registry.get_default(PREFIX_VIDEO_FIRSTLAST)
        lip_default = self.registry.get_default(PREFIX_LIPSYNC)

        lines = ["### Gefundene Workflows\n"]

        # Keyframe
        lines.append(f"**Keyframe (gcp_):** {len(kf_workflows)} Workflow(s)")
        if kf_workflows:
            for wf in kf_workflows:
                marker = "⭐" if wf == kf_default else "  "
                has_lora = "🎭" if self.registry.has_lora_variant(wf) else "  "
                lines.append(f"  {marker}{has_lora} `{wf}`")
        lines.append("")

        # Keyframe LoRA (hidden from dropdown, auto-selected)
        if kf_lora_workflows:
            lines.append(f"**Keyframe LoRA (gcpl_):** {len(kf_lora_workflows)} Workflow(s)")
            for wf in kf_lora_workflows:
                lines.append(f"     `{wf}`")
            lines.append("")

        # Video
        lines.append(f"**Video (gcv_):** {len(vid_workflows)} Workflow(s)")
        if vid_workflows:
            for wf in vid_workflows:
                marker = "⭐" if wf == vid_default else "  "
                lines.append(f"  {marker} `{wf}`")
        lines.append("")

        # Video First-Last
        lines.append(f"**First-Last Frame (gcvfl_):** {len(vid_fl_workflows)} Workflow(s)")
        if vid_fl_workflows:
            for wf in vid_fl_workflows:
                marker = "⭐" if wf == vid_fl_default else "  "
                lines.append(f"  {marker} `{wf}`")
        lines.append("")

        # Lipsync
        lines.append(f"**Lipsync (gcl_):** {len(lip_workflows)} Workflow(s)")
        if lip_workflows:
            for wf in lip_workflows:
                marker = "⭐" if wf == lip_default else "  "
                lines.append(f"  {marker} `{wf}`")

        lines.append("")
        lines.append("*⭐ = Default | 🎭 = LoRA-Variante verfügbar*")

        return "\n".join(lines)


__all__ = ["SettingsAddon"]
