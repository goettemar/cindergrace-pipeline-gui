"""OpenRouter API client for LLM-based storyboard generation.

Uses the OpenRouter API to access various LLM models (Claude, GPT-4, Llama, etc.)
for generating structured storyboard JSON from natural language descriptions.
"""
import json
import os
import re
from typing import Any, Dict, Optional

import requests

from domain.exceptions import (
    OpenRouterAPIError,
    OpenRouterAuthError,
    OpenRouterRateLimitError,
)
from infrastructure.logger import get_logger

logger = get_logger(__name__)

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterClient:
    """Client for OpenRouter API to generate storyboards via LLM."""

    def __init__(self, api_key: str):
        """Initialize client with API key.

        Args:
            api_key: OpenRouter API key
        """
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://cindergrace.local",
            "X-Title": "Cindergrace Pipeline",
            "Content-Type": "application/json",
        })

    def _extract_json(self, text: str) -> str:
        """Extract JSON from LLM response text.

        Handles cases where LLM wraps JSON in markdown code blocks.

        Args:
            text: Raw LLM response text

        Returns:
            Extracted JSON string
        """
        logger.debug(f"Extracting JSON from text ({len(text)} chars)")

        # Try to find JSON in markdown code block
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if json_match:
            extracted = json_match.group(1).strip()
            logger.debug(f"Found JSON in code block ({len(extracted)} chars)")
            return extracted

        # Try to find raw JSON (starts with {)
        json_start = text.find('{')
        if json_start != -1:
            # Find matching closing brace
            brace_count = 0
            last_close = -1
            for i, char in enumerate(text[json_start:]):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        last_close = json_start + i + 1
                        # Don't break - continue to find the outermost closing brace
                        extracted = text[json_start:last_close]
                        logger.debug(f"Found raw JSON ({len(extracted)} chars)")
                        return extracted

            # If we found opening but no matching close, return what we have
            if last_close > 0:
                return text[json_start:last_close]

        logger.warning(f"Could not extract JSON, returning raw text")
        return text.strip()

    def _allow_sensitive_logs(self) -> bool:
        """Check if sensitive LLM logging is explicitly enabled."""
        return os.environ.get("CINDERGRACE_LLM_DEBUG", "").strip() == "1"

    def _log_preview(self, label: str, text: str, limit: int = 200):
        """Log a preview or redacted placeholder for sensitive text."""
        if self._allow_sensitive_logs():
            preview = text[:limit]
            suffix = "..." if len(text) > limit else ""
            logger.debug(f"{label} preview: {preview}{suffix}")
        else:
            logger.debug(f"{label} length: {len(text)} chars (redacted)")

    def generate_storyboard(
        self,
        idea: str,
        model: str,
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> Dict[str, Any]:
        """Generate a storyboard JSON from a natural language idea.

        Args:
            idea: User's video/storyboard idea description
            model: OpenRouter model ID (e.g., "anthropic/claude-sonnet-4")
            system_prompt: System prompt with schema and examples
            temperature: LLM temperature (0.0-1.0)
            max_tokens: Maximum tokens in response

        Returns:
            Parsed storyboard dictionary

        Raises:
            OpenRouterAuthError: If API key is invalid
            OpenRouterRateLimitError: If rate limit exceeded
            OpenRouterAPIError: For other API errors
        """
        if not self.api_key:
            raise OpenRouterAuthError("OpenRouter API key not configured")

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": idea},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        logger.info(f"Requesting storyboard generation from {model}")
        self._log_preview("Idea", idea, limit=120)

        try:
            response = self.session.post(
                OPENROUTER_API_URL,
                json=payload,
                timeout=120,  # LLM can take a while
            )

            # Handle specific error codes
            if response.status_code == 401:
                raise OpenRouterAuthError(
                    "Invalid OpenRouter API key",
                    status_code=401,
                    response_body=response.text,
                )
            elif response.status_code == 429:
                raise OpenRouterRateLimitError(
                    "OpenRouter rate limit exceeded. Please wait and try again.",
                    status_code=429,
                    response_body=response.text,
                )
            elif response.status_code != 200:
                raise OpenRouterAPIError(
                    f"OpenRouter API error: {response.status_code}",
                    status_code=response.status_code,
                    response_body=response.text,
                )

            result = response.json()

            # Extract content from response
            if "choices" not in result or not result["choices"]:
                raise OpenRouterAPIError(
                    "Invalid response format from OpenRouter",
                    response_body=json.dumps(result),
                )

            content = result["choices"][0]["message"]["content"]
            logger.info(f"LLM response received: {len(content)} chars")
            self._log_preview("LLM response", content, limit=500)

            # Extract and parse JSON
            json_str = self._extract_json(content)
            logger.info(f"Extracted JSON: {len(json_str)} chars")
            storyboard = json.loads(json_str)

            logger.info(f"Successfully generated storyboard with {len(storyboard.get('shots', []))} shots")
            return storyboard

        except requests.exceptions.Timeout:
            raise OpenRouterAPIError("OpenRouter request timed out after 120 seconds")
        except requests.exceptions.ConnectionError as e:
            raise OpenRouterAPIError(f"Failed to connect to OpenRouter: {e}")
        except json.JSONDecodeError as e:
            raise OpenRouterAPIError(f"Failed to parse LLM response as JSON: {e}")

    def test_connection(self) -> Dict[str, Any]:
        """Test the API connection with a minimal request.

        Returns:
            Dict with connection status and model info

        Raises:
            OpenRouterAPIError: If connection fails
        """
        if not self.api_key:
            raise OpenRouterAuthError("OpenRouter API key not configured")

        try:
            # Use a minimal request to test auth
            payload = {
                "model": "openai/gpt-4o-mini",  # Cheapest model for testing
                "messages": [
                    {"role": "user", "content": "Say 'OK'"},
                ],
                "max_tokens": 10,
            }

            response = self.session.post(
                OPENROUTER_API_URL,
                json=payload,
                timeout=30,
            )

            if response.status_code == 401:
                raise OpenRouterAuthError("Invalid API key")
            elif response.status_code == 429:
                raise OpenRouterRateLimitError("Rate limit exceeded")
            elif response.status_code != 200:
                raise OpenRouterAPIError(
                    f"API error: {response.status_code}",
                    status_code=response.status_code,
                )

            return {
                "connected": True,
                "message": "OpenRouter connection successful",
            }

        except requests.exceptions.RequestException as e:
            raise OpenRouterAPIError(f"Connection failed: {e}")

    def get_available_models(self) -> list:
        """Get list of popular models for storyboard generation.

        Returns:
            List of model IDs suitable for structured output
        """
        # Curated list of models good for JSON generation
        return [
            "anthropic/claude-sonnet-4",
            "anthropic/claude-3.5-sonnet",
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "google/gemini-pro-1.5",
            "meta-llama/llama-3.1-70b-instruct",
            "meta-llama/llama-3.1-8b-instruct",
            "mistralai/mistral-large",
        ]


__all__ = ["OpenRouterClient"]
