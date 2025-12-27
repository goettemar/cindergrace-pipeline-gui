"""Global settings addon for configuring ComfyUI + workflow presets"""
import os
import sys
from urllib.parse import urlparse
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
            description="Global configuration for ComfyUI + workflow presets",
            category="tools"
        )
        self.config = ConfigManager()
        self.registry = WorkflowRegistry()

    def get_tab_name(self) -> str:
        return "⚙️ Settings"

    def _get_remote_backend_warning(self, url: str) -> str:
        """Return a warning if the backend URL is non-local."""
        if not url:
            return ""

        parsed = urlparse(url)
        host = parsed.hostname
        local_hosts = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}
        if host in local_hosts:
            return ""

        return (
            "⚠️ **Remote backend in use**\n\n"
            "Outputs are generated on a remote server. Avoid sensitive inputs and "
            "ensure you trust the backend."
        )


    def render(self) -> gr.Blocks:
        with gr.Blocks() as interface:
            # Unified header: Tab name left, no project relation
            gr.HTML(format_project_status(
                tab_name="⚙️ Pipeline Settings",
                no_project_relation=True,
                include_remote_warning=True,
            ))

            # Backend Selection Section
            with gr.Group():
                gr.Markdown("## 🔌 ComfyUI Backend")

                # Current backend info
                active = self.config.get_active_backend()
                active_type = active.get("type", "local")
                if active_type == "runpod":
                    type_display = f"🚀 RunPod (Pod: {active.get('pod_id', 'unknown')})"
                else:
                    type_display = "🖥️ Local"

                with gr.Row():
                    current_url = gr.Textbox(
                        value=active.get("url", ""),
                        label="Active URL",
                        interactive=False,
                        scale=3
                    )
                    current_type = gr.Textbox(
                        value=type_display,
                        label="Type",
                        interactive=False,
                        scale=1
                    )
                    test_btn = gr.Button("🧪 Test", scale=0)

                backend_status = gr.Markdown("")
                backend_warning = gr.Markdown(self._get_remote_backend_warning(active.get("url", "")))

            # RunPod Quick Connect
            with gr.Accordion("🚀 RunPod Quick Connect", open=False):
                gr.Markdown(
                    "Enter your Pod-ID to connect to RunPod. "
                    "URL: `https://{pod_id}-8188.proxy.runpod.net`\n\n"
                    "*Pod-ID ändert sich bei jedem neuen Pod - daher kein Speichern nötig.*"
                )

                with gr.Row():
                    runpod_id = gr.Textbox(
                        label="Pod-ID",
                        placeholder="abc123xyz",
                        info="Found in RunPod dashboard URL",
                        scale=3
                    )
                    activate_runpod_btn = gr.Button("🚀 Activate RunPod", variant="primary", scale=1)
                    use_local_btn = gr.Button("🖥️ Use Local", variant="secondary", scale=1)

                runpod_status = gr.Markdown("")

            # Local Backend Settings
            # Open accordion by default if comfy_root is not configured (first run)
            local_comfy_root = self.config.get_backends().get("local", {}).get("comfy_root", "")
            needs_config = not local_comfy_root

            with gr.Accordion("🖥️ Edit Local Backend", open=needs_config):
                if needs_config:
                    gr.Markdown(
                        """<div style="background: #fff3cd; color: #856404; padding: 12px; border-radius: 8px; margin-bottom: 12px;">
                        ⚠️ <strong>Bitte ComfyUI-Pfad eintragen</strong> - Dieser wird für Model-Validierung benötigt.
                        </div>"""
                    )
                local_url = gr.Textbox(
                    value=self.config.get_backends().get("local", {}).get("url", "http://127.0.0.1:8188"),
                    label="Local ComfyUI URL"
                )
                local_root = gr.Textbox(
                    value=local_comfy_root,
                    label="ComfyUI Installation Path",
                    placeholder="/path/to/ComfyUI",
                    info="Used for model validation"
                )
                save_local_btn = gr.Button("💾 Save Local Backend", variant="primary")
                local_status = gr.Markdown("")

            # Workflow Overview Section (dynamic, prefix-based)
            with gr.Group():
                gr.Markdown("## 🧩 Workflows")
                gr.Markdown(
                    "Workflows are automatically loaded from `config/workflow_templates/`.\n\n"
                    "**Prefixes:** `gcp_` = Keyframe, `gcv_` = Video, `gcvfl_` = First-Last, `gcl_` = Lipsync"
                )

                workflow_status = gr.Markdown(value=self._get_workflow_status())
                refresh_workflows_btn = gr.Button("🔄 Rescan Workflows", size="sm")

            # API Keys Section
            with gr.Group():
                gr.Markdown("## 🔑 API Keys")
                gr.Markdown(
                    "API keys are stored **encrypted** in the local database. "
                    "They never leave your machine."
                )

                civitai_key = gr.Textbox(
                    value=self.config.get_civitai_api_key(),
                    label="Civitai API Key",
                    type="password",
                    placeholder="Enter your Civitai API key",
                    info="Required for downloading models from Civitai. Get yours at civitai.com/user/account"
                )

                huggingface_token = gr.Textbox(
                    value=self.config.get_huggingface_token(),
                    label="Huggingface Token",
                    type="password",
                    placeholder="hf_...",
                    info="Required for some model downloads. Get yours at huggingface.co/settings/tokens"
                )

                google_tts_key = gr.Textbox(
                    value=self.config.get_google_tts_api_key(),
                    label="Google Cloud TTS API Key",
                    type="password",
                    placeholder="AIza...",
                    info="Required for text-to-speech. Get yours at console.cloud.google.com/apis/credentials"
                )

                save_api_keys_btn = gr.Button("💾 Save API Keys", variant="primary")
                api_keys_status = gr.Markdown(self._get_api_keys_status())

            # OpenRouter LLM Section
            with gr.Group():
                gr.Markdown("## 🤖 OpenRouter (LLM)")
                gr.Markdown(
                    "OpenRouter enables AI-powered storyboard generation from natural language. "
                    "Get your API key at [openrouter.ai](https://openrouter.ai/keys)."
                )

                openrouter_key = gr.Textbox(
                    value=self.config.get_openrouter_api_key(),
                    label="OpenRouter API Key",
                    type="password",
                    placeholder="sk-or-v1-...",
                    info="Required for AI storyboard generation"
                )

                gr.Markdown("### Models (choose up to 3)")
                current_models = self.config.get_openrouter_models()

                openrouter_model_1 = gr.Textbox(
                    value=current_models[0] if len(current_models) > 0 else "anthropic/claude-sonnet-4",
                    label="Model 1 (Primary)",
                    placeholder="anthropic/claude-sonnet-4",
                    info="Recommended: anthropic/claude-sonnet-4 or openai/gpt-4o"
                )
                openrouter_model_2 = gr.Textbox(
                    value=current_models[1] if len(current_models) > 1 else "openai/gpt-4o",
                    label="Model 2",
                    placeholder="openai/gpt-4o"
                )
                openrouter_model_3 = gr.Textbox(
                    value=current_models[2] if len(current_models) > 2 else "meta-llama/llama-3.1-70b-instruct",
                    label="Model 3",
                    placeholder="meta-llama/llama-3.1-70b-instruct"
                )

                with gr.Row():
                    save_openrouter_btn = gr.Button("💾 Save OpenRouter Settings", variant="primary")
                    test_openrouter_btn = gr.Button("🧪 Test Connection")

                openrouter_status = gr.Markdown(self._get_openrouter_status())

            # Developer Tools Section
            with gr.Accordion("🔧 Developer Tools", open=False):
                gr.Markdown(
                    "⚠️ **Warning:** These tools are for development and testing only."
                )

                with gr.Row():
                    reset_setup_btn = gr.Button(
                        "🔄 Reset Setup Wizard",
                        variant="secondary",
                        size="sm"
                    )
                    reset_all_btn = gr.Button(
                        "🗑️ Reset All Settings",
                        variant="stop",
                        size="sm"
                    )

                reset_status = gr.Markdown("")

            # Event handlers
            test_btn.click(
                fn=self.test_connection,
                inputs=[],
                outputs=[backend_status]
            )

            activate_runpod_btn.click(
                fn=self.activate_runpod,
                inputs=[runpod_id],
                outputs=[runpod_status, current_url, current_type, backend_warning]
            )

            use_local_btn.click(
                fn=self.use_local_backend,
                inputs=[],
                outputs=[runpod_status, current_url, current_type, backend_warning]
            )

            save_local_btn.click(
                fn=self.save_local_backend,
                inputs=[local_url, local_root],
                outputs=[local_status, backend_warning]
            )

            refresh_workflows_btn.click(
                fn=self._rescan_and_get_status,
                outputs=[workflow_status]
            )

            save_api_keys_btn.click(
                fn=self.save_api_keys,
                inputs=[civitai_key, huggingface_token, google_tts_key],
                outputs=[api_keys_status]
            )

            reset_setup_btn.click(
                fn=self.reset_setup_wizard,
                outputs=[reset_status]
            )

            reset_all_btn.click(
                fn=self.reset_all_settings,
                outputs=[reset_status]
            )

            # OpenRouter event handlers
            save_openrouter_btn.click(
                fn=self.save_openrouter_settings,
                inputs=[openrouter_key, openrouter_model_1, openrouter_model_2, openrouter_model_3],
                outputs=[openrouter_status]
            )

            test_openrouter_btn.click(
                fn=self.test_openrouter_connection,
                outputs=[openrouter_status]
            )

        return interface

    def _get_openrouter_status(self) -> str:
        """Get OpenRouter configuration status."""
        api_key = self.config.get_openrouter_api_key()
        models = self.config.get_openrouter_models()

        lines = []
        if api_key:
            lines.append("✅ **API Key:** Configured")
        else:
            lines.append("⚠️ **API Key:** Not configured")

        lines.append(f"**Models:** {len(models)} configured")
        for i, model in enumerate(models, 1):
            if model:
                lines.append(f"  {i}. `{model}`")

        return "\n".join(lines)

    def save_openrouter_settings(self, api_key: str, model_1: str, model_2: str, model_3: str) -> str:
        """Save OpenRouter API key and models."""
        try:
            # Save API key
            if api_key and api_key.strip():
                self.config.set_openrouter_api_key(api_key.strip())
                logger.info("OpenRouter API key saved")
            elif not api_key:
                self.config.set_openrouter_api_key("")

            # Save models (filter empty ones)
            models = [m.strip() for m in [model_1, model_2, model_3] if m and m.strip()]
            if not models:
                # Use defaults if all empty
                models = [
                    "anthropic/claude-sonnet-4",
                    "openai/gpt-4o",
                    "meta-llama/llama-3.1-70b-instruct",
                ]
            self.config.set_openrouter_models(models)
            logger.info(f"OpenRouter models saved: {models}")

            return f"✅ **Saved!**\n\n" + self._get_openrouter_status()
        except Exception as e:
            logger.error(f"Failed to save OpenRouter settings: {e}")
            return f"❌ **Error:** {e}"

    def test_openrouter_connection(self) -> str:
        """Test OpenRouter API connection."""
        try:
            from services.storyboard_llm_service import StoryboardLLMService

            service = StoryboardLLMService(self.config)
            result = service.test_connection()

            if result.get("connected"):
                return (
                    "✅ **Connection successful!**\n\n"
                    "OpenRouter API is ready for storyboard generation.\n\n"
                    + self._get_openrouter_status()
                )
            else:
                return f"❌ **Connection failed:** {result.get('message', 'Unknown error')}"
        except Exception as e:
            logger.error(f"OpenRouter connection test failed: {e}")
            return f"❌ **Error:** {e}"

    def _get_api_keys_status(self) -> str:
        """Get API keys configuration status."""
        lines = []

        civitai = self.config.get_civitai_api_key()
        if civitai:
            lines.append("✅ **Civitai:** Configured")
        else:
            lines.append("⚠️ **Civitai:** Not configured")

        huggingface = self.config.get_huggingface_token()
        if huggingface:
            lines.append("✅ **Huggingface:** Configured")
        else:
            lines.append("⚠️ **Huggingface:** Not configured")

        google_tts = self.config.get_google_tts_api_key()
        if google_tts:
            lines.append("✅ **Google TTS:** Configured")
        else:
            lines.append("⚠️ **Google TTS:** Not configured")

        return "\n".join(lines)

    def save_api_keys(self, civitai: str, huggingface: str, google_tts: str) -> str:
        """Save all API keys (encrypted)."""
        try:
            saved = []

            if civitai and civitai.strip():
                self.config.set_civitai_api_key(civitai.strip())
                saved.append("Civitai")
            elif not civitai:
                self.config.set_civitai_api_key("")

            if huggingface and huggingface.strip():
                self.config.set_huggingface_token(huggingface.strip())
                saved.append("Huggingface")
            elif not huggingface:
                self.config.set_huggingface_token("")

            if google_tts and google_tts.strip():
                self.config.set_google_tts_api_key(google_tts.strip())
                saved.append("Google TTS")
            elif not google_tts:
                self.config.set_google_tts_api_key("")

            if saved:
                logger.info(f"API keys saved: {', '.join(saved)}")
                return f"✅ **Saved:** {', '.join(saved)}\n\n" + self._get_api_keys_status()
            else:
                return "⚠️ **No keys to save** - All fields are empty\n\n" + self._get_api_keys_status()

        except Exception as e:
            logger.error(f"Failed to save API keys: {e}")
            return f"❌ **Error:** {e}"

    def _get_tts_status(self) -> str:
        """Get TTS configuration status (legacy)."""
        key = self.config.get_google_tts_api_key()
        if key and len(key) > 10:
            return "✅ **API Key configured** - TTS is ready"
        return "⚠️ **Not configured** - Please enter API Key"

    def save_tts_key(self, api_key: str) -> str:
        """Save Google Cloud TTS API key (legacy method)."""
        try:
            if not api_key or not api_key.strip():
                self.config.set_google_tts_api_key("")
                return "⚠️ **API Key removed**"

            api_key = api_key.strip()
            self.config.set_google_tts_api_key(api_key)
            logger.info("Google TTS API key saved")
            return "✅ **API Key saved** - TTS is now ready"
        except Exception as e:
            logger.error(f"Failed to save TTS API key: {e}")
            return f"❌ **Error:** {e}"

    def activate_runpod(self, pod_id: str):
        """Activate RunPod backend with given Pod-ID."""
        try:
            if not pod_id or not pod_id.strip():
                return ("**❌ Pod-ID required**", gr.update(), gr.update(), gr.update())

            pod_id = pod_id.strip()
            url = f"https://{pod_id}-8188.proxy.runpod.net"

            # Set temporary RunPod backend
            self.config.set_runpod_backend(pod_id, url)
            logger.info(f"Activated RunPod backend: {pod_id}")

            return (
                f"**✅ RunPod activated**\n\nPod-ID: `{pod_id}`",
                url,
                f"🚀 RunPod (Pod: {pod_id})",
                self._get_remote_backend_warning(url),
            )
        except Exception as e:
            logger.error(f"Failed to activate RunPod: {e}")
            return (f"**❌ Error:** {e}", gr.update(), gr.update(), gr.update())

    def use_local_backend(self):
        """Switch back to local backend."""
        try:
            self.config.set_active_backend("local")
            backend = self.config.get_active_backend()
            url = backend.get("url", "http://127.0.0.1:8188")
            logger.info("Switched to local backend")

            return (
                "**✅ Local backend activated**",
                url,
                "🖥️ Local",
                self._get_remote_backend_warning(url),
            )
        except Exception as e:
            logger.error(f"Failed to switch to local: {e}")
            return (f"**❌ Error:** {e}", gr.update(), gr.update(), gr.update())

    def test_connection(self):
        """Test connection to active backend."""
        try:
            url = self.config.get_comfy_url()
            api = ComfyUIAPI(url)
            result = api.test_connection()

            if result.get("connected"):
                backend = self.config.get_active_backend()
                return (
                    f"**✅ Connected to {backend.get('name', 'Backend')}**\n\n"
                    f"- URL: `{url}`\n"
                    f"- ComfyUI is running"
                )
            else:
                return f"**❌ No connection:** {result.get('error', 'Unknown error')}"
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return f"**❌ Connection error:** {e}"

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
            active = self.config.get_active_backend()
            active_url = active.get("url", "")
            return "**✅ Local backend updated**", self._get_remote_backend_warning(active_url)
        except Exception as e:
            logger.error(f"Failed to save local backend: {e}")
            return f"**❌ Error:** {e}", gr.update()

    def save_settings(self, comfy_url: str, comfy_root: str) -> str:
        """Legacy method for backward compatibility."""
        try:
            validated = SettingsInput(
                comfy_url=comfy_url,
                comfy_root=comfy_root
            )
        except Exception as exc:
            return f"**❌ Error:** {exc}"

        if hasattr(self.config, "update_backend"):
            result = self.save_local_backend(validated.comfy_url, validated.comfy_root)
            if isinstance(result, tuple):
                return result[0]
            return result

        self.config.set("comfy_url", validated.comfy_url)
        self.config.set("comfy_root", validated.comfy_root)
        return "**✅ Saved**"

    def save_presets(self, content: str) -> str:
        """Legacy method for saving workflow presets JSON."""
        return self.registry.save_raw(content)

    def _rescan_and_get_status(self) -> str:
        """Rescan filesystem for workflows and return status."""
        try:
            total, prefixes = self.registry.rescan()
            logger.info(f"Workflow rescan: {total} workflows found")
        except Exception as e:
            logger.error(f"Rescan failed: {e}")
        return self._get_workflow_status()

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

        lines = ["### Found Workflows\n"]

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
        lines.append("*⭐ = Default | 🎭 = LoRA variant available*")

        return "\n".join(lines)

    def reset_setup_wizard(self) -> str:
        """Reset the setup wizard flag so it shows as first run again."""
        try:
            from infrastructure.settings_store import SettingsStore
            store = SettingsStore()
            store.delete("setup_completed")
            logger.info("Setup wizard reset - will show on next app start")
            return (
                "✅ **Setup Wizard zurückgesetzt!**\n\n"
                "Beim nächsten App-Start wird der Setup-Hinweis wieder angezeigt.\n\n"
                "**Bitte App neu starten** um den Effekt zu sehen."
            )
        except Exception as e:
            logger.error(f"Failed to reset setup wizard: {e}")
            return f"❌ **Fehler:** {e}"

    def reset_all_settings(self) -> str:
        """Reset all settings to defaults including API keys."""
        try:
            from infrastructure.settings_store import SettingsStore
            store = SettingsStore()

            # Reset setup flag
            store.delete("setup_completed")

            # Reset backend to local
            store.delete("active_backend")

            # Clear project settings
            store.delete("current_project")
            store.delete("current_storyboard")

            # Clear API keys
            store.delete("civitai_api_key")
            store.delete("huggingface_token")
            store.delete("google_tts_api_key")

            logger.info("All settings reset to defaults (including API keys)")
            return (
                "✅ **Alle Einstellungen zurückgesetzt!**\n\n"
                "- Setup-Status: Zurückgesetzt\n"
                "- Backend: Zurück auf 'local'\n"
                "- Projekt: Gelöscht\n"
                "- API Keys: Gelöscht\n\n"
                "**Bitte App neu starten.**"
            )
        except Exception as e:
            logger.error(f"Failed to reset settings: {e}")
            return f"❌ **Fehler:** {e}"


__all__ = ["SettingsAddon"]
