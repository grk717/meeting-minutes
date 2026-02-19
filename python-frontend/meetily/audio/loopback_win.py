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


class LoopbackStream:
    """Captures audio from a Windows output device via WASAPI loopback.

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

        # Resolve device
        if device_index is not None:
            self._device_info = self._pa.get_device_info_by_index(device_index)
        else:
            dev = get_default_output_device()
            if dev is None:
                raise RuntimeError("No output device found for loopback")
            self._device_info = self._pa.get_device_info_by_index(dev.index)

        self._device_rate = int(self._device_info["defaultSampleRate"])
        self._device_channels = self._device_info["maxOutputChannels"]

        # Callback for captured audio (mono float32 at target_rate)
        self.on_data: Callable[[np.ndarray], None] | None = None

        log.info(
            "LoopbackStream configured: '%s' (%dHz, %dch → %dHz mono)",
            self._device_info["name"],
            self._device_rate,
            self._device_channels,
            self._target_rate,
        )

    def start(self) -> None:
        """Start capturing loopback audio."""
        if self._running:
            return

        self._stream = self._pa.open(
            format=_pyaudio.paFloat32,
            channels=self._device_channels,
            rate=self._device_rate,
            input=True,
            input_device_index=self._device_info["index"],
            frames_per_buffer=1024,
            stream_callback=self._callback,
            as_loopback=True,  # The key flag — WASAPI loopback mode
        )
        self._stream.start_stream()
        self._running = True
        log.info("Loopback stream started")

    def stop(self) -> None:
        """Stop capturing."""
        self._running = False
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

    def _callback(self, in_data, frame_count, time_info, status) -> tuple:
        if not self._running or self.on_data is None:
            return (None, _pyaudio.paContinue)

        # Convert bytes to float32 numpy array
        audio = np.frombuffer(in_data, dtype=np.float32)

        # Downmix to mono if multi-channel
        if self._device_channels > 1:
            audio = audio.reshape(-1, self._device_channels).mean(axis=1)

        # Resample if needed (simple linear interpolation)
        if self._device_rate != self._target_rate:
            ratio = self._target_rate / self._device_rate
            new_len = int(len(audio) * ratio)
            indices = np.linspace(0, len(audio) - 1, new_len)
            audio = np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)

        self.on_data(audio)
        return (None, _pyaudio.paContinue)
