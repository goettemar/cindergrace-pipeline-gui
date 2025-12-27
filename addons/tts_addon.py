"""Text-to-Speech Addon for CINDERGRACE Pipeline."""
import os
import gradio as gr

from addons.base_addon import BaseAddon
from addons.components import project_status_md
from infrastructure.config_manager import ConfigManager
from infrastructure.project_store import ProjectStore
from infrastructure.logger import get_logger
from services.tts_service import TTSService, GERMAN_VOICES, ENGLISH_VOICES

logger = get_logger(__name__)


class TTSAddon(BaseAddon):
    """Text-to-Speech addon using Google Cloud TTS."""

    def __init__(self):
        super().__init__(
            name="Text-to-Speech",
            description="Voice output for explainer videos and narration",
            category="production"
        )
        self.config = ConfigManager()
        self.project_store = ProjectStore(self.config)
        self.tts_service = TTSService(self.config)

    def get_tab_name(self) -> str:
        return "🎙️ TTS"

    def render(self) -> gr.Blocks:
        with gr.Blocks() as interface:
            # Unified header: Tab name left, project status right
            project_status = gr.HTML(project_status_md(self.project_store, "🎙️ Text-to-Speech"))

            gr.Markdown("Create professional voice outputs for explainer videos, tutorials and narration.")

            # Status/Config check
            config_status = self._get_config_status()
            status_md = gr.Markdown(config_status)

            with gr.Row():
                # Left Column: Settings (30%)
                with gr.Column(scale=3):
                    with gr.Group():
                        gr.Markdown("### ⚙️ Settings")

                        language = gr.Radio(
                            choices=[("German", "de"), ("English", "en")],
                            value="de",
                            label="Language",
                            interactive=True
                        )

                        # Voice selection with gender grouping
                        voice_choices = self._get_voice_choices("de")
                        voice = gr.Dropdown(
                            choices=voice_choices,
                            value="de-DE-Wavenet-B",  # Default: male Wavenet
                            label="Voice",
                            info="Wavenet/Neural2 = better quality, Standard = free",
                            interactive=True
                        )

                        with gr.Row():
                            speaking_rate = gr.Slider(
                                minimum=0.5,
                                maximum=2.0,
                                value=1.0,
                                step=0.1,
                                label="Speed",
                                info="0.5 = slow, 1.0 = normal, 2.0 = fast"
                            )
                            pitch = gr.Slider(
                                minimum=-10.0,
                                maximum=10.0,
                                value=0.0,
                                step=0.5,
                                label="Pitch",
                                info="-10 = lower, 0 = normal, +10 = higher"
                            )

                        output_format = gr.Radio(
                            choices=[("MP3 (compact)", "mp3"), ("WAV (uncompressed)", "wav")],
                            value="mp3",
                            label="Format"
                        )

                    with gr.Group():
                        gr.Markdown("### 📊 Cost Estimate")
                        cost_info = gr.Markdown("*Enter text to estimate costs*")

                # Right Column: Text & Output (70%)
                with gr.Column(scale=7):
                    with gr.Group():
                        gr.Markdown("### 📝 Script / Text")

                        script_text = gr.Textbox(
                            label="Text for voice output",
                            placeholder="Welcome to Cindergrace! In this video I'll show you how to...",
                            lines=10,
                            max_lines=30,
                            interactive=True
                        )

                        char_count = gr.Markdown("*0 characters*")

                    with gr.Row():
                        preview_btn = gr.Button("▶️ Preview (first 100 characters)", variant="secondary")
                        generate_btn = gr.Button("💾 Generate Audio", variant="primary")

                    gr.Markdown(
                        "⚠️ **Do not refresh during generation.** If you refresh, the job "
                        "continues in the backend but this page will lose tracking. "
                        "Check `logs/pipeline.log` for progress."
                    )

                    with gr.Group():
                        gr.Markdown("### 🔊 Output")

                        audio_output = gr.Audio(
                            label="Generated Audio",
                            type="filepath",
                            interactive=False
                        )

                        output_path = gr.Textbox(
                            label="Saved at",
                            interactive=False,
                            visible=True
                        )

                        generation_status = gr.Markdown("")

            # === Help texts ===
            with gr.Accordion("💡 Tips & Notes", open=False):
                gr.Markdown("""
### Voice Recommendations

**For Tech Tutorials (male):**
- 🎤 **Wavenet B** - Natural, professional
- 🎤 **Neural2 B** - State-of-the-art quality
- 🎤 **Neural2 D** - Slightly deeper

**For friendly explanations (female):**
- 🎤 **Wavenet C** - Warm, inviting
- 🎤 **Neural2 C** - Best quality

### Costs

| Voice | Free/Month | After |
|--------|-----------------|--------|
| Standard | 4M characters | $4/M |
| Wavenet | 1M characters | $16/M |
| Neural2 | - | $16/M |

**Example:** 10 minutes narration ≈ 8,000-10,000 characters

### Setting up API Key

1. Open [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project (or use existing one)
3. Enable "Cloud Text-to-Speech API"
4. Create API Key under "APIs & Services > Credentials"
5. Enter key in the "⚙️ Settings" tab
""")

            # === Event Handlers ===

            # Update voice choices when language changes
            language.change(
                fn=self._update_voice_choices,
                inputs=[language],
                outputs=[voice]
            )

            # Update char count and cost estimate
            script_text.change(
                fn=self._update_estimates,
                inputs=[script_text, voice],
                outputs=[char_count, cost_info]
            )

            voice.change(
                fn=self._update_estimates,
                inputs=[script_text, voice],
                outputs=[char_count, cost_info]
            )

            # Preview button
            preview_btn.click(
                fn=self._generate_preview,
                inputs=[script_text, voice, speaking_rate, pitch],
                outputs=[audio_output, generation_status]
            )

            # Generate button
            generate_btn.click(
                fn=self._generate_audio,
                inputs=[script_text, voice, speaking_rate, pitch, output_format],
                outputs=[audio_output, output_path, generation_status, status_md]
            )

            # Refresh status on tab load
            interface.load(
                fn=self._on_tab_load,
                outputs=[project_status, status_md]
            )

        return interface

    def _on_tab_load(self):
        """Refresh project status and config status when tab loads."""
        self.config.refresh()
        return project_status_md(self.project_store, "🎙️ Text-to-Speech"), self._get_config_status()

    def _get_config_status(self) -> str:
        """Get configuration status message."""
        self.config.refresh()  # Reload config from disk
        if not self.tts_service.is_configured():
            return """
⚠️ **Not configured:** Please enter Google Cloud API Key in the **⚙️ Settings** tab.

[Open Google Cloud Console](https://console.cloud.google.com/apis/credentials)
"""
        return "✅ **Configured:** TTS Service ready"

    def _get_voice_choices(self, language: str) -> list:
        """Get voice choices for dropdown."""
        voices = GERMAN_VOICES if language == "de" else ENGLISH_VOICES

        choices = []
        # Male voices first (for tech tutorials)
        male_voices = [v for v in voices if v.gender == "male"]
        female_voices = [v for v in voices if v.gender == "female"]

        for v in male_voices:
            label = f"👨 {v.name}"
            choices.append((label, v.id))

        for v in female_voices:
            label = f"👩 {v.name}"
            choices.append((label, v.id))

        return choices

    def _update_voice_choices(self, language: str):
        """Update voice dropdown when language changes."""
        choices = self._get_voice_choices(language)
        default = "de-DE-Wavenet-B" if language == "de" else "en-US-Wavenet-A"
        return gr.update(choices=choices, value=default)

    def _update_estimates(self, text: str, voice_id: str) -> tuple:
        """Update character count and cost estimate."""
        if not text:
            return "*0 characters*", "*Enter text to estimate costs*"

        estimate = self.tts_service.estimate_cost(text, voice_id)

        char_md = f"**{estimate['char_count']:,}** characters | ~**{estimate['duration_seconds']:.0f}s** audio"

        cost_md = f"""
**Voice type:** {estimate['voice_type']}
**Estimated cost:** {estimate['cost_info']}

*Wavenet/Neural2: 1M characters free/month*
*Standard: 4M characters free/month*
"""
        return char_md, cost_md

    def _generate_preview(
        self,
        text: str,
        voice_id: str,
        speaking_rate: float,
        pitch: float
    ) -> tuple:
        """Generate preview with first 100 characters."""
        if not text:
            return None, "⚠️ Please enter text."

        if not self.tts_service.is_configured():
            return None, "⚠️ API key not configured."

        # Use first 100 chars for preview
        preview_text = text[:100]
        if len(text) > 100:
            preview_text += "..."

        # Generate to temp file
        import tempfile
        temp_path = os.path.join(tempfile.gettempdir(), "tts_preview.mp3")

        success, message = self.tts_service.synthesize(
            text=preview_text,
            voice_id=voice_id,
            output_path=temp_path,
            speaking_rate=speaking_rate,
            pitch=pitch,
            audio_format="mp3"
        )

        if success:
            return temp_path, f"✅ Preview generated ({len(preview_text)} characters)"
        else:
            return None, f"❌ {message}"

    def _generate_audio(
        self,
        text: str,
        voice_id: str,
        speaking_rate: float,
        pitch: float,
        output_format: str
    ) -> tuple:
        """Generate full audio and save to project."""
        if not text:
            return None, "", "⚠️ Please enter text.", self._get_config_status()

        if not self.tts_service.is_configured():
            return None, "", "⚠️ API key not configured.", self._get_config_status()

        output_dir = self.tts_service.get_output_dir()
        if not output_dir:
            return None, "", "⚠️ No active project.", self._get_config_status()

        # Generate filename
        filename = self.tts_service.generate_filename("narration")
        if output_format == "wav":
            filename = filename.replace(".mp3", ".wav")

        output_path = os.path.join(output_dir, filename)

        success, message = self.tts_service.synthesize(
            text=text,
            voice_id=voice_id,
            output_path=output_path,
            speaking_rate=speaking_rate,
            pitch=pitch,
            audio_format=output_format
        )

        if success:
            estimate = self.tts_service.estimate_cost(text, voice_id)
            status = f"""
✅ **Audio successfully generated!**

- **File:** `{filename}`
- **Characters:** {estimate['char_count']:,}
- **Estimated length:** ~{estimate['duration_seconds']:.0f} seconds
- **Cost:** {estimate['cost_info']}
"""
            return output_path, output_path, status, self._get_config_status()
        else:
            return None, "", f"❌ {message}", self._get_config_status()


__all__ = ["TTSAddon"]
