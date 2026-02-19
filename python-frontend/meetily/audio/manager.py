"""Audio capture manager using sounddevice.

Handles microphone and system audio capture, device enumeration,
real-time audio level metering, and WAV file saving.
"""

from __future__ import annotations

import enum
import logging
import platform
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
import sounddevice as sd
import soundfile as sf

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000  # 16 kHz — standard for speech
CHANNELS = 1  # Mono for speech
BLOCK_SIZE = 1024  # ~64ms at 16kHz
LEVEL_SMOOTHING = 0.3  # EMA smoothing for level meter


class RecordingState(enum.Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPING = "stopping"


@dataclass
class AudioDevice:
    """Represents an available audio device."""

    index: int
    name: str
    max_input_channels: int
    max_output_channels: int
    default_samplerate: float
    hostapi_name: str

    @property
    def is_input(self) -> bool:
        return self.max_input_channels > 0

    @property
    def is_output(self) -> bool:
        return self.max_output_channels > 0

    @property
    def is_loopback(self) -> bool:
        """Heuristic: detect loopback/virtual audio devices."""
        name_lower = self.name.lower()
        loopback_hints = [
            "loopback",
            "blackhole",
            "soundflower",
            "virtual",
            "stereo mix",
            "what u hear",
            "wave out",
        ]
        return any(hint in name_lower for hint in loopback_hints)

    def __str__(self) -> str:
        return self.name


@dataclass
class AudioLevels:
    """Current audio levels for UI display."""

    mic_rms: float = 0.0
    mic_peak: float = 0.0
    system_rms: float = 0.0
    system_peak: float = 0.0


class AudioManager:
    """Manages audio capture from microphone and system audio.

    Signals are emitted via callbacks so this module stays UI-agnostic.
    The UI layer wraps these into Qt signals.
    """

    def __init__(self) -> None:
        self._state = RecordingState.IDLE
        self._mic_stream: sd.InputStream | None = None
        self._sys_stream: sd.InputStream | None = None
        self._mic_device: int | None = None
        self._sys_device: int | None = None
        self._save_path: Path | None = None
        self._meeting_name: str = ""

        # Audio buffers (protected by lock)
        self._lock = threading.Lock()
        self._mic_chunks: list[np.ndarray] = []
        self._sys_chunks: list[np.ndarray] = []

        # Level metering (smoothed)
        self._levels = AudioLevels()

        # Callbacks
        self.on_levels_updated: Callable[[AudioLevels], None] | None = None
        self.on_state_changed: Callable[[RecordingState], None] | None = None
        self.on_error: Callable[[str], None] | None = None

    @property
    def state(self) -> RecordingState:
        return self._state

    @property
    def levels(self) -> AudioLevels:
        return self._levels

    # ── Device enumeration ──────────────────────────────────────

    @staticmethod
    def list_devices() -> list[AudioDevice]:
        """List all available audio devices."""
        devices: list[AudioDevice] = []
        hostapis = sd.query_hostapis()

        for info in sd.query_devices():
            hostapi_idx = info["hostapi"]
            hostapi_name = hostapis[hostapi_idx]["name"] if hostapi_idx < len(hostapis) else "Unknown"

            devices.append(
                AudioDevice(
                    index=info["index"],
                    name=info["name"],
                    max_input_channels=info["max_input_channels"],
                    max_output_channels=info["max_output_channels"],
                    default_samplerate=info["default_samplerate"],
                    hostapi_name=hostapi_name,
                )
            )
        return devices

    @staticmethod
    def list_input_devices() -> list[AudioDevice]:
        """List microphone (input) devices."""
        return [d for d in AudioManager.list_devices() if d.is_input]

    @staticmethod
    def list_loopback_devices() -> list[AudioDevice]:
        """List system audio / loopback devices."""
        return [d for d in AudioManager.list_devices() if d.is_input and d.is_loopback]

    @staticmethod
    def default_input_device() -> int | None:
        """Get the default input device index."""
        try:
            info = sd.query_devices(kind="input")
            return info["index"]
        except Exception:
            return None

    # ── Recording control ───────────────────────────────────────

    def start_recording(
        self,
        mic_device: int | None = None,
        system_device: int | None = None,
        meeting_name: str = "",
        save_dir: Path | None = None,
    ) -> None:
        """Start capturing audio from microphone and optionally system audio."""
        if self._state != RecordingState.IDLE:
            log.warning("Cannot start recording: state is %s", self._state)
            return

        self._mic_device = mic_device
        self._sys_device = system_device
        self._meeting_name = meeting_name or f"meeting_{int(time.time())}"

        # Prepare save directory
        if save_dir is None:
            save_dir = Path.home() / "Documents" / "Meetily"
        save_dir.mkdir(parents=True, exist_ok=True)
        self._save_path = save_dir

        # Clear previous buffers
        with self._lock:
            self._mic_chunks.clear()
            self._sys_chunks.clear()

        # Start mic stream
        if mic_device is not None:
            try:
                self._mic_stream = sd.InputStream(
                    device=mic_device,
                    samplerate=SAMPLE_RATE,
                    channels=CHANNELS,
                    blocksize=BLOCK_SIZE,
                    dtype="float32",
                    callback=self._mic_callback,
                )
                self._mic_stream.start()
                log.info("Mic stream started on device %d", mic_device)
            except Exception as e:
                log.error("Failed to start mic stream: %s", e)
                self._emit_error(f"Microphone error: {e}")
                return

        # Start system audio stream (if selected)
        if system_device is not None:
            try:
                self._sys_stream = sd.InputStream(
                    device=system_device,
                    samplerate=SAMPLE_RATE,
                    channels=CHANNELS,
                    blocksize=BLOCK_SIZE,
                    dtype="float32",
                    callback=self._sys_callback,
                )
                self._sys_stream.start()
                log.info("System audio stream started on device %d", system_device)
            except Exception as e:
                log.warning("Failed to start system audio: %s (continuing with mic only)", e)

        self._set_state(RecordingState.RECORDING)

    def stop_recording(self) -> Path | None:
        """Stop recording and save audio to WAV file. Returns the saved file path."""
        if self._state not in (RecordingState.RECORDING, RecordingState.PAUSED):
            log.warning("Cannot stop recording: state is %s", self._state)
            return None

        self._set_state(RecordingState.STOPPING)

        # Stop streams
        if self._mic_stream is not None:
            try:
                self._mic_stream.stop()
                self._mic_stream.close()
            except Exception as e:
                log.warning("Error stopping mic stream: %s", e)
            self._mic_stream = None

        if self._sys_stream is not None:
            try:
                self._sys_stream.stop()
                self._sys_stream.close()
            except Exception as e:
                log.warning("Error stopping system stream: %s", e)
            self._sys_stream = None

        # Save audio
        saved_path = self._save_audio()

        # Reset levels
        self._levels = AudioLevels()
        if self.on_levels_updated:
            self.on_levels_updated(self._levels)

        self._set_state(RecordingState.IDLE)
        return saved_path

    def pause_recording(self) -> None:
        """Pause the current recording."""
        if self._state != RecordingState.RECORDING:
            return
        if self._mic_stream:
            self._mic_stream.stop()
        if self._sys_stream:
            self._sys_stream.stop()
        self._set_state(RecordingState.PAUSED)

    def resume_recording(self) -> None:
        """Resume a paused recording."""
        if self._state != RecordingState.PAUSED:
            return
        if self._mic_stream:
            self._mic_stream.start()
        if self._sys_stream:
            self._sys_stream.start()
        self._set_state(RecordingState.RECORDING)

    # ── Audio callbacks (called from audio thread) ──────────────

    def _mic_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        if status:
            log.debug("Mic status: %s", status)
        if self._state != RecordingState.RECORDING:
            return

        audio = indata[:, 0].copy()

        with self._lock:
            self._mic_chunks.append(audio)

        # Update levels (fast path, no lock needed for atomic float writes)
        rms = float(np.sqrt(np.mean(audio**2)))
        peak = float(np.max(np.abs(audio)))
        self._levels.mic_rms = self._levels.mic_rms * LEVEL_SMOOTHING + rms * (1 - LEVEL_SMOOTHING)
        self._levels.mic_peak = max(peak, self._levels.mic_peak * 0.95)

        if self.on_levels_updated:
            self.on_levels_updated(self._levels)

    def _sys_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        if status:
            log.debug("System audio status: %s", status)
        if self._state != RecordingState.RECORDING:
            return

        audio = indata[:, 0].copy()

        with self._lock:
            self._sys_chunks.append(audio)

        rms = float(np.sqrt(np.mean(audio**2)))
        peak = float(np.max(np.abs(audio)))
        self._levels.system_rms = self._levels.system_rms * LEVEL_SMOOTHING + rms * (1 - LEVEL_SMOOTHING)
        self._levels.system_peak = max(peak, self._levels.system_peak * 0.95)

        if self.on_levels_updated:
            self.on_levels_updated(self._levels)

    # ── Audio saving ────────────────────────────────────────────

    def _save_audio(self) -> Path | None:
        """Mix and save captured audio to WAV file."""
        with self._lock:
            mic_chunks = list(self._mic_chunks)
            sys_chunks = list(self._sys_chunks)

        if not mic_chunks and not sys_chunks:
            log.warning("No audio data captured")
            return None

        # Concatenate chunks
        mic_audio = np.concatenate(mic_chunks) if mic_chunks else np.array([], dtype=np.float32)
        sys_audio = np.concatenate(sys_chunks) if sys_chunks else np.array([], dtype=np.float32)

        # Mix: if both streams, combine them (simple average mix)
        if len(mic_audio) > 0 and len(sys_audio) > 0:
            # Align lengths (pad shorter with zeros)
            max_len = max(len(mic_audio), len(sys_audio))
            if len(mic_audio) < max_len:
                mic_audio = np.pad(mic_audio, (0, max_len - len(mic_audio)))
            if len(sys_audio) < max_len:
                sys_audio = np.pad(sys_audio, (0, max_len - len(sys_audio)))

            # Simple mix with ducking: mic takes priority
            mixed = mic_audio * 0.7 + sys_audio * 0.3

            # Prevent clipping
            max_val = np.max(np.abs(mixed))
            if max_val > 1.0:
                mixed = mixed / max_val
            audio = mixed
        elif len(mic_audio) > 0:
            audio = mic_audio
        else:
            audio = sys_audio

        # Check minimum duration (2 seconds)
        duration = len(audio) / SAMPLE_RATE
        if duration < 2.0:
            log.warning("Recording too short (%.1fs), discarding", duration)
            return None

        # Save to WAV
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in self._meeting_name)
        filename = f"{timestamp}_{safe_name}.wav"
        filepath = self._save_path / filename

        sf.write(str(filepath), audio, SAMPLE_RATE)
        log.info("Saved recording: %s (%.1fs)", filepath, duration)
        return filepath

    # ── Internal helpers ────────────────────────────────────────

    def _set_state(self, state: RecordingState) -> None:
        self._state = state
        log.info("Recording state: %s", state.value)
        if self.on_state_changed:
            self.on_state_changed(state)

    def _emit_error(self, message: str) -> None:
        log.error(message)
        if self.on_error:
            self.on_error(message)

    def get_recording_duration(self) -> float:
        """Get current recording duration in seconds."""
        with self._lock:
            total_samples = sum(len(c) for c in self._mic_chunks)
        return total_samples / SAMPLE_RATE if total_samples > 0 else 0.0
