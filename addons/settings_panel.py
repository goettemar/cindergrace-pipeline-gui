"""Global settings addon for configuring ComfyUI + workflow presets"""
import os
import sys
import gradio as gr

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from addons.base_addon import BaseAddon
from infrastructure.config_manager import ConfigManager
from infrastructure.workflow_registry import WorkflowRegistry
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

    def render(self) -> gr.Blocks:
        with gr.Blocks() as interface:
            gr.Markdown("# ⚙️ Pipeline Settings")
            gr.Markdown(
                "Passe grundlegende Verbindungsdaten sowie die Workflow-Presets an. "
                "Diese Einstellungen werden direkt in `config/settings.json` bzw. "
                "`config/workflow_presets.json` gespeichert."
            )

            with gr.Group():
                gr.Markdown("## 🔌 ComfyUI Verbindung")
                comfy_url = gr.Textbox(
                    value=self.config.get_comfy_url(),
                    label="ComfyUI URL"
                )
                comfy_root = gr.Textbox(
                    value=self.config.get_comfy_root(),
                    label="ComfyUI Installationspfad",
                    info="Wird für Modell-Validierung genutzt (z.B. /home/user/ComfyUI)"
                )
                save_settings_btn = gr.Button("💾 Einstellungen speichern", variant="primary")
                settings_status = gr.Markdown("")

                save_settings_btn.click(
                    fn=self.save_settings,
                    inputs=[comfy_url, comfy_root],
                    outputs=[settings_status]
                )

            with gr.Group():
                gr.Markdown("## 🧩 Workflow-Presets")
                gr.Markdown(
                    "Hier definierst du, welche Workflow-Dateien in den einzelnen Tabs "
                    "ausgewählt werden dürfen. Kategorien: `flux`, `wan` usw."
                )
                workflow_editor = gr.Code(
                    value=self.registry.read_raw(),
                    language="json",
                    label="workflow_presets.json",
                    lines=20
                )

                with gr.Row():
                    reload_btn = gr.Button("🔄 Neu laden")
                    save_presets_btn = gr.Button("💾 Speichern", variant="primary")
                presets_status = gr.Markdown("")

                reload_btn.click(
                    fn=lambda: self.registry.read_raw(),
                    outputs=[workflow_editor]
                )

                save_presets_btn.click(
                    fn=self.save_presets,
                    inputs=[workflow_editor],
                    outputs=[presets_status]
                )

        return interface

    def save_settings(self, comfy_url: str, comfy_root: str) -> str:
        try:
            # Validate inputs with Pydantic
            validated = SettingsInput(
                comfy_url=comfy_url,
                comfy_root=comfy_root
            )

            logger.info(f"Saving settings: URL={validated.comfy_url}, Root={validated.comfy_root}")

            self.config.set("comfy_url", validated.comfy_url)
            self.config.set("comfy_root", validated.comfy_root)

            logger.info("✓ Settings saved successfully")
            return "**✅ Gespeichert:** Basiseinstellungen aktualisiert."
        except Exception as exc:
            logger.error(f"Failed to save settings: {exc}")
            return f"**❌ Fehler:** {exc}"

    def save_presets(self, content: str) -> str:
        return self.registry.save_raw(content)


__all__ = ["SettingsAddon"]
