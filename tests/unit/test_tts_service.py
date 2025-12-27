"""Tests for TTSService."""
import os
import json
import base64
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from services.tts_service import (
    TTSService,
    VoiceOption,
    GERMAN_VOICES,
    ENGLISH_VOICES
)


class TestVoiceOption:
    """Tests for VoiceOption dataclass."""

    def test_voice_option_creation(self):
        """Test creating a VoiceOption."""
        voice = VoiceOption(
            id="de-DE-Wavenet-B",
            name="Wavenet B (männlich)",
            language="de-DE",
            gender="male",
            type="Wavenet"
        )
        assert voice.id == "de-DE-Wavenet-B"
        assert voice.name == "Wavenet B (männlich)"
        assert voice.language == "de-DE"
        assert voice.gender == "male"
        assert voice.type == "Wavenet"


class TestVoiceLists:
    """Tests for voice lists."""

    def test_german_voices_not_empty(self):
        """Test that German voices list is not empty."""
        assert len(GERMAN_VOICES) > 0

    def test_english_voices_not_empty(self):
        """Test that English voices list is not empty."""
        assert len(ENGLISH_VOICES) > 0

    def test_german_voices_have_de_language(self):
        """Test that all German voices have de-DE language."""
        for voice in GERMAN_VOICES:
            assert voice.language.startswith("de-")

    def test_english_voices_have_en_language(self):
        """Test that all English voices have en language."""
        for voice in ENGLISH_VOICES:
            assert voice.language.startswith("en-")

    def test_voices_have_valid_genders(self):
        """Test that all voices have valid gender."""
        for voice in GERMAN_VOICES + ENGLISH_VOICES:
            assert voice.gender in ("male", "female")

    def test_voices_have_valid_types(self):
        """Test that all voices have valid type."""
        valid_types = ("Standard", "Wavenet", "Neural2")
        for voice in GERMAN_VOICES + ENGLISH_VOICES:
            assert voice.type in valid_types


class TestTTSService:
    """Tests for TTSService class."""

    @pytest.fixture
    def mock_config(self):
        """Create mock ConfigManager."""
        config = Mock()
        config.get.return_value = "test-api-key-12345"
        config.refresh = Mock()
        return config

    @pytest.fixture
    def mock_project_store(self, tmp_path):
        """Create mock ProjectStore."""
        store = Mock()
        store.get_active_project.return_value = {
            "path": str(tmp_path / "project")
        }
        return store

    @pytest.fixture
    def service(self, mock_config):
        """Create TTSService instance."""
        with patch('services.tts_service.ProjectStore'):
            service = TTSService(config=mock_config)
            return service

    # ========================================================================
    # Configuration Tests
    # ========================================================================

    def test_get_api_key(self, service, mock_config):
        """Test getting API key."""
        result = service.get_api_key()
        mock_config.refresh.assert_called_once()
        mock_config.get.assert_called_with("google_tts_api_key")

    def test_is_configured_with_key(self, service, mock_config):
        """Test is_configured returns True with valid key."""
        mock_config.get.return_value = "valid-api-key-123"
        assert service.is_configured() is True

    def test_is_configured_without_key(self, service, mock_config):
        """Test is_configured returns False without key."""
        mock_config.get.return_value = None
        assert service.is_configured() is False

    def test_is_configured_with_short_key(self, service, mock_config):
        """Test is_configured returns False with short key."""
        mock_config.get.return_value = "short"
        assert service.is_configured() is False

    def test_is_configured_with_empty_key(self, service, mock_config):
        """Test is_configured returns False with empty key."""
        mock_config.get.return_value = ""
        assert service.is_configured() is False

    # ========================================================================
    # Voice Choice Tests
    # ========================================================================

    def test_get_voice_choices_german(self, service):
        """Test getting German voice choices."""
        choices = service.get_voice_choices("de")

        assert len(choices) > 0
        # Check for gender headers
        labels = [c[0] for c in choices]
        assert any("Männlich" in l for l in labels)
        assert any("Weiblich" in l for l in labels)

    def test_get_voice_choices_english(self, service):
        """Test getting English voice choices."""
        choices = service.get_voice_choices("en")

        assert len(choices) > 0
        # Should contain English voices
        ids = [c[1] for c in choices if c[1]]
        assert any("en-" in id for id in ids)

    def test_get_voice_choices_format(self, service):
        """Test voice choices format."""
        choices = service.get_voice_choices("de")

        for label, voice_id in choices:
            assert isinstance(label, str)
            assert isinstance(voice_id, str)

    def test_get_voice_by_id_found(self, service):
        """Test getting voice by valid ID."""
        voice = service.get_voice_by_id("de-DE-Wavenet-B")

        assert voice is not None
        assert voice.id == "de-DE-Wavenet-B"

    def test_get_voice_by_id_not_found(self, service):
        """Test getting voice by invalid ID."""
        voice = service.get_voice_by_id("invalid-voice-id")
        assert voice is None

    def test_get_voice_by_id_english(self, service):
        """Test getting English voice by ID."""
        voice = service.get_voice_by_id("en-US-Wavenet-A")

        assert voice is not None
        assert voice.language == "en-US"

    # ========================================================================
    # Cost Estimation Tests
    # ========================================================================

    def test_estimate_cost_structure(self, service):
        """Test cost estimation structure."""
        result = service.estimate_cost("Hello world", "de-DE-Standard-A")

        assert "char_count" in result
        assert "duration_seconds" in result
        assert "voice_type" in result
        assert "cost_estimate" in result
        assert "cost_info" in result

    def test_estimate_cost_char_count(self, service):
        """Test character count in estimation."""
        text = "Hello world"
        result = service.estimate_cost(text, "de-DE-Standard-A")

        assert result["char_count"] == len(text)

    def test_estimate_cost_standard_voice(self, service):
        """Test cost estimation for Standard voice."""
        result = service.estimate_cost("Test text", "de-DE-Standard-A")
        assert result["voice_type"] == "Standard"

    def test_estimate_cost_wavenet_voice(self, service):
        """Test cost estimation for Wavenet voice."""
        result = service.estimate_cost("Test text", "de-DE-Wavenet-B")
        assert result["voice_type"] == "Wavenet"

    def test_estimate_cost_neural2_voice(self, service):
        """Test cost estimation for Neural2 voice."""
        result = service.estimate_cost("Test text", "de-DE-Neural2-B")
        assert result["voice_type"] == "Neural2"

    def test_estimate_cost_duration_calculation(self, service):
        """Test duration calculation."""
        # 150 words per minute, 5 chars per word
        # 750 chars = 150 words = 1 minute = 60 seconds
        text = "x" * 750
        result = service.estimate_cost(text, "de-DE-Standard-A")

        assert result["duration_seconds"] == pytest.approx(60.0, rel=0.1)

    def test_estimate_cost_unknown_voice(self, service):
        """Test cost estimation for unknown voice."""
        result = service.estimate_cost("Test", "unknown-voice")
        # Should fall back to Standard pricing
        assert result["voice_type"] == "Standard"

    # ========================================================================
    # Synthesis Tests
    # ========================================================================

    def test_synthesize_no_api_key(self, service, mock_config):
        """Test synthesis without API key."""
        mock_config.get.return_value = None

        success, message = service.synthesize(
            "Test text",
            "de-DE-Wavenet-B",
            "/tmp/output.mp3"
        )

        assert success is False
        assert "API Key" in message

    def test_synthesize_invalid_voice(self, service):
        """Test synthesis with invalid voice."""
        success, message = service.synthesize(
            "Test text",
            "invalid-voice",
            "/tmp/output.mp3"
        )

        assert success is False
        assert "Unbekannte Stimme" in message

    def test_synthesize_success(self, service, tmp_path):
        """Test successful synthesis."""
        output_path = tmp_path / "output.mp3"

        # Mock the HTTP request
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({
            "audioContent": base64.b64encode(b"fake audio data").decode()
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        with patch('urllib.request.urlopen', return_value=mock_response):
            success, message = service.synthesize(
                "Test text",
                "de-DE-Wavenet-B",
                str(output_path)
            )

        assert success is True
        assert output_path.exists()

    def test_synthesize_creates_directory(self, service, tmp_path):
        """Test that synthesis creates output directory."""
        output_path = tmp_path / "new" / "nested" / "output.mp3"

        mock_response = Mock()
        mock_response.read.return_value = json.dumps({
            "audioContent": base64.b64encode(b"fake audio data").decode()
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        with patch('urllib.request.urlopen', return_value=mock_response):
            service.synthesize(
                "Test text",
                "de-DE-Wavenet-B",
                str(output_path)
            )

        assert output_path.parent.exists()

    def test_synthesize_rate_limits(self, service):
        """Test that speaking rate is limited."""
        import urllib.request

        with patch.object(urllib.request, 'urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.read.return_value = json.dumps({
                "audioContent": base64.b64encode(b"data").decode()
            }).encode()
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            mock_urlopen.return_value = mock_response

            service.synthesize(
                "Test",
                "de-DE-Wavenet-B",
                "/tmp/test.mp3",
                speaking_rate=10.0  # Should be clamped to 4.0
            )

            # Check that the request was made with clamped value
            call_args = mock_urlopen.call_args
            request = call_args[0][0]
            data = json.loads(request.data.decode())
            assert data["audioConfig"]["speakingRate"] == 4.0

    def test_synthesize_pitch_limits(self, service):
        """Test that pitch is limited."""
        import urllib.request

        with patch.object(urllib.request, 'urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.read.return_value = json.dumps({
                "audioContent": base64.b64encode(b"data").decode()
            }).encode()
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            mock_urlopen.return_value = mock_response

            service.synthesize(
                "Test",
                "de-DE-Wavenet-B",
                "/tmp/test.mp3",
                pitch=-50.0  # Should be clamped to -20.0
            )

            call_args = mock_urlopen.call_args
            request = call_args[0][0]
            data = json.loads(request.data.decode())
            assert data["audioConfig"]["pitch"] == -20.0

    def test_synthesize_http_403_error(self, service):
        """Test handling of 403 error."""
        import urllib.error

        error = urllib.error.HTTPError(
            "url", 403, "Forbidden", {}, None
        )

        with patch('urllib.request.urlopen', side_effect=error):
            success, message = service.synthesize(
                "Test",
                "de-DE-Wavenet-B",
                "/tmp/test.mp3"
            )

        assert success is False
        assert "Zugriff verweigert" in message

    def test_synthesize_http_400_error(self, service):
        """Test handling of 400 error."""
        import urllib.error

        error = urllib.error.HTTPError(
            "url", 400, "Bad Request", {}, None
        )
        error.fp = None

        with patch('urllib.request.urlopen', side_effect=error):
            success, message = service.synthesize(
                "Test",
                "de-DE-Wavenet-B",
                "/tmp/test.mp3"
            )

        assert success is False
        assert "Ungültige Anfrage" in message

    def test_synthesize_wav_format(self, service, tmp_path):
        """Test synthesis with WAV format."""
        import urllib.request

        output_path = tmp_path / "output.wav"

        with patch.object(urllib.request, 'urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.read.return_value = json.dumps({
                "audioContent": base64.b64encode(b"wav data").decode()
            }).encode()
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            mock_urlopen.return_value = mock_response

            service.synthesize(
                "Test",
                "de-DE-Wavenet-B",
                str(output_path),
                audio_format="wav"
            )

            call_args = mock_urlopen.call_args
            request = call_args[0][0]
            data = json.loads(request.data.decode())
            assert data["audioConfig"]["audioEncoding"] == "LINEAR16"

    # ========================================================================
    # Output Directory Tests
    # ========================================================================

    def test_get_output_dir_with_project(self, service, tmp_path):
        """Test getting output directory with active project."""
        project_path = tmp_path / "project"
        project_path.mkdir()

        service.project_store = Mock()
        service.project_store.get_active_project.return_value = {
            "path": str(project_path)
        }

        result = service.get_output_dir()

        assert result == str(project_path / "audio")
        assert (project_path / "audio").exists()

    def test_get_output_dir_no_project(self, service):
        """Test getting output directory without active project."""
        service.project_store = Mock()
        service.project_store.get_active_project.return_value = None

        result = service.get_output_dir()
        assert result is None

    # ========================================================================
    # Filename Generation Tests
    # ========================================================================

    def test_generate_filename_default_prefix(self, service):
        """Test filename generation with default prefix."""
        filename = service.generate_filename()

        assert filename.startswith("narration_")
        assert filename.endswith(".mp3")

    def test_generate_filename_custom_prefix(self, service):
        """Test filename generation with custom prefix."""
        filename = service.generate_filename("voiceover")

        assert filename.startswith("voiceover_")
        assert filename.endswith(".mp3")

    def test_generate_filename_contains_timestamp(self, service):
        """Test that filename contains timestamp."""
        filename = service.generate_filename()

        # Should contain date pattern YYYYMMDD
        parts = filename.split("_")
        assert len(parts) >= 2
        # The timestamp part should be numeric
        timestamp_part = parts[1].replace(".mp3", "")
        assert timestamp_part[:8].isdigit()
