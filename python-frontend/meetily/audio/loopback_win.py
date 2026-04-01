"""Windows WASAPI loopback capture using PyAudioWPatch.

Standard PortAudio (sounddevice) cannot capture system audio on Windows.
PyAudioWPatch is a fork of PyAudio that exposes WASAPI loopback mode,
which captures whatever is playing through an output device (speakers).

CRASH PREVENTION: WASAPI loopback handles can become invalid when audio
devices disconnect (Bluetooth off, USB unplug, display sleep, audio
service restart). Calling read()/close() on a dead handle triggers a
C-level access violation (segfault) that kills the ENTIRE process —
threads cannot isolate this.

The fix: all PyAudioWPatch I/O runs in a **child process** via
multiprocessing. If the child segfaults, the parent detects the exit
and continues safely with microphone-only recording.

This module provides:
- list_output_devices(): discover speakers/headphones to capture from
- LoopbackStream: a capture stream that records from an output device
"""

from __future__ import annotations

import logging
import multiprocessing
import platform
import threading
import time
from dataclasses import dataclass
from typing import Callable

import numpy as np

log = logging.getLogger(__name__)

# Only import on Windows
_pyaudio = None
if platform.system() == "Windows":
    try:
        import pyaudiowpatch as _pyaudio

        log.info("PyAudioWPatch loaded — WASAPI loopback available")
    except ImportError:
        log.warning(
            "PyAudioWPatch not installed. System audio capture unavailable. "
            "Install with: pip install PyAudioWPatch"
        )


@dataclass
class OutputDevice:
    """An output (speaker/headphone) device that can be loopback-captured."""

    index: int
    name: str
    channels: int
    default_samplerate: int
    is_default: bool

    def __str__(self) -> str:
        suffix = " (Default)" if self.is_default else ""
        return f"{self.name}{suffix}"


def is_available() -> bool:
    """Check if WASAPI loopback is available on this platform."""
    return _pyaudio is not None


def list_output_devices() -> list[OutputDevice]:
    """List output devices available for loopback capture."""
    if _pyaudio is None:
        return []

    devices: list[OutputDevice] = []
    pa = _pyaudio.PyAudio()

    try:
        # Find the WASAPI host API
        wasapi_idx = None
        for i in range(pa.get_host_api_count()):
            api_info = pa.get_host_api_info_by_index(i)
            if "wasapi" in api_info["name"].lower():
                wasapi_idx = i
                break

        if wasapi_idx is None:
            log.warning("WASAPI host API not found")
            return []

        wasapi_info = pa.get_host_api_info_by_index(wasapi_idx)
        default_output_idx = wasapi_info.get("defaultOutputDevice", -1)

        # Enumerate WASAPI devices, pick output ones
        for i in range(wasapi_info["deviceCount"]):
            dev_info = pa.get_device_info_by_host_api_device_index(wasapi_idx, i)
            if dev_info["maxOutputChannels"] > 0:
                devices.append(
                    OutputDevice(
                        index=dev_info["index"],
                        name=dev_info["name"],
                        channels=dev_info["maxOutputChannels"],
                        default_samplerate=int(dev_info["defaultSampleRate"]),
                        is_default=(dev_info["index"] == default_output_idx),
                    )
                )
    finally:
        pa.terminate()

    return devices


def get_default_output_device() -> OutputDevice | None:
    """Get the default output device (speakers) for loopback capture."""
    devices = list_output_devices()
    # Prefer the default device
    for dev in devices:
        if dev.is_default:
            return dev
    # Fallback to first available
    return devices[0] if devices else None


def _find_loopback_device(pa, output_device_index: int) -> dict | None:
    """Find the corresponding loopback input device for an output device.

    PyAudioWPatch exposes loopback devices as special input devices
    whose name contains '[Loopback]'. This function finds the loopback
    counterpart of a given output device.
    """
    output_info = pa.get_device_info_by_index(output_device_index)
    output_name = output_info["name"]

    # Search for a loopback device matching this output
    for i in range(pa.get_device_count()):
        try:
            dev_info = pa.get_device_info_by_index(i)
            if dev_info["maxInputChannels"] > 0 and "[Loopback]" in dev_info["name"]:
                # Check if the loopback name contains the output device name
                # PyAudioWPatch names loopback devices like "Speakers [Loopback]"
                base_name = dev_info["name"].replace(" [Loopback]", "")
                if base_name == output_name or output_name.startswith(base_name):
                    return dev_info
        except Exception:
            continue

    return None


# ── Child process function ──────────────────────────────────

def _loopback_worker(
    device_index: int | None,
    target_rate: int,
    audio_queue: multiprocessing.Queue,
    stop_event: multiprocessing.Event,
) -> None:
    """Runs in a child process. All PyAudioWPatch I/O happens here.

    If the WASAPI handle dies and read() segfaults, only THIS process
    dies — the parent continues safely.

    Sends audio chunks as (numpy bytes, shape, dtype) tuples through
    the queue. Sends None as a sentinel when stopping.
    """
    import pyaudiowpatch as pa_mod

    pa = pa_mod.PyAudio()
    stream = None

    try:
        # Resolve device
        if device_index is not None:
            output_info = pa.get_device_info_by_index(device_index)
        else:
            # Find default output
            for i in range(pa.get_host_api_count()):
                api_info = pa.get_host_api_info_by_index(i)
                if "wasapi" in api_info["name"].lower():
                    wasapi_info = pa.get_host_api_info_by_index(i)
                    default_idx = wasapi_info.get("defaultOutputDevice", -1)
                    if default_idx >= 0:
                        output_info = pa.get_device_info_by_index(default_idx)
                        break
            else:
                audio_queue.put(("error", "No WASAPI output device found"))
                return

        # Find loopback device
        loopback_info = _find_loopback_device(pa, output_info["index"])

        if loopback_info is not None:
            capture_info = loopback_info
            use_as_loopback = False
        else:
            capture_info = output_info
            use_as_loopback = True

        device_rate = int(capture_info["defaultSampleRate"])
        device_channels = max(
            capture_info.get("maxInputChannels", 0),
            capture_info.get("maxOutputChannels", 0),
        )
        if device_channels == 0:
            device_channels = 2

        frames_per_buffer = int(device_rate * 0.05)  # 50ms

        open_kwargs = dict(
            format=pa_mod.paFloat32,
            channels=device_channels,
            rate=device_rate,
            input=True,
            input_device_index=capture_info["index"],
            frames_per_buffer=frames_per_buffer,
        )
        if use_as_loopback:
            open_kwargs["as_loopback"] = True

        stream = pa.open(**open_kwargs)

        # Signal successful start
        audio_queue.put(("started", device_rate, device_channels))

        frames_per_read = frames_per_buffer
        consecutive_errors = 0

        while not stop_event.is_set():
            try:
                raw = stream.read(frames_per_read, exception_on_overflow=False)
                consecutive_errors = 0

                audio = np.frombuffer(raw, dtype=np.float32)
                if len(audio) == 0:
                    continue

                # Downmix to mono
                if device_channels > 1:
                    try:
                        audio = audio.reshape(-1, device_channels).mean(axis=1)
                    except ValueError:
                        audio = audio[::device_channels]

                # Resample to target rate
                if device_rate != target_rate:
                    ratio = target_rate / device_rate
                    new_len = max(1, int(len(audio) * ratio))
                    indices = np.linspace(0, len(audio) - 1, new_len)
                    audio = np.interp(indices, np.arange(len(audio)), audio).astype(
                        np.float32
                    )

                # Boost quiet loopback audio
                peak = np.max(np.abs(audio))
                if peak > 1e-6:
                    gain = min(0.8 / peak, 10.0)
                    if gain > 1.5:
                        audio = audio * gain

                # Send via queue — use tobytes() for pickling efficiency
                try:
                    audio_queue.put_nowait(("audio", audio.tobytes(), len(audio)))
                except Exception:
                    pass  # queue full, drop frame

            except OSError:
                consecutive_errors += 1
                if consecutive_errors >= 5:
                    audio_queue.put(("error", "Too many WASAPI read errors"))
                    break

    except Exception as e:
        try:
            audio_queue.put(("error", str(e)))
        except Exception:
            pass
    finally:
        if stream is not None:
            try:
                stream.stop_stream()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass
        try:
            pa.terminate()
        except Exception:
            pass


class LoopbackStream:
    """Captures audio from a Windows output device via WASAPI loopback.

    All WASAPI I/O runs in a child process to isolate access violations.
    If the child crashes (device disconnected), the parent continues
    safely with microphone-only recording.

    Usage:
        stream = LoopbackStream(device_index=5, target_rate=16000)
        stream.on_data = lambda audio_f32: process(audio_f32)
        stream.start()
        ...
        stream.close()
    """

    def __init__(
        self,
        device_index: int | None = None,
        target_rate: int = 16000,
    ) -> None:
        if _pyaudio is None:
            raise RuntimeError("PyAudioWPatch not available")

        self._device_index = device_index
        self._target_rate = target_rate
        self._process: multiprocessing.Process | None = None
        self._audio_queue: multiprocessing.Queue | None = None
        self._stop_event: multiprocessing.Event | None = None
        self._reader_thread: threading.Thread | None = None
        self._running = False

        # Callback for captured audio (mono float32 at target_rate)
        self.on_data: Callable[[np.ndarray], None] | None = None
        # Callback for errors (string message)
        self.on_error: Callable[[str], None] | None = None

    def start(self) -> None:
        """Start the loopback capture subprocess."""
        if self._running:
            return

        self._audio_queue = multiprocessing.Queue(maxsize=200)
        self._stop_event = multiprocessing.Event()

        self._process = multiprocessing.Process(
            target=_loopback_worker,
            args=(
                self._device_index,
                self._target_rate,
                self._audio_queue,
                self._stop_event,
            ),
            daemon=True,
            name="loopback-worker",
        )
        self._process.start()
        log.info("Loopback worker process started (pid=%d)", self._process.pid)

        # Wait for the "started" message or an error
        try:
            msg = self._audio_queue.get(timeout=5.0)
            if msg[0] == "error":
                raise RuntimeError(f"Loopback worker failed: {msg[1]}")
            if msg[0] == "started":
                log.info(
                    "Loopback capture active: %dHz %dch -> %dHz mono",
                    msg[1], msg[2], self._target_rate,
                )
        except Exception as e:
            self._cleanup()
            raise RuntimeError(f"Loopback worker did not start: {e}") from e

        self._running = True

        # Start a thread that reads from the queue and calls on_data
        self._reader_thread = threading.Thread(
            target=self._queue_reader,
            daemon=True,
            name="loopback-queue-reader",
        )
        self._reader_thread.start()

    def _queue_reader(self) -> None:
        """Reads audio chunks from the child process queue and calls on_data."""
        while self._running:
            try:
                msg = self._audio_queue.get(timeout=1.0)
            except Exception:
                # Timeout — check if process is still alive
                if self._process is not None and not self._process.is_alive():
                    exit_code = self._process.exitcode
                    if self._running:
                        log.error(
                            "Loopback worker process died (exit code %s) — "
                            "audio device may have disconnected",
                            exit_code,
                        )
                        self._notify_error(
                            "System audio capture stopped unexpectedly. "
                            "The audio device may have disconnected. "
                            "Microphone recording continues."
                        )
                    self._running = False
                    break
                continue

            if msg[0] == "audio":
                audio = np.frombuffer(msg[1], dtype=np.float32).copy()
                if self.on_data is not None:
                    self.on_data(audio)

            elif msg[0] == "error":
                log.warning("Loopback worker error: %s", msg[1])
                self._notify_error(f"System audio error: {msg[1]}")
                self._running = False
                break

        log.info("Loopback queue reader exited")

    def stop(self) -> None:
        """Stop the loopback capture. Non-blocking — cleanup runs in background."""
        if not self._running and self._process is None:
            return

        self._running = False

        # Signal the child process to stop
        if self._stop_event is not None:
            self._stop_event.set()

        # Reader thread checks self._running every 1s, so it will exit soon.
        # Don't join it here — let _cleanup_async handle everything off-thread.

        # Run all cleanup in a background thread so the caller (main thread)
        # doesn't freeze waiting for process joins / queue drains.
        cleanup_thread = threading.Thread(
            target=self._cleanup_blocking,
            daemon=True,
            name="loopback-cleanup",
        )
        cleanup_thread.start()

    def _cleanup_blocking(self) -> None:
        """Cleanup that may block. Runs in a background thread."""
        # Wait for reader thread to exit
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=3.0)
            self._reader_thread = None

        # Kill child process
        if self._process is not None:
            self._process.join(timeout=1.0)
            if self._process.is_alive():
                log.info("Loopback worker still alive — terminating")
                try:
                    self._process.kill()
                except Exception:
                    pass
                self._process.join(timeout=1.0)
            exit_code = self._process.exitcode if self._process else None
            log.info("Loopback worker ended (exit code %s)", exit_code)
            self._process = None

        # Drain and close queue — do this AFTER process is dead
        if self._audio_queue is not None:
            try:
                # Brief drain — don't loop forever
                for _ in range(100):
                    if self._audio_queue.empty():
                        break
                    self._audio_queue.get_nowait()
            except Exception:
                pass
            try:
                self._audio_queue.close()
                self._audio_queue.join_thread()
            except Exception:
                pass
            self._audio_queue = None

        self._stop_event = None
        log.info("Loopback cleanup complete")

    def close(self) -> None:
        """Release resources."""
        self.stop()

    def _notify_error(self, message: str) -> None:
        """Safely invoke the on_error callback."""
        if self.on_error is not None:
            try:
                self.on_error(message)
            except Exception:
                pass
