"""HTTP client for OpenAI-compatible chat completions endpoint.

Sends a meeting transcript to an LLM and returns a structured summary.
"""

from __future__ import annotations

import logging

import requests

log = logging.getLogger(__name__)

_TIMEOUT = 60  # seconds — summaries can be slow for long transcripts

_SYSTEM_PROMPT = (
    "You are a meeting assistant. Summarize the following meeting transcript.\n\n"
    "Output valid Markdown with the following structure:\n\n"
    "## Overview\n"
    "A 1-2 sentence summary of what the meeting was about.\n\n"
    "## Key Topics Discussed\n"
    "- Topic 1\n"
    "- Topic 2\n\n"
    "## Decisions Made\n"
    "- Decision 1\n"
    "- Decision 2\n\n"
    "## Action Items\n"
    "- [ ] Action item with owner if mentioned\n"
    "- [ ] Another action item\n\n"
    "Rules:\n"
    "- Use proper Markdown formatting (headers, bullet points, checkboxes for action items)\n"
    "- Be concise. Each bullet should be one clear sentence.\n"
    "- If a section has no items, write 'None.'\n"
    "- Do NOT wrap the output in a code fence. Output raw Markdown directly."
)


class SummarizationClient:
    """Sends transcript to an OpenAI-compatible chat completions endpoint."""

    def __init__(self, base_url: str, api_key: str = "", model: str = "gpt-4o-mini") -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model

    def update_settings(self, base_url: str, api_key: str = "", model: str = "gpt-4o-mini") -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model

    def summarize(self, transcript: str) -> str:
        """Summarize a meeting transcript.

        Args:
            transcript: Full transcript text (all segments joined).

        Returns:
            Summary text from the LLM.

        Raises:
            requests.RequestException: On network / HTTP errors.
        """
        url = f"{self._base_url}/v1/chat/completions"

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": transcript},
            ],
        }

        response = requests.post(url, json=payload, headers=headers, timeout=_TIMEOUT)
        response.raise_for_status()

        result = response.json()
        text = result["choices"][0]["message"]["content"].strip()

        if text:
            log.info("Summary generated (%d chars)", len(text))
        return text
