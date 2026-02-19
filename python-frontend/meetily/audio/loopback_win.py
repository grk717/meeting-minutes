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
        """Polling loop that reads from the loopback stream."""
        frames_per_read = int(self._device_rate * 0.05)  # 50ms chunks

        while self._running and self._stream is not None:
            try:
                # Read raw bytes from stream
                raw = self._stream.read(frames_per_read, exception_on_overflow=False)

                # Convert bytes to float32 numpy
                audio = np.frombuffer(raw, dtype=np.float32)

                if len(audio) == 0:
                    continue

                # Downmix to mono if multi-channel
                if self._device_channels > 1:
                    try:
                        audio = audio.reshape(-1, self._device_channels).mean(axis=1)
                    except ValueError:
                        # If reshape fails, just take every Nth sample
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
                # very quiet signals (0.01-0.1 range). Normalize to use
                # more of the dynamic range while preventing clipping.
                peak = np.max(np.abs(audio))
                if peak > 1e-6:  # Not silence
                    # Target peak of ~0.8 to leave headroom
                    # Use a capped gain to avoid amplifying noise
                    gain = min(0.8 / peak, 10.0)
                    if gain > 1.5:
                        audio = audio * gain

                if self.on_data is not None:
                    self.on_data(audio)

            except OSError as e:
                if self._running:
                    log.warning("Loopback read error: %s", e)
            except Exception as e:
                if self._running:
                    log.error("Loopback read error: %s", e)
                break

    def stop(self) -> None:
        """Stop capturing."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._stream is not None:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception as e:
                log.warning("Error stopping loopback stream: %s", e)
            self._stream = None

    def close(self) -> None:
        """Release resources."""
        self.stop()
        if self._pa is not None:
            self._pa.terminate()
            self._pa = None
