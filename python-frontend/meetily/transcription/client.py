"""HTTP client for OpenAI-compatible ASR endpoint.

Sends audio segments as WAV files to POST /v1/audio/transcriptions
and returns the transcribed text.
"""

from __future__ import annotations

import io
import logging

import numpy as np
import requests
import soundfile as sf

log = logging.getLogger(__name__)

_TIMEOUT = 30  # seconds


class TranscriptionClient:
    """Sends audio to an OpenAI-compatible transcription endpoint."""

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    def update_settings(self, base_url: str, api_key: str = "") -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16_000) -> str:
        """Transcribe an audio segment.

        Args:
            audio: float32 mono audio array.
            sample_rate: Sample rate of the audio.

        Returns:
            Transcribed text.

        Raises:
            requests.RequestException: On network / HTTP errors.
        """
        # Convert numpy array → WAV bytes in memory
        buf = io.BytesIO()
        sf.write(buf, audio, sample_rate, format="WAV", subtype="PCM_16")
        buf.seek(0)

        url = f"{self._base_url}/v1/audio/transcriptions"

        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            response = requests.post(
                url,
                files={"file": ("audio.wav", buf, "audio/wav")},
                data={
                    "model": "whisper-1",
                    "response_format": "json",
                },
                headers=headers,
                timeout=_TIMEOUT,
            )
        except requests.ConnectionError:
            raise requests.ConnectionError(
                f"Cannot reach ASR endpoint at {self._base_url}. Check Settings."
            )
        except requests.Timeout:
            raise requests.Timeout(
                f"ASR endpoint timed out ({_TIMEOUT}s). The server may be overloaded."
            )

        if response.status_code in (401, 403):
            raise requests.HTTPError(
                "ASR authentication failed. Check your API key in Settings."
            )
        if response.status_code == 404:
            raise requests.HTTPError(
                f"ASR endpoint not found at {url}. Check the URL in Settings."
            )
        if not response.ok:
            raise requests.HTTPError(
                f"ASR error: {response.status_code} {response.reason}"
            )

        result = response.json()
        text = result.get("text", "").strip()

        if text:
            log.info("Transcribed: %s", text[:80])
        return text
