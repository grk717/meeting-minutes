"""Transcription manager: VAD → queue → HTTP worker → callbacks.

Orchestrates the full pipeline from raw audio chunks to transcribed text.
Thread-safe: feed_audio() is called from the audio callback thread,
the worker runs in its own daemon thread, and callbacks are invoked
from the worker thread (UI must bridge via Qt signals).
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Callable

import numpy as np

from meetily.transcription.client import TranscriptionClient
from meetily.transcription.vad import VadProcessor

log = logging.getLogger(__name__)


class TranscriptionManager:
    """Manages VAD segmentation and async transcription of audio."""

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._vad = VadProcessor()
        self._client = TranscriptionClient(base_url, api_key)
        self._queue: queue.Queue[np.ndarray | None] = queue.Queue()
        self._worker: threading.Thread | None = None
        self._running = False
        self._recording_start: float = 0.0
        self._samples_fed: int = 0

        # Callbacks (called from worker thread)
        self.on_transcript: Callable[[str, str], None] | None = None
        self.on_error: Callable[[str], None] | None = None

    def update_settings(self, base_url: str, api_key: str = "") -> None:
        """Update ASR endpoint settings (can be called while running)."""
        self._client.update_settings(base_url, api_key)

    def start(self) -> None:
        """Start the transcription pipeline."""
        if self._running:
            return

        self._vad.reset()
        # Drain any leftover items from a previous session
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

        self._running = True
        self._recording_start = time.monotonic()
        self._samples_fed = 0

        self._worker = threading.Thread(target=self._worker_run, daemon=True)
        self._worker.start()
        log.info("Transcription pipeline started")

    def stop(self) -> None:
        """Stop the pipeline, flushing any remaining speech."""
        if not self._running:
            return

        self._running = False

        # Flush VAD — get any remaining speech
        remaining = self._vad.flush()
        if remaining is not None:
            self._queue.put(remaining)

        # Sentinel to stop worker
        self._queue.put(None)

        if self._worker is not None:
            self._worker.join(timeout=35)
            self._worker = None

        log.info("Transcription pipeline stopped")

    def feed_audio(self, audio: np.ndarray) -> None:
        """Feed a raw audio chunk from the audio callback.

        Thread-safe. Called from the audio capture thread.
        """
        if not self._running:
            return

        self._samples_fed += len(audio)

        segments = self._vad.process_chunk(audio)
        for segment in segments:
            self._queue.put(segment)

    def _worker_run(self) -> None:
        """Worker loop: consume segments from queue and transcribe."""
        log.debug("Transcription worker started")

        while True:
            try:
                segment = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue

            if segment is None:
                break

            timestamp = self._format_timestamp()

            try:
                text = self._client.transcribe(segment)
            except Exception as e:
                log.error("Transcription failed: %s", e)
                if self.on_error:
                    self.on_error(f"Transcription error: {e}")
                continue

            if text and self.on_transcript:
                self.on_transcript(text, timestamp)

        log.debug("Transcription worker stopped")

    def _format_timestamp(self) -> str:
        """Format current recording time as MM:SS."""
        elapsed = time.monotonic() - self._recording_start
        mins = int(elapsed) // 60
        secs = int(elapsed) % 60
        return f"{mins:02d}:{secs:02d}"
