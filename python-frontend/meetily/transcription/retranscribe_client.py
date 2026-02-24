"""HTTP client for the queued full-audio retranscription API."""

from __future__ import annotations

import logging
from pathlib import Path

import requests

log = logging.getLogger(__name__)

_SUBMIT_TIMEOUT = 60  # file upload can be slow for large WAVs
_POLL_TIMEOUT = 10


class RetranscribeClient:
    """Client for the backend's queued transcription endpoint."""

    def __init__(self, backend_url: str = "http://localhost:5167") -> None:
        self._backend_url = backend_url.rstrip("/")

    def submit(
        self,
        wav_path: str,
        meeting_name: str = "",
        asr_url: str = "",
        asr_api_key: str = "",
        asr_model: str = "whisper-1",
    ) -> dict:
        """Submit a WAV file for queued transcription.

        Returns:
            dict with keys: job_id, status, queue_position, message
        """
        url = f"{self._backend_url}/api/transcribe"
        path = Path(wav_path)
        if not path.exists():
            raise FileNotFoundError(f"WAV file not found: {wav_path}")

        with open(path, "rb") as f:
            files = {"file": (path.name, f, "audio/wav")}
            data = {
                "meeting_name": meeting_name,
                "asr_url": asr_url,
                "asr_api_key": asr_api_key,
                "asr_model": asr_model,
            }
            resp = requests.post(
                url, files=files, data=data, timeout=_SUBMIT_TIMEOUT
            )

        resp.raise_for_status()
        result = resp.json()
        log.info("Transcription job submitted: %s", result.get("job_id"))
        return result

    def poll_status(self, job_id: str) -> dict:
        """Poll the status of a transcription job.

        Returns:
            dict with keys: job_id, status, and status-specific fields
            (queue_position, progress, transcript, segments, error, etc.)
        """
        url = f"{self._backend_url}/api/transcribe/{job_id}/status"
        resp = requests.get(url, timeout=_POLL_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def cancel(self, job_id: str) -> dict:
        """Cancel a queued or processing transcription job.

        Returns:
            dict with keys: job_id, status
        """
        url = f"{self._backend_url}/api/transcribe/{job_id}"
        resp = requests.delete(url, timeout=_POLL_TIMEOUT)
        resp.raise_for_status()
        result = resp.json()
        log.info("Transcription job cancelled: %s", job_id)
        return result
