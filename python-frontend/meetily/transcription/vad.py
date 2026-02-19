"""Voice Activity Detection using webrtcvad.

Processes raw audio chunks from the audio callback, detects speech
segments, and returns completed segments for transcription.
"""

from __future__ import annotations

import logging

import numpy as np
import webrtcvad

log = logging.getLogger(__name__)

# webrtcvad requires 16-bit PCM at specific frame durations
_FRAME_DURATION_MS = 30
_SAMPLE_RATE = 16_000
_FRAME_SAMPLES = _SAMPLE_RATE * _FRAME_DURATION_MS // 1000  # 480

# Thresholds
_SPEECH_START_FRAMES = 3  # ~90ms of speech to trigger start
_SILENCE_END_FRAMES = 15  # ~450ms of silence to end segment
_MIN_SEGMENT_SECONDS = 0.5
_MAX_SEGMENT_SECONDS = 30.0
_MIN_SEGMENT_SAMPLES = int(_MIN_SEGMENT_SECONDS * _SAMPLE_RATE)
_MAX_SEGMENT_SAMPLES = int(_MAX_SEGMENT_SECONDS * _SAMPLE_RATE)


class VadProcessor:
    """Detects speech segments from a continuous audio stream.

    Feed audio chunks via process_chunk(). When a speech segment
    completes (speaker stops talking), it is returned as a numpy array.
    """

    def __init__(self, aggressiveness: int = 2) -> None:
        self._vad = webrtcvad.Vad(aggressiveness)
        self._remainder = np.array([], dtype=np.float32)
        self.reset()

    def reset(self) -> None:
        """Clear all state for a new recording."""
        self._is_speaking = False
        self._speech_chunks: list[np.ndarray] = []
        self._speech_sample_count = 0
        self._silence_frames = 0
        self._speech_frames = 0
        self._remainder = np.array([], dtype=np.float32)

    def process_chunk(self, audio: np.ndarray) -> list[np.ndarray]:
        """Process an audio chunk and return any completed speech segments.

        Args:
            audio: float32 mono audio at 16kHz.

        Returns:
            List of completed speech segments (usually 0 or 1).
        """
        # Prepend leftover samples from previous call
        if len(self._remainder) > 0:
            audio = np.concatenate([self._remainder, audio])
            self._remainder = np.array([], dtype=np.float32)

        completed: list[np.ndarray] = []
        offset = 0

        while offset + _FRAME_SAMPLES <= len(audio):
            frame = audio[offset : offset + _FRAME_SAMPLES]
            offset += _FRAME_SAMPLES

            is_speech = self._classify_frame(frame)

            if self._is_speaking:
                self._speech_chunks.append(frame)
                self._speech_sample_count += _FRAME_SAMPLES

                if is_speech:
                    self._silence_frames = 0
                else:
                    self._silence_frames += 1

                # End of speech: enough silence
                if self._silence_frames >= _SILENCE_END_FRAMES:
                    segment = self._finalize_segment()
                    if segment is not None:
                        completed.append(segment)

                # Force-flush long segments to bound latency
                elif self._speech_sample_count >= _MAX_SEGMENT_SAMPLES:
                    log.debug("Force-flushing long segment (%.1fs)", _MAX_SEGMENT_SECONDS)
                    segment = self._finalize_segment()
                    if segment is not None:
                        completed.append(segment)

            else:
                if is_speech:
                    self._speech_frames += 1
                    # Buffer pre-speech audio so we don't clip the start
                    self._speech_chunks.append(frame)
                    self._speech_sample_count += _FRAME_SAMPLES

                    if self._speech_frames >= _SPEECH_START_FRAMES:
                        self._is_speaking = True
                        self._silence_frames = 0
                        log.debug("Speech started")
                else:
                    self._speech_frames = 0
                    # Discard buffered pre-speech if speech didn't confirm
                    if self._speech_chunks:
                        self._speech_chunks.clear()
                        self._speech_sample_count = 0

        # Save leftover samples for next call
        if offset < len(audio):
            self._remainder = audio[offset:]

        return completed

    def flush(self) -> np.ndarray | None:
        """Flush any remaining speech at end of recording."""
        if self._speech_chunks:
            return self._finalize_segment()
        return None

    def _classify_frame(self, frame: np.ndarray) -> bool:
        """Run webrtcvad on a single frame."""
        # Convert float32 [-1, 1] → int16 bytes
        pcm = (frame * 32767).astype(np.int16).tobytes()
        return self._vad.is_speech(pcm, _SAMPLE_RATE)

    def _finalize_segment(self) -> np.ndarray | None:
        """Concatenate buffered speech and reset state."""
        if not self._speech_chunks:
            return None

        segment = np.concatenate(self._speech_chunks)

        # Reset state
        self._is_speaking = False
        self._speech_chunks.clear()
        self._speech_sample_count = 0
        self._silence_frames = 0
        self._speech_frames = 0

        # Reject too-short segments
        if len(segment) < _MIN_SEGMENT_SAMPLES:
            duration = len(segment) / _SAMPLE_RATE
            log.debug("Discarding short segment (%.2fs)", duration)
            return None

        duration = len(segment) / _SAMPLE_RATE
        log.info("Speech segment: %.1fs (%d samples)", duration, len(segment))
        return segment
