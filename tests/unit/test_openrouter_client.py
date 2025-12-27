"""Tests for OpenRouterClient - LLM-based storyboard generation via OpenRouter API."""
import json
import os
import pytest
from unittest.mock import MagicMock, Mock, patch

import requests

from infrastructure.openrouter_client import OpenRouterClient, OPENROUTER_API_URL
from domain.exceptions import (
    OpenRouterAPIError,
    OpenRouterAuthError,
    OpenRouterRateLimitError,
)


@pytest.fixture
def client():
    """Create OpenRouterClient with test API key."""
    return OpenRouterClient(api_key="test-api-key-123")


@pytest.fixture
def mock_response():
    """Create a mock response object."""
    response = Mock()
    response.status_code = 200
    response.text = ""
    response.json.return_value = {
        "choices": [{
            "message": {
                "content": '{"shots": [{"scene": "test"}]}'
            }
        }]
    }
    return response


class TestOpenRouterClientInit:
    """Tests for OpenRouterClient initialization."""

    def test_init_stores_api_key(self):
        """API key is stored."""
        client = OpenRouterClient(api_key="my-key")
        assert client.api_key == "my-key"

    def test_init_creates_session(self):
        """Creates requests session."""
        client = OpenRouterClient(api_key="my-key")
        assert isinstance(client.session, requests.Session)

    def test_init_sets_headers(self):
        """Session has correct headers."""
        client = OpenRouterClient(api_key="test-key")
        headers = client.session.headers

        assert headers["Authorization"] == "Bearer test-key"
        assert headers["Content-Type"] == "application/json"
        assert "HTTP-Referer" in headers
        assert "X-Title" in headers


class TestExtractJson:
    """Tests for _extract_json method."""

    def test_extract_from_code_block(self, client):
        """Extract JSON from markdown code block."""
        text = '''Here is the result:
```json
{"shots": [{"scene": "test"}]}
```
'''
        result = client._extract_json(text)
        assert result == '{"shots": [{"scene": "test"}]}'

    def test_extract_from_code_block_no_language(self, client):
        """Extract JSON from code block without language specifier."""
        text = '''Result:
```
{"data": "value"}
```
'''
        result = client._extract_json(text)
        assert result == '{"data": "value"}'

    def test_extract_raw_json(self, client):
        """Extract raw JSON without code block."""
        text = 'Some text {"key": "value"} more text'
        result = client._extract_json(text)
        assert result == '{"key": "value"}'

    def test_extract_nested_json(self, client):
        """Extract nested JSON object."""
        text = '{"outer": {"inner": {"deep": "value"}}}'
        result = client._extract_json(text)
        data = json.loads(result)
        assert data["outer"]["inner"]["deep"] == "value"

    def test_extract_json_with_arrays(self, client):
        """Extract JSON with arrays."""
        text = '{"items": [1, 2, {"nested": true}]}'
        result = client._extract_json(text)
        data = json.loads(result)
        assert len(data["items"]) == 3

    def test_extract_no_json(self, client):
        """Return stripped text when no JSON found."""
        text = "This is just plain text"
        result = client._extract_json(text)
        assert result == "This is just plain text"

    def test_extract_complex_storyboard(self, client):
        """Extract complex storyboard JSON."""
        text = '''```json
{
    "shots": [
        {"id": 1, "scene": "Opening shot", "duration": 5.0},
        {"id": 2, "scene": "Character intro", "duration": 10.0}
    ],
    "metadata": {"title": "My Video"}
}
```'''
        result = client._extract_json(text)
        data = json.loads(result)
        assert len(data["shots"]) == 2
        assert data["metadata"]["title"] == "My Video"


class TestAllowSensitiveLogs:
    """Tests for _allow_sensitive_logs method."""

    def test_allow_when_env_set(self, client):
        """Returns True when CINDERGRACE_LLM_DEBUG=1."""
        with patch.dict(os.environ, {"CINDERGRACE_LLM_DEBUG": "1"}):
            assert client._allow_sensitive_logs() is True

    def test_deny_when_env_not_set(self, client):
        """Returns False when env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Make sure CINDERGRACE_LLM_DEBUG is not set
            os.environ.pop("CINDERGRACE_LLM_DEBUG", None)
            assert client._allow_sensitive_logs() is False

    def test_deny_when_env_wrong_value(self, client):
        """Returns False when env var has wrong value."""
        with patch.dict(os.environ, {"CINDERGRACE_LLM_DEBUG": "true"}):
            assert client._allow_sensitive_logs() is False

    def test_deny_when_env_empty(self, client):
        """Returns False when env var is empty."""
        with patch.dict(os.environ, {"CINDERGRACE_LLM_DEBUG": ""}):
            assert client._allow_sensitive_logs() is False


class TestLogPreview:
    """Tests for _log_preview method."""

    def test_log_preview_sensitive_enabled(self, client):
        """Logs preview when sensitive logging enabled."""
        with patch.dict(os.environ, {"CINDERGRACE_LLM_DEBUG": "1"}):
            with patch("infrastructure.openrouter_client.logger") as mock_logger:
                client._log_preview("Test", "Hello World")
                mock_logger.debug.assert_called_once()
                call_args = mock_logger.debug.call_args[0][0]
                assert "Hello World" in call_args

    def test_log_preview_sensitive_disabled(self, client):
        """Logs only length when sensitive logging disabled."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("CINDERGRACE_LLM_DEBUG", None)
            with patch("infrastructure.openrouter_client.logger") as mock_logger:
                client._log_preview("Test", "Secret data")
                mock_logger.debug.assert_called_once()
                call_args = mock_logger.debug.call_args[0][0]
                assert "Secret data" not in call_args
                assert "redacted" in call_args

    def test_log_preview_truncates_long_text(self, client):
        """Truncates long text in preview."""
        long_text = "x" * 500
        with patch.dict(os.environ, {"CINDERGRACE_LLM_DEBUG": "1"}):
            with patch("infrastructure.openrouter_client.logger") as mock_logger:
                client._log_preview("Test", long_text, limit=100)
                call_args = mock_logger.debug.call_args[0][0]
                assert "..." in call_args


class TestGenerateStoryboard:
    """Tests for generate_storyboard method."""

    def test_generate_no_api_key(self):
        """Raises error when no API key."""
        client = OpenRouterClient(api_key="")
        with pytest.raises(OpenRouterAuthError):
            client.generate_storyboard(
                idea="test",
                model="test-model",
                system_prompt="test"
            )

    def test_generate_success(self, client, mock_response):
        """Successfully generates storyboard."""
        with patch.object(client.session, "post", return_value=mock_response):
            result = client.generate_storyboard(
                idea="A short video about cats",
                model="anthropic/claude-sonnet-4",
                system_prompt="Generate a storyboard"
            )

            assert "shots" in result
            assert len(result["shots"]) == 1

    def test_generate_auth_error(self, client):
        """Raises auth error on 401."""
        mock_resp = Mock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"

        with patch.object(client.session, "post", return_value=mock_resp):
            with pytest.raises(OpenRouterAuthError) as exc_info:
                client.generate_storyboard(
                    idea="test",
                    model="test-model",
                    system_prompt="test"
                )
            assert exc_info.value.status_code == 401

    def test_generate_rate_limit_error(self, client):
        """Raises rate limit error on 429."""
        mock_resp = Mock()
        mock_resp.status_code = 429
        mock_resp.text = "Rate limit exceeded"

        with patch.object(client.session, "post", return_value=mock_resp):
            with pytest.raises(OpenRouterRateLimitError) as exc_info:
                client.generate_storyboard(
                    idea="test",
                    model="test-model",
                    system_prompt="test"
                )
            assert exc_info.value.status_code == 429

    def test_generate_api_error(self, client):
        """Raises API error on other status codes."""
        mock_resp = Mock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal server error"

        with patch.object(client.session, "post", return_value=mock_resp):
            with pytest.raises(OpenRouterAPIError) as exc_info:
                client.generate_storyboard(
                    idea="test",
                    model="test-model",
                    system_prompt="test"
                )
            assert exc_info.value.status_code == 500

    def test_generate_invalid_response_format(self, client):
        """Raises error on invalid response format."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}  # Missing 'choices'

        with patch.object(client.session, "post", return_value=mock_resp):
            with pytest.raises(OpenRouterAPIError) as exc_info:
                client.generate_storyboard(
                    idea="test",
                    model="test-model",
                    system_prompt="test"
                )
            assert "Invalid response format" in str(exc_info.value)

    def test_generate_empty_choices(self, client):
        """Raises error when choices is empty."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": []}

        with patch.object(client.session, "post", return_value=mock_resp):
            with pytest.raises(OpenRouterAPIError):
                client.generate_storyboard(
                    idea="test",
                    model="test-model",
                    system_prompt="test"
                )

    def test_generate_timeout(self, client):
        """Raises error on timeout."""
        with patch.object(client.session, "post", side_effect=requests.exceptions.Timeout()):
            with pytest.raises(OpenRouterAPIError) as exc_info:
                client.generate_storyboard(
                    idea="test",
                    model="test-model",
                    system_prompt="test"
                )
            assert "timed out" in str(exc_info.value)

    def test_generate_connection_error(self, client):
        """Raises error on connection failure."""
        with patch.object(client.session, "post", side_effect=requests.exceptions.ConnectionError("Failed")):
            with pytest.raises(OpenRouterAPIError) as exc_info:
                client.generate_storyboard(
                    idea="test",
                    model="test-model",
                    system_prompt="test"
                )
            assert "connect" in str(exc_info.value).lower()

    def test_generate_json_decode_error(self, client):
        """Raises error when JSON parsing fails."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {
                    "content": "This is not valid JSON at all"
                }
            }]
        }

        with patch.object(client.session, "post", return_value=mock_resp):
            with pytest.raises(OpenRouterAPIError) as exc_info:
                client.generate_storyboard(
                    idea="test",
                    model="test-model",
                    system_prompt="test"
                )
            assert "JSON" in str(exc_info.value)

    def test_generate_sends_correct_payload(self, client, mock_response):
        """Sends correct payload to API."""
        with patch.object(client.session, "post", return_value=mock_response) as mock_post:
            client.generate_storyboard(
                idea="My video idea",
                model="anthropic/claude-sonnet-4",
                system_prompt="Generate JSON",
                temperature=0.5,
                max_tokens=2000
            )

            call_kwargs = mock_post.call_args
            payload = call_kwargs.kwargs["json"]

            assert payload["model"] == "anthropic/claude-sonnet-4"
            assert payload["temperature"] == 0.5
            assert payload["max_tokens"] == 2000
            assert len(payload["messages"]) == 2
            assert payload["messages"][0]["role"] == "system"
            assert payload["messages"][1]["role"] == "user"
            assert payload["messages"][1]["content"] == "My video idea"

    def test_generate_uses_api_url(self, client, mock_response):
        """Sends request to correct API URL."""
        with patch.object(client.session, "post", return_value=mock_response) as mock_post:
            client.generate_storyboard(
                idea="test",
                model="test-model",
                system_prompt="test"
            )

            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args.args[0] == OPENROUTER_API_URL


class TestTestConnection:
    """Tests for test_connection method."""

    def test_connection_no_api_key(self):
        """Raises error when no API key."""
        client = OpenRouterClient(api_key="")
        with pytest.raises(OpenRouterAuthError):
            client.test_connection()

    def test_connection_success(self, client):
        """Returns success on valid connection."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": "OK"}}]}

        with patch.object(client.session, "post", return_value=mock_resp):
            result = client.test_connection()

            assert result["connected"] is True
            assert "successful" in result["message"].lower()

    def test_connection_auth_error(self, client):
        """Raises auth error on 401."""
        mock_resp = Mock()
        mock_resp.status_code = 401

        with patch.object(client.session, "post", return_value=mock_resp):
            with pytest.raises(OpenRouterAuthError):
                client.test_connection()

    def test_connection_rate_limit(self, client):
        """Raises rate limit error on 429."""
        mock_resp = Mock()
        mock_resp.status_code = 429

        with patch.object(client.session, "post", return_value=mock_resp):
            with pytest.raises(OpenRouterRateLimitError):
                client.test_connection()

    def test_connection_api_error(self, client):
        """Raises API error on other status codes."""
        mock_resp = Mock()
        mock_resp.status_code = 503

        with patch.object(client.session, "post", return_value=mock_resp):
            with pytest.raises(OpenRouterAPIError):
                client.test_connection()

    def test_connection_request_exception(self, client):
        """Raises API error on request exception."""
        with patch.object(client.session, "post", side_effect=requests.exceptions.RequestException("Error")):
            with pytest.raises(OpenRouterAPIError) as exc_info:
                client.test_connection()
            assert "failed" in str(exc_info.value).lower()

    def test_connection_uses_cheap_model(self, client):
        """Uses cheap model for testing."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": "OK"}}]}

        with patch.object(client.session, "post", return_value=mock_resp) as mock_post:
            client.test_connection()

            payload = mock_post.call_args.kwargs["json"]
            assert payload["model"] == "openai/gpt-4o-mini"
            assert payload["max_tokens"] == 10


class TestGetAvailableModels:
    """Tests for get_available_models method."""

    def test_returns_list(self, client):
        """Returns a list of models."""
        models = client.get_available_models()
        assert isinstance(models, list)
        assert len(models) > 0

    def test_contains_claude_models(self, client):
        """Contains Claude models."""
        models = client.get_available_models()
        claude_models = [m for m in models if "claude" in m.lower()]
        assert len(claude_models) >= 1

    def test_contains_gpt_models(self, client):
        """Contains GPT models."""
        models = client.get_available_models()
        gpt_models = [m for m in models if "gpt" in m.lower()]
        assert len(gpt_models) >= 1

    def test_contains_gemini_models(self, client):
        """Contains Gemini models."""
        models = client.get_available_models()
        gemini_models = [m for m in models if "gemini" in m.lower()]
        assert len(gemini_models) >= 1

    def test_contains_llama_models(self, client):
        """Contains Llama models."""
        models = client.get_available_models()
        llama_models = [m for m in models if "llama" in m.lower()]
        assert len(llama_models) >= 1

    def test_models_have_provider_prefix(self, client):
        """All models have provider prefix format."""
        models = client.get_available_models()
        for model in models:
            assert "/" in model, f"Model {model} should have provider/model format"


class TestOpenRouterAPIUrl:
    """Tests for API URL constant."""

    def test_api_url_is_https(self):
        """API URL uses HTTPS."""
        assert OPENROUTER_API_URL.startswith("https://")

    def test_api_url_is_openrouter(self):
        """API URL is OpenRouter."""
        assert "openrouter.ai" in OPENROUTER_API_URL

    def test_api_url_is_chat_completions(self):
        """API URL is chat completions endpoint."""
        assert "chat/completions" in OPENROUTER_API_URL
