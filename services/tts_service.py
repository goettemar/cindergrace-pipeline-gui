"""Text-to-Speech Service using Google Cloud TTS API."""
import os
import json
import base64
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple
from pathlib import Path

from infrastructure.config_manager import ConfigManager
from infrastructure.project_store import ProjectStore
from infrastructure.logger import get_logger

logger = get_logger(__name__)


@dataclass
class VoiceOption:
    """Represents a TTS voice option."""
    id: str  # e.g., "de-DE-Wavenet-C"
    name: str  # Display name, e.g., "Wavenet C (weiblich)"
    language: str  # e.g., "de-DE"
    gender: str  # "male" or "female"
    type: str  # "Standard", "Wavenet", "Neural2"


# Available German voices from Google Cloud TTS
GERMAN_VOICES: List[VoiceOption] = [
    # WaveNet voices (higher quality)
    VoiceOption("de-DE-Wavenet-A", "Wavenet A (weiblich)", "de-DE", "female", "Wavenet"),
    VoiceOption("de-DE-Wavenet-B", "Wavenet B (männlich)", "de-DE", "male", "Wavenet"),
    VoiceOption("de-DE-Wavenet-C", "Wavenet C (weiblich)", "de-DE", "female", "Wavenet"),
    VoiceOption("de-DE-Wavenet-D", "Wavenet D (männlich)", "de-DE", "male", "Wavenet"),
    VoiceOption("de-DE-Wavenet-E", "Wavenet E (männlich)", "de-DE", "male", "Wavenet"),
    VoiceOption("de-DE-Wavenet-F", "Wavenet F (weiblich)", "de-DE", "female", "Wavenet"),
    # Neural2 voices (newest, best quality)
    VoiceOption("de-DE-Neural2-A", "Neural2 A (weiblich)", "de-DE", "female", "Neural2"),
    VoiceOption("de-DE-Neural2-B", "Neural2 B (männlich)", "de-DE", "male", "Neural2"),
    VoiceOption("de-DE-Neural2-C", "Neural2 C (weiblich)", "de-DE", "female", "Neural2"),
    VoiceOption("de-DE-Neural2-D", "Neural2 D (männlich)", "de-DE", "male", "Neural2"),
    VoiceOption("de-DE-Neural2-F", "Neural2 F (weiblich)", "de-DE", "female", "Neural2"),
    # Standard voices (free tier)
    VoiceOption("de-DE-Standard-A", "Standard A (weiblich)", "de-DE", "female", "Standard"),
    VoiceOption("de-DE-Standard-B", "Standard B (männlich)", "de-DE", "male", "Standard"),
    VoiceOption("de-DE-Standard-C", "Standard C (weiblich)", "de-DE", "female", "Standard"),
    VoiceOption("de-DE-Standard-D", "Standard D (männlich)", "de-DE", "male", "Standard"),
    VoiceOption("de-DE-Standard-E", "Standard E (männlich)", "de-DE", "male", "Standard"),
    VoiceOption("de-DE-Standard-F", "Standard F (weiblich)", "de-DE", "female", "Standard"),
]

# English voices for international content
ENGLISH_VOICES: List[VoiceOption] = [
    VoiceOption("en-US-Wavenet-A", "US Wavenet A (männlich)", "en-US", "male", "Wavenet"),
    VoiceOption("en-US-Wavenet-C", "US Wavenet C (weiblich)", "en-US", "female", "Wavenet"),
    VoiceOption("en-US-Wavenet-D", "US Wavenet D (männlich)", "en-US", "male", "Wavenet"),
    VoiceOption("en-US-Wavenet-F", "US Wavenet F (weiblich)", "en-US", "female", "Wavenet"),
    VoiceOption("en-GB-Wavenet-A", "UK Wavenet A (weiblich)", "en-GB", "female", "Wavenet"),
    VoiceOption("en-GB-Wavenet-B", "UK Wavenet B (männlich)", "en-GB", "male", "Wavenet"),
]


class TTSService:
    """Service for Text-to-Speech conversion using Google Cloud TTS."""

    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config or ConfigManager()
        self.project_store = ProjectStore(self.config)

    def get_api_key(self) -> Optional[str]:
        """Get Google Cloud API key from config."""
        self.config.refresh()  # Reload from disk to get latest value
        return self.config.get("google_tts_api_key")

    def is_configured(self) -> bool:
        """Check if TTS is properly configured."""
        api_key = self.get_api_key()
        return bool(api_key and len(api_key) > 10)

    def get_voice_choices(self, language: str = "de") -> List[Tuple[str, str]]:
        """Get voice choices for dropdown.

        Returns:
            List of (display_name, voice_id) tuples
        """
        voices = GERMAN_VOICES if language == "de" else ENGLISH_VOICES

        choices = []
        # Group by gender for better UX
        male_voices = [v for v in voices if v.gender == "male"]
        female_voices = [v for v in voices if v.gender == "female"]

        choices.append(("--- Männlich ---", ""))
        for v in male_voices:
            label = f"🎤 {v.name} [{v.type}]"
            choices.append((label, v.id))

        choices.append(("--- Weiblich ---", ""))
        for v in female_voices:
            label = f"🎤 {v.name} [{v.type}]"
            choices.append((label, v.id))

        return choices

    def get_voice_by_id(self, voice_id: str) -> Optional[VoiceOption]:
        """Get voice option by ID."""
        all_voices = GERMAN_VOICES + ENGLISH_VOICES
        for v in all_voices:
            if v.id == voice_id:
                return v
        return None

    def estimate_cost(self, text: str, voice_id: str) -> dict:
        """Estimate cost for TTS conversion.

        Returns:
            Dict with char_count, estimated_duration, cost_estimate
        """
        char_count = len(text)
        # Approximate: 150 words per minute, 5 chars per word
        words = char_count / 5
        duration_minutes = words / 150
        duration_seconds = duration_minutes * 60

        voice = self.get_voice_by_id(voice_id)
        voice_type = voice.type if voice else "Standard"

        # Cost per million characters (after free tier)
        costs = {
            "Standard": 4.0,
            "Wavenet": 16.0,
            "Neural2": 16.0,
        }
        cost_per_char = costs.get(voice_type, 4.0) / 1_000_000
        cost_estimate = char_count * cost_per_char

        return {
            "char_count": char_count,
            "duration_seconds": round(duration_seconds, 1),
            "voice_type": voice_type,
            "cost_estimate": round(cost_estimate, 4),
            "cost_info": f"${cost_estimate:.4f}" if cost_estimate > 0 else "Kostenlos (Free Tier)"
        }

    def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: str,
        speaking_rate: float = 1.0,
        pitch: float = 0.0,
        audio_format: str = "mp3"
    ) -> Tuple[bool, str]:
        """Synthesize text to speech.

        Args:
            text: Text to convert to speech
            voice_id: Google Cloud voice ID (e.g., "de-DE-Wavenet-B")
            output_path: Path to save audio file
            speaking_rate: Speed (0.25 to 4.0, default 1.0)
            pitch: Pitch adjustment (-20.0 to 20.0, default 0.0)
            audio_format: Output format ("mp3" or "wav")

        Returns:
            Tuple of (success: bool, message: str)
        """
        api_key = self.get_api_key()
        if not api_key:
            return False, "Kein Google Cloud API Key konfiguriert. Bitte in Settings eintragen."

        voice = self.get_voice_by_id(voice_id)
        if not voice:
            return False, f"Unbekannte Stimme: {voice_id}"

        # Prepare request
        url = "https://texttospeech.googleapis.com/v1/text:synthesize"

        audio_encoding = "MP3" if audio_format == "mp3" else "LINEAR16"

        payload = {
            "input": {"text": text},
            "voice": {
                "languageCode": voice.language,
                "name": voice_id,
            },
            "audioConfig": {
                "audioEncoding": audio_encoding,
                "speakingRate": max(0.25, min(4.0, speaking_rate)),
                "pitch": max(-20.0, min(20.0, pitch)),
            }
        }

        try:
            import urllib.request
            import urllib.error

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": api_key,
                },
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode("utf-8"))

            # Decode audio content
            audio_content = base64.b64decode(result["audioContent"])

            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Write audio file
            with open(output_path, "wb") as f:
                f.write(audio_content)

            file_size = len(audio_content) / 1024  # KB
            logger.info(f"TTS audio generated: {output_path} ({file_size:.1f} KB)")

            return True, f"Audio gespeichert: {output_path}"

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            redacted_error = self._redact_api_key(error_body, api_key)
            logger.error(f"Google TTS API error: {e.code} - {redacted_error}")

            if e.code == 403:
                return False, "API-Fehler: Zugriff verweigert. Prüfe den API Key und ob TTS API aktiviert ist."
            elif e.code == 400:
                safe_preview = redacted_error[:200] if redacted_error else ""
                return False, f"API-Fehler: Ungültige Anfrage. {safe_preview}"
            else:
                return False, f"API-Fehler: {e.code}"

        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}", exc_info=True)
            return False, f"Fehler: {str(e)}"

    def get_output_dir(self) -> Optional[str]:
        """Get audio output directory for current project."""
        project = self.project_store.get_active_project()
        if not project:
            return None
        audio_dir = os.path.join(project["path"], "audio")
        os.makedirs(audio_dir, exist_ok=True)
        return audio_dir

    def generate_filename(self, prefix: str = "narration") -> str:
        """Generate unique filename for audio output."""
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_{timestamp}.mp3"

    def _redact_api_key(self, text: str, api_key: str) -> str:
        """Redact API key from logs and error messages."""
        if not text:
            return text

        redacted = text
        if api_key:
            redacted = redacted.replace(api_key, "***REDACTED***")

        # Also redact common key query param patterns
        redacted = re.sub(r"(key=)[^&\"'\\s]+", r"\\1***REDACTED***", redacted)
        return redacted


__all__ = ["TTSService", "VoiceOption", "GERMAN_VOICES", "ENGLISH_VOICES"]
