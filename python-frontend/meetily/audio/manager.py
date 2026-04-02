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

from meetily.audio import loopback_win

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000  # 16 kHz — standard for speech
CHANNELS = 1  # Mono for speech
BLOCK_SIZE = 1024  # ~64ms at 16kHz
LEVEL_SMOOTHING = 0.3  # EMA smoothing for level meter
LEVEL_UPDATE_INTERVAL = 1.0 / 30  # Throttle level callbacks to ~30fps
CHUNK_LOG_INTERVAL = 5000  # Log chunk stats every N chunks
STREAM_WATCHDOG_INTERVAL = 5.0  # Check stream health every N seconds
# How long with zero callbacks before we consider a stream dead.
# WASAPI loopback sends data continuously even during silence (~50ms intervals),
# so 30s of no callbacks means the device is truly gone, not just a quiet room.
STREAM_DEAD_THRESHOLD = 30.0


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
            "vb-audio",
            "cable output",
            "voicemeeter",
        ]
        return any(hint in name_lower for hint in loopback_hints)

    @property
    def loopback_priority(self) -> int:
        """Higher = better candidate for system audio capture.

        On Windows, WASAPI loopback devices are the best option.
        On macOS, BlackHole is the standard virtual audio device.
        """
        name_lower = self.name.lower()
        hostapi_lower = self.hostapi_name.lower()

        # Windows WASAPI loopback — best option, works natively
        if "wasapi" in hostapi_lower and "loopback" in name_lower:
            return 100

        # macOS: BlackHole is the standard
        if "blackhole" in name_lower:
            return 90

        # Soundflower (legacy macOS)
        if "soundflower" in name_lower:
            return 80

        # VB-Audio / VoiceMeeter (cross-platform)
        if "cable output" in name_lower or "voicemeeter" in name_lower:
            return 70

        # Generic virtual/loopback
        if "loopback" in name_lower:
            return 60
        if "virtual" in name_lower:
            return 50
        if "stereo mix" in name_lower:
            return 40

        return 0

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
        self._loopback_stream: loopback_win.LoopbackStream | None = None
        self._mic_device: int | None = None
        self._sys_device: int | None = None
        self._save_path: Path | None = None
        self._meeting_name: str = ""

        # Audio buffers (protected by lock)
        self._lock = threading.Lock()
        self._mic_chunks: list[np.ndarray] = []
        self._sys_chunks: list[np.ndarray] = []

        # Stream start timestamps for time-alignment during mixing.
        # Set to monotonic time when each stream delivers its first chunk.
        self._mic_first_chunk_time: float | None = None
        self._sys_first_chunk_time: float | None = None

        # Duration snapshot — set just before chunks are consumed in stop_recording
        self._last_duration_secs: float = 0.0

        # Level metering (smoothed)
        self._levels = AudioLevels()
        self._last_level_emit: float = 0.0

        # Stream health tracking
        self._mic_last_data: float = 0.0
        self._sys_last_data: float = 0.0
        self._watchdog_thread: threading.Thread | None = None
        self._watchdog_running = False
        self._mic_dead_warned = False
        self._sys_dead_warned = False

        # Callbacks
        self.on_levels_updated: Callable[[AudioLevels], None] | None = None
        self.on_state_changed: Callable[[RecordingState], None] | None = None
        self.on_error: Callable[[str], None] | None = None
        self.on_warning: Callable[[str], None] | None = None
        self.on_audio_chunk: Callable[[np.ndarray], None] | None = None

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

    @staticmethod
    def auto_detect_system_device() -> tuple[AudioDevice | loopback_win.OutputDevice | None, bool]:
        """Auto-detect the best system audio capture device.

        Returns:
            (device, use_loopback) tuple.
            - On Windows: (OutputDevice, True) — uses WASAPI loopback on speakers.
            - On macOS: (AudioDevice, False) — uses BlackHole/Soundflower input.
            - On Linux: (AudioDevice, False) — uses PulseAudio monitor input.
            - If nothing found: (None, False).
        """
        system = platform.system()

        # Windows: use PyAudioWPatch WASAPI loopback (captures from speakers directly)
        if system == "Windows" and loopback_win.is_available():
            dev = loopback_win.get_default_output_device()
            if dev is not None:
                log.info("Auto-detected Windows loopback device: '%s'", dev.name)
                return dev, True
            # Fallback: list all output devices
            outputs = loopback_win.list_output_devices()
            if outputs:
                log.info("Auto-detected Windows loopback device (fallback): '%s'", outputs[0].name)
                return outputs[0], True

        # macOS / Linux: look for virtual input devices
        all_devices = AudioManager.list_devices()
        candidates: list[AudioDevice] = []

        if system == "Darwin":
            for dev in all_devices:
                if dev.is_input and dev.loopback_priority > 0:
                    candidates.append(dev)
        else:
            # Linux: PulseAudio/PipeWire monitor sources
            for dev in all_devices:
                if not dev.is_input:
                    continue
                name_lower = dev.name.lower()
                if "monitor" in name_lower or dev.loopback_priority > 0:
                    candidates.append(dev)

        if not candidates:
            log.info("No system audio capture device found automatically")
            return None, False

        candidates.sort(key=lambda d: d.loopback_priority, reverse=True)
        best = candidates[0]
        log.info(
            "Auto-detected system audio device: '%s' (priority=%d, hostapi=%s)",
            best.name,
            best.loopback_priority,
            best.hostapi_name,
        )
        return best, False

    @staticmethod
    def get_system_audio_help() -> str:
        """Return platform-specific help text for system audio setup."""
        system = platform.system()
        if system == "Darwin":
            return (
                "macOS requires a virtual audio device to capture system audio.\n\n"
                "Install BlackHole (free, open source):\n"
                "  brew install blackhole-2ch\n\n"
                "Then set BlackHole as your system output in System Settings > Sound, "
                "or create a Multi-Output Device in Audio MIDI Setup to hear audio "
                "while capturing it."
            )
        elif system == "Windows":
            if loopback_win.is_available():
                return (
                    "System audio capture uses WASAPI loopback.\n"
                    "Your default speakers will be captured automatically."
                )
            return (
                "Install PyAudioWPatch for system audio capture:\n"
                "  pip install PyAudioWPatch\n\n"
                "This captures audio directly from your speakers — "
                "no virtual audio driver needed."
            )
        else:
            return (
                "Linux: PulseAudio/PipeWire monitor sources should be auto-detected.\n\n"
                "If not listed, check that your audio server exposes monitor sources:\n"
                "  pactl list sources | grep monitor"
            )

    # ── Recording control ───────────────────────────────────────

    def start_recording(
        self,
        mic_device: int | None = None,
        system_device: int | None = None,
        use_loopback: bool = False,
        meeting_name: str = "",
        save_dir: Path | None = None,
    ) -> None:
        """Start capturing audio from microphone and optionally system audio.

        Args:
            mic_device: sounddevice input device index for microphone.
            system_device: Device index for system audio capture.
                On Windows with use_loopback=True, this is a PyAudioWPatch
                output device index (speakers). Otherwise it's a sounddevice
                input device index (loopback/virtual device).
            use_loopback: If True and on Windows, use WASAPI loopback mode
                to capture from an output device. This is the recommended
                approach on Windows — no virtual audio driver needed.
            meeting_name: Optional name for the meeting recording.
            save_dir: Directory to save the WAV file.
        """
        if self._state != RecordingState.IDLE:
            log.warning("Cannot start recording: state is %s", self._state)
            return

        self._mic_device = mic_device
        self._sys_device = system_device
        self._meeting_name = meeting_name or f"meeting_{int(time.time())}"

        # Prepare save directory
        if save_dir is None:
            save_dir = Path.home() / "Documents" / "ZennoCall"
        save_dir.mkdir(parents=True, exist_ok=True)
        self._save_path = save_dir

        # Clear previous buffers and timing state
        with self._lock:
            self._mic_chunks.clear()
            self._sys_chunks.clear()
        self._mic_first_chunk_time = None
        self._sys_first_chunk_time = None
        self._last_duration_secs = 0.0

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
                self._set_state(RecordingState.IDLE)
                return

        # Start system audio stream
        if system_device is not None:
            if use_loopback and loopback_win.is_available():
                # Windows WASAPI loopback: capture from output device
                try:
                    self._loopback_stream = loopback_win.LoopbackStream(
                        device_index=system_device,
                        target_rate=SAMPLE_RATE,
                    )
                    self._loopback_stream.on_data = self._loopback_data_callback
                    self._loopback_stream.on_error = self._on_loopback_error
                    self._loopback_stream.start()
                    log.info("WASAPI loopback stream started on output device %d", system_device)
                except Exception as e:
                    log.warning("Failed to start WASAPI loopback: %s (continuing with mic only)", e)
                    self._loopback_stream = None
                    self._emit_warning("System audio unavailable — recording microphone only")
            else:
                # Standard sounddevice input (virtual device / macOS BlackHole / Linux monitor)
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
                    self._emit_warning("System audio unavailable — recording microphone only")

        self._start_watchdog()
        self._set_state(RecordingState.RECORDING)

    def stop_recording(self) -> Path | None:
        """Stop recording and save audio to WAV file. Returns the saved file path."""
        if self._state not in (RecordingState.RECORDING, RecordingState.PAUSED):
            log.warning("Cannot stop recording: state is %s", self._state)
            return None

        self._set_state(RecordingState.STOPPING)

        # Stop watchdog first
        self._stop_watchdog()

        # Snapshot duration before chunks are consumed by _save_audio()
        self._last_duration_secs = self.get_recording_duration()

        # Stop streams with timeout to handle dead/hung streams
        self._stop_stream("mic", self._mic_stream)
        self._mic_stream = None

        self._stop_stream("sys", self._sys_stream)
        self._sys_stream = None

        if self._loopback_stream is not None:
            try:
                # stop() is non-blocking — cleanup runs in background thread
                self._loopback_stream.stop()
            except Exception as e:
                log.warning("Error stopping loopback stream: %s", e)
            self._loopback_stream = None

        # Save audio
        saved_path = self._save_audio()

        # Reset levels
        self._levels = AudioLevels()
        if self.on_levels_updated:
            self.on_levels_updated(self._levels)

        self._set_state(RecordingState.IDLE)
        return saved_path

    def _stop_stream(self, name: str, stream: sd.InputStream | None) -> None:
        """Stop and close an audio stream with timeout protection.

        Dead WASAPI streams can hang on stop()/close(). Run in a thread
        with a timeout to prevent the main thread from freezing.
        """
        if stream is None:
            return

        def _do_stop() -> None:
            try:
                stream.stop()
            except Exception as e:
                log.warning("Error stopping %s stream: %s", name, e)
            try:
                stream.close()
            except Exception as e:
                log.warning("Error closing %s stream: %s", name, e)

        t = threading.Thread(target=_do_stop, daemon=True)
        t.start()
        t.join(timeout=3.0)
        if t.is_alive():
            log.warning(
                "%s stream stop timed out (3s) — stream may be dead, continuing",
                name,
            )

    def pause_recording(self) -> None:
        """Pause the current recording."""
        if self._state != RecordingState.RECORDING:
            return
        if self._mic_stream:
            self._mic_stream.stop()
        if self._sys_stream:
            self._sys_stream.stop()
        # Loopback subprocess: don't stop/start — the _loopback_data_callback
        # already ignores data when state != RECORDING
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

        now = time.monotonic()
        self._mic_last_data = now
        if self._mic_first_chunk_time is None:
            self._mic_first_chunk_time = now
        audio = indata[:, 0].copy()

        with self._lock:
            self._mic_chunks.append(audio)
            chunk_count = len(self._mic_chunks)
            total_samples = sum(len(c) for c in self._mic_chunks)

        if self.on_audio_chunk:
            self.on_audio_chunk(audio)

        # Periodic debug logging
        if chunk_count % CHUNK_LOG_INTERVAL == 0:
            mb_est = (total_samples * 4) / 1e6  # float32 = 4 bytes
            duration = total_samples / SAMPLE_RATE
            log.info(
                "Mic buffer: %d chunks, %.1fs, ~%.1fMB",
                chunk_count, duration, mb_est,
            )

        # Debug monitor integration
        try:
            from meetily.debug import DebugMonitor
            mon = DebugMonitor.instance()
            if mon.is_running:
                mon.track_chunks("mic", chunk_count, total_samples)
        except Exception:
            pass

        # Update levels (fast path, no lock needed for atomic float writes)
        rms = float(np.sqrt(np.mean(audio**2)))
        peak = float(np.max(np.abs(audio)))
        self._levels.mic_rms = self._levels.mic_rms * LEVEL_SMOOTHING + rms * (1 - LEVEL_SMOOTHING)
        self._levels.mic_peak = max(peak, self._levels.mic_peak * 0.95)

        # Throttle level updates to ~30fps to avoid flooding Qt event queue
        now = time.monotonic()
        if self.on_levels_updated and (now - self._last_level_emit) >= LEVEL_UPDATE_INTERVAL:
            self._last_level_emit = now
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

        now = time.monotonic()
        self._sys_last_data = now
        if self._sys_first_chunk_time is None:
            self._sys_first_chunk_time = now

        audio = indata[:, 0].copy()

        with self._lock:
            self._sys_chunks.append(audio)
            chunk_count = len(self._sys_chunks)
            total_samples = sum(len(c) for c in self._sys_chunks)

        if self.on_audio_chunk:
            self.on_audio_chunk(audio)

        # Periodic debug logging
        if chunk_count % CHUNK_LOG_INTERVAL == 0:
            mb_est = (total_samples * 4) / 1e6
            duration = total_samples / SAMPLE_RATE
            log.info(
                "Sys buffer: %d chunks, %.1fs, ~%.1fMB",
                chunk_count, duration, mb_est,
            )

        # Debug monitor integration
        try:
            from meetily.debug import DebugMonitor
            mon = DebugMonitor.instance()
            if mon.is_running:
                mon.track_chunks("sys", chunk_count, total_samples)
        except Exception:
            pass

        rms = float(np.sqrt(np.mean(audio**2)))
        peak = float(np.max(np.abs(audio)))
        self._levels.system_rms = self._levels.system_rms * LEVEL_SMOOTHING + rms * (1 - LEVEL_SMOOTHING)
        self._levels.system_peak = max(peak, self._levels.system_peak * 0.95)

        # Throttle level updates (same as mic callback)
        now = time.monotonic()
        if self.on_levels_updated and (now - self._last_level_emit) >= LEVEL_UPDATE_INTERVAL:
            self._last_level_emit = now
            self.on_levels_updated(self._levels)

    def _loopback_data_callback(self, audio: np.ndarray) -> None:
        """Called by LoopbackStream with mono float32 audio at target rate."""
        if self._state != RecordingState.RECORDING:
            return

        now = time.monotonic()
        self._sys_last_data = now
        if self._sys_first_chunk_time is None:
            self._sys_first_chunk_time = now
        audio_copy = audio.copy()

        with self._lock:
            self._sys_chunks.append(audio_copy)
            chunk_count = len(self._sys_chunks)
            total_samples = sum(len(c) for c in self._sys_chunks)

        if self.on_audio_chunk:
            self.on_audio_chunk(audio_copy)

        # Debug monitor integration
        try:
            from meetily.debug import DebugMonitor
            mon = DebugMonitor.instance()
            if mon.is_running:
                mon.track_chunks("sys", chunk_count, total_samples)
        except Exception:
            pass

        rms = float(np.sqrt(np.mean(audio**2)))
        peak = float(np.max(np.abs(audio)))
        self._levels.system_rms = self._levels.system_rms * LEVEL_SMOOTHING + rms * (1 - LEVEL_SMOOTHING)
        self._levels.system_peak = max(peak, self._levels.system_peak * 0.95)

        # Throttle level updates
        now = time.monotonic()
        if self.on_levels_updated and (now - self._last_level_emit) >= LEVEL_UPDATE_INTERVAL:
            self._last_level_emit = now
            self.on_levels_updated(self._levels)

    def _on_loopback_error(self, message: str) -> None:
        """Called from the loopback reader thread when the stream fails."""
        log.warning("Loopback stream error: %s", message)
        self._emit_warning(message)

    # ── Stream health watchdog ─────────────────────────────────

    def _start_watchdog(self) -> None:
        """Start a background thread that monitors stream health."""
        self._watchdog_running = True
        self._mic_dead_warned = False
        self._sys_dead_warned = False
        now = time.monotonic()
        self._mic_last_data = now
        self._sys_last_data = now
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop, daemon=True, name="stream-watchdog"
        )
        self._watchdog_thread.start()

    def _stop_watchdog(self) -> None:
        self._watchdog_running = False
        if self._watchdog_thread is not None:
            self._watchdog_thread.join(timeout=STREAM_WATCHDOG_INTERVAL + 1)
            self._watchdog_thread = None

    def _watchdog_loop(self) -> None:
        """Periodically check that audio streams are still delivering data."""
        while self._watchdog_running:
            time.sleep(STREAM_WATCHDOG_INTERVAL)
            if not self._watchdog_running or self._state != RecordingState.RECORDING:
                continue

            now = time.monotonic()

            # Check mic stream
            if self._mic_stream is not None and not self._mic_dead_warned:
                gap = now - self._mic_last_data
                if gap > STREAM_DEAD_THRESHOLD:
                    self._mic_dead_warned = True
                    log.warning(
                        "Mic stream appears dead — no data for %.0fs", gap
                    )
                    self._emit_warning(
                        "Microphone stream stopped receiving data. "
                        "The device may have disconnected."
                    )

            # Check system audio stream.
            # WASAPI loopback sends data continuously (~50ms intervals)
            # even during silence, so if callbacks stop for 30s the
            # device is truly gone. We only warn here — the actual crash
            # prevention is in LoopbackStream._guarded_read() which
            # isolates every read() in a daemon thread with a timeout.
            sys_active = (self._sys_stream is not None or self._loopback_stream is not None)
            if sys_active and not self._sys_dead_warned:
                gap = now - self._sys_last_data
                if gap > STREAM_DEAD_THRESHOLD:
                    self._sys_dead_warned = True
                    log.warning(
                        "System audio stream appears dead — no data for %.0fs",
                        gap,
                    )
                    self._emit_warning(
                        "System audio may have disconnected. "
                        "Microphone recording continues."
                    )

    # ── Audio saving ────────────────────────────────────────────

    def _save_audio(self) -> Path | None:
        """Mix and save captured audio to WAV file.

        Moves chunks out of the accumulation lists and frees them
        incrementally to avoid doubling peak memory during concat.
        """
        # Move chunks out of the lists (swap-and-clear to minimise lock time)
        with self._lock:
            mic_chunks = self._mic_chunks
            sys_chunks = self._sys_chunks
            self._mic_chunks = []
            self._sys_chunks = []

        if not mic_chunks and not sys_chunks:
            log.warning("No audio data captured")
            return None

        log.info(
            "Saving audio: mic_chunks=%d, sys_chunks=%d",
            len(mic_chunks), len(sys_chunks),
        )

        # Concatenate chunks — pre-allocate to avoid intermediate copies
        mic_audio = self._concat_and_free(mic_chunks)
        sys_audio = self._concat_and_free(sys_chunks)

        # Mix: if both streams, combine them (simple average mix)
        if len(mic_audio) > 0 and len(sys_audio) > 0:
            # Time-align streams: the stream that started later gets silence
            # prepended so that both streams are synchronized in the mix.
            mic_t0 = self._mic_first_chunk_time
            sys_t0 = self._sys_first_chunk_time
            if mic_t0 is not None and sys_t0 is not None:
                offset_secs = mic_t0 - sys_t0  # positive = mic started later
                offset_samples = int(abs(offset_secs) * SAMPLE_RATE)
                if offset_samples > 0:
                    silence = np.zeros(offset_samples, dtype=np.float32)
                    if offset_secs > 0:
                        # Mic started later — prepend silence to mic
                        mic_audio = np.concatenate([silence, mic_audio])
                        log.info("Time-align: mic started %.3fs after system, prepended %d samples", offset_secs, offset_samples)
                    else:
                        # System started later — prepend silence to system
                        sys_audio = np.concatenate([silence, sys_audio])
                        log.info("Time-align: system started %.3fs after mic, prepended %d samples", -offset_secs, offset_samples)

            # Align lengths (pad shorter with zeros at the end)
            max_len = max(len(mic_audio), len(sys_audio))
            if len(mic_audio) < max_len:
                mic_audio = np.pad(mic_audio, (0, max_len - len(mic_audio)))
            if len(sys_audio) < max_len:
                sys_audio = np.pad(sys_audio, (0, max_len - len(sys_audio)))

            # Mix in-place to avoid yet another allocation
            mic_audio *= 0.5
            mic_audio += sys_audio * 0.5
            del sys_audio  # free immediately

            # Normalize to use full dynamic range
            max_val = float(np.max(np.abs(mic_audio)))
            if max_val > 0.001:
                mic_audio *= 0.9 / max_val
            audio = mic_audio
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

        try:
            sf.write(str(filepath), audio, SAMPLE_RATE)
            log.info("Saved recording: %s (%.1fs)", filepath, duration)
            return filepath
        except Exception as e:
            log.error("Failed to write WAV file %s: %s", filepath, e)
            self._emit_error(f"Failed to save recording: {e}")
            return None

    @staticmethod
    def _concat_and_free(chunks: list[np.ndarray]) -> np.ndarray:
        """Concatenate audio chunks into a single array, freeing as we go.

        Pre-allocates the output buffer, then copies each chunk in and
        deletes the source to keep peak memory ~1x instead of ~2x.
        """
        if not chunks:
            return np.array([], dtype=np.float32)

        total = sum(len(c) for c in chunks)
        out = np.empty(total, dtype=np.float32)
        offset = 0
        while chunks:
            c = chunks.pop(0)
            out[offset:offset + len(c)] = c
            offset += len(c)
        return out

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

    def _emit_warning(self, message: str) -> None:
        log.warning(message)
        if self.on_warning:
            self.on_warning(message)

    def get_recording_duration(self) -> float:
        """Get current recording duration in seconds."""
        with self._lock:
            total_samples = sum(len(c) for c in self._mic_chunks)
        return total_samples / SAMPLE_RATE if total_samples > 0 else 0.0
