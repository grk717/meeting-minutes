"""Windows WASAPI loopback capture using PyAudioWPatch.

Standard PortAudio (sounddevice) cannot capture system audio on Windows.
PyAudioWPatch is a fork of PyAudio that exposes WASAPI loopback mode,
which captures whatever is playing through an output device (speakers).

This module provides:
- list_output_devices(): discover speakers/headphones to capture from
- LoopbackStream: a capture stream that records from an output device
"""

from __future__ import annotations

import logging
import platform
import threading
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


class LoopbackStream:
    """Captures audio from a Windows output device via WASAPI loopback.

    Uses a polling thread instead of a callback to avoid PyAudio callback
    issues with WASAPI loopback mode.

    Usage:
        stream = LoopbackStream(device_index=5, target_rate=16000)
        stream.on_data = lambda audio_f32: process(audio_f32)
        stream.start()
        ...
        stream.stop()
    """

    def __init__(
        self,
        device_index: int | None = None,
        target_rate: int = 16000,
    ) -> None:
        if _pyaudio is None:
            raise RuntimeError("PyAudioWPatch not available")

        self._pa = _pyaudio.PyAudio()
        self._stream = None
        self._running = False
        self._target_rate = target_rate
        self._thread: threading.Thread | None = None

        # Resolve output device
        if device_index is not None:
            self._output_info = self._pa.get_device_info_by_index(device_index)
        else:
            dev = get_default_output_device()
            if dev is None:
                raise RuntimeError("No output device found for loopback")
            self._output_info = self._pa.get_device_info_by_index(dev.index)

        # Try to find the corresponding loopback input device
        self._loopback_info = _find_loopback_device(self._pa, self._output_info["index"])

        if self._loopback_info is not None:
            # Use the dedicated loopback device (preferred)
            self._capture_info = self._loopback_info
            self._use_as_loopback_flag = False
            log.info(
                "Found loopback device: '%s' (%dHz, %dch)",
                self._capture_info["name"],
                int(self._capture_info["defaultSampleRate"]),
                self._capture_info["maxInputChannels"],
            )
        else:
            # Fall back to as_loopback flag on the output device itself
            self._capture_info = self._output_info
            self._use_as_loopback_flag = True
            log.info(
                "No dedicated loopback device found, using as_loopback flag on '%s'",
                self._output_info["name"],
            )

        self._device_rate = int(self._capture_info["defaultSampleRate"])
        self._device_channels = max(
            self._capture_info.get("maxInputChannels", 0),
            self._capture_info.get("maxOutputChannels", 0),
        )
        if self._device_channels == 0:
            self._device_channels = 2  # Fallback to stereo

        # Callback for captured audio (mono float32 at target_rate)
        self.on_data: Callable[[np.ndarray], None] | None = None
        # Callback for errors (string message)
        self.on_error: Callable[[str], None] | None = None

        log.info(
            "LoopbackStream configured: '%s' (%dHz, %dch -> %dHz mono)",
            self._capture_info["name"],
            self._device_rate,
            self._device_channels,
            self._target_rate,
        )

    def start(self) -> None:
        """Start capturing loopback audio via polling thread."""
        if self._running:
            return

        # Calculate frames per buffer (~50ms chunks)
        frames_per_buffer = int(self._device_rate * 0.05)

        open_kwargs = dict(
            format=_pyaudio.paFloat32,
            channels=self._device_channels,
            rate=self._device_rate,
            input=True,
            input_device_index=self._capture_info["index"],
            frames_per_buffer=frames_per_buffer,
        )

        # Only use as_loopback if we don't have a dedicated loopback device
        if self._use_as_loopback_flag:
            open_kwargs["as_loopback"] = True

        self._stream = self._pa.open(**open_kwargs)
        self._running = True

        # Use polling thread — more reliable than callbacks for WASAPI loopback
        self._thread = threading.Thread(
            target=self._read_loop,
            name="loopback-reader",
            daemon=True,
        )
        self._thread.start()
        log.info("Loopback stream started (polling mode, %d frames/buffer)", frames_per_buffer)

    def _read_loop(self) -> None:
        """Polling loop that reads from the loopback stream.

        WASAPI loopback streams can crash with an access violation
        (segfault) when the audio device becomes invalid — for example
        when Bluetooth headphones disconnect, the display sleeps, or
        the Windows audio service restarts.

        The segfault happens inside the C call to pa.read() and CANNOT
        be caught by Python exception handling. is_active() also lies —
        it returns True even after the handle is corrupted.

        The only reliable defense is to run read() in a disposable
        sub-thread with a short timeout. If read() hangs or segfaults,
        only the sub-thread dies — the reader loop detects the timeout
        and exits cleanly.
        """
        frames_per_read = int(self._device_rate * 0.05)  # 50ms chunks
        consecutive_errors = 0
        max_consecutive_errors = 5
        read_timeout = 2.0  # seconds — a 50ms read should never take this long

        while self._running and self._stream is not None:
            try:
                if not self._stream.is_active():
                    if self._running:
                        log.warning("Loopback stream no longer active — stopping reader")
                        self._notify_error(
                            "System audio stream stopped unexpectedly. "
                            "The audio device may have disconnected."
                        )
                    break

                # Run read() in a sub-thread so a segfault or hang
                # kills only the sub-thread, not the whole process.
                raw = self._guarded_read(frames_per_read, read_timeout)
                if raw is None:
                    # read() timed out or the stream was killed
                    if self._running:
                        log.error(
                            "Loopback read timed out (%.1fs) — "
                            "WASAPI handle likely dead, stopping to prevent crash",
                            read_timeout,
                        )
                        self._notify_error(
                            "System audio device stopped responding. "
                            "Microphone recording continues."
                        )
                    break

                consecutive_errors = 0

                # Convert bytes to float32 numpy
                audio = np.frombuffer(raw, dtype=np.float32)

                if len(audio) == 0:
                    continue

                # Downmix to mono if multi-channel
                if self._device_channels > 1:
                    try:
                        audio = audio.reshape(-1, self._device_channels).mean(axis=1)
                    except ValueError:
                        audio = audio[::self._device_channels]

                # Resample to target rate if needed
                if self._device_rate != self._target_rate:
                    ratio = self._target_rate / self._device_rate
                    new_len = max(1, int(len(audio) * ratio))
                    indices = np.linspace(0, len(audio) - 1, new_len)
                    audio = np.interp(indices, np.arange(len(audio)), audio).astype(
                        np.float32
                    )

                # Boost loopback audio — WASAPI loopback often delivers
                # very quiet signals (0.01-0.1 range).
                peak = np.max(np.abs(audio))
                if peak > 1e-6:
                    gain = min(0.8 / peak, 10.0)
                    if gain > 1.5:
                        audio = audio * gain

                if self.on_data is not None:
                    self.on_data(audio)

            except OSError as e:
                if self._running:
                    consecutive_errors += 1
                    log.warning(
                        "Loopback read error (%d/%d): %s",
                        consecutive_errors, max_consecutive_errors, e,
                    )
                    if consecutive_errors >= max_consecutive_errors:
                        log.error(
                            "Too many consecutive loopback read errors — "
                            "stopping capture to prevent crash"
                        )
                        self._notify_error(
                            "System audio capture stopped: too many read errors. "
                            "Microphone recording continues."
                        )
                        break
            except Exception as e:
                if self._running:
                    log.error("Loopback read error: %s", e)
                    self._notify_error(f"System audio error: {e}")
                break

        log.info("Loopback read loop exited")

    def _guarded_read(self, frames: int, timeout: float) -> bytes | None:
        """Run stream.read() in a disposable thread with a timeout.

        If the WASAPI handle is corrupted, read() will either:
          (a) segfault — kills only the sub-thread (daemon), or
          (b) hang forever — we detect via timeout and abandon it.

        Returns the raw bytes on success, or None on timeout/failure.
        """
        # Capture a local reference — stop() may set self._stream = None
        stream = self._stream
        if stream is None:
            return None

        result: list[bytes | None] = [None]

        def _do_read():
            try:
                result[0] = stream.read(frames, exception_on_overflow=False)
            except Exception:
                result[0] = None

        t = threading.Thread(target=_do_read, daemon=True)
        t.start()
        t.join(timeout=timeout)

        if t.is_alive():
            # read() is hung or segfaulted in the sub-thread.
            # The daemon thread will be cleaned up on process exit.
            return None

        return result[0]

    def _notify_error(self, message: str) -> None:
        """Safely invoke the on_error callback."""
        if self.on_error is not None:
            try:
                self.on_error(message)
            except Exception:
                pass

    def stop(self) -> None:
        """Stop capturing.

        Sets _running=False so the read loop exits on its next iteration,
        then waits for the reader thread to finish. Stream teardown
        (stop_stream/close) runs in a daemon thread with a timeout
        because these calls can also hang on a dead WASAPI handle.
        """
        self._running = False

        # Wait for the read loop to notice _running=False and exit.
        # The _guarded_read timeout is 2s, so the loop will check
        # _running within at most ~2s.
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                log.warning("Loopback reader thread did not exit — abandoning")
            self._thread = None

        # Now tear down the stream. The read loop is no longer using it.
        if self._stream is not None:
            stream_ref = self._stream
            self._stream = None

            def _do_close():
                try:
                    stream_ref.stop_stream()
                except Exception as e:
                    log.debug("Error in stop_stream: %s", e)
                try:
                    stream_ref.close()
                except Exception as e:
                    log.debug("Error in close: %s", e)

            closer = threading.Thread(target=_do_close, daemon=True)
            closer.start()
            closer.join(timeout=2.0)
            if closer.is_alive():
                log.warning("Loopback stream close timed out — abandoning handle")

    def close(self) -> None:
        """Release resources."""
        self.stop()
        if self._pa is not None:
            try:
                self._pa.terminate()
            except Exception as e:
                log.debug("Error terminating PyAudio: %s", e)
            self._pa = None
