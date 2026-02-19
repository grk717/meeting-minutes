# Meetily Python Frontend — Implementation Plan

## Overview

Python desktop app (PySide6) that replicates the core functionality of the Meetily Tauri app.
Key difference: **no on-device ML** — all transcription and summarization via cloud APIs.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| UI Framework | PySide6 (Qt 6) — native look on macOS & Windows |
| Audio Capture (mic) | sounddevice (PortAudio) |
| Audio Capture (system, Windows) | PyAudioWPatch (WASAPI loopback) |
| Audio Capture (system, macOS) | sounddevice + BlackHole virtual device |
| ASR API | Deepgram / OpenAI Whisper API / Groq (planned) |
| Summarization API | Claude API / OpenAI / Groq (planned) |
| Storage | SQLite via aiosqlite (planned) |
| Packaging | PyInstaller or Briefcase (planned) |

## Project Structure

```
python-frontend/
├── pyproject.toml                     # Dependencies, entry point
├── .gitignore                         # __pycache__, .pyc, build artifacts
├── PLAN.md                            # This file
└── meetily/
    ├── __init__.py
    ├── main.py                        # Entry point — QApplication, dark theme
    ├── audio/
    │   ├── __init__.py                # Exports AudioManager, AudioDevice, RecordingState
    │   ├── manager.py                 # Core audio engine (~540 lines)
    │   └── loopback_win.py            # Windows WASAPI loopback capture (~300 lines)
    ├── ui/
    │   ├── __init__.py                # Exports MainWindow
    │   ├── main_window.py             # Main window with all controls (~350 lines)
    │   ├── level_bars.py              # Animated 3-bar audio visualizer (~150 lines)
    │   ├── device_panel.py            # Mic + system audio device selectors (~210 lines)
    │   └── theme.py                   # Dark theme QSS stylesheet (~245 lines)
    ├── storage/
    │   └── __init__.py                # Placeholder for Phase 5
    └── utils/
        └── __init__.py                # Placeholder
```

## Implementation Phases

### Phase 1+2: Audio Recording + UI — DONE

**What's implemented:**

#### `meetily/audio/manager.py` — AudioManager
- `AudioDevice` dataclass with device properties, `is_loopback` heuristic, `loopback_priority` scoring
- `AudioManager.list_devices()` / `list_input_devices()` / `list_loopback_devices()` — device enumeration via sounddevice
- `AudioManager.auto_detect_system_device()` — returns `(device, use_loopback)` tuple:
  - Windows: finds default speakers via PyAudioWPatch, returns `(OutputDevice, True)`
  - macOS: finds BlackHole/Soundflower, returns `(AudioDevice, False)`
  - Linux: finds PulseAudio monitor sources, returns `(AudioDevice, False)`
- `AudioManager.get_system_audio_help()` — platform-specific setup instructions
- `start_recording(mic_device, system_device, use_loopback, meeting_name, save_dir)` — starts mic stream (sounddevice) and system stream (sounddevice or WASAPI loopback)
- `stop_recording()` → `Path | None` — stops streams, mixes audio, saves WAV
- `pause_recording()` / `resume_recording()` — pause/resume all streams
- Audio mixing: `mic*0.5 + system*0.5` with normalization to 0.9 peak
- Real-time RMS/peak level metering with EMA smoothing
- Thread-safe callbacks: `on_levels_updated`, `on_state_changed`, `on_error`
- 16kHz mono, 1024 block size, float32

#### `meetily/audio/loopback_win.py` — Windows WASAPI Loopback
- `OutputDevice` dataclass (index, name, channels, samplerate, is_default)
- `list_output_devices()` — enumerates WASAPI output devices (speakers/headphones)
- `get_default_output_device()` — finds default speakers
- `_find_loopback_device()` — finds PyAudioWPatch `[Loopback]` input device for a given output
- `LoopbackStream` class:
  - Polling thread (not callback) — more reliable for WASAPI loopback
  - 50ms read chunks at device native rate
  - Downmix multi-channel to mono
  - Resample to target rate (linear interpolation)
  - Auto-gain boost: normalizes quiet loopback audio (target 0.8 peak, max 10x gain)
  - Two-tier device resolution: dedicated `[Loopback]` device first, `as_loopback=True` fallback

#### `meetily/ui/main_window.py` — MainWindow
- Header ("Meetily" / "AI Meeting Assistant")
- Meeting name input field
- Device selection panel (DevicePanel widget)
- Recording section with level bars, duration timer, status text
- Start/Stop/Pause/Resume buttons with state management
- Thread-safe UI updates via Qt signals (levels, state, errors from audio thread)
- Close confirmation when recording active

#### `meetily/ui/level_bars.py` — LevelBarsWidget
- 3 vertical bars with rounded corners
- Green→Yellow→Red gradient based on level
- Fast attack / slow release smoothing (0.35 up, 0.15 down)
- Idle pulsing animation when not recording
- Amplification: `rms*8`, `peak*5` for visibility

#### `meetily/ui/device_panel.py` — DevicePanel
- Microphone dropdown (filters out loopback devices, selects default)
- "Capture system audio" checkbox toggle
- Auto-detect status with green/red indicator text
- "Manual" checkbox to override with full device list
- On Windows: shows output devices (speakers) for loopback
- On macOS/Linux: shows input devices (virtual/monitor)
- `selected_mic_device`, `selected_system_device`, `use_loopback` properties

#### `meetily/ui/theme.py` — Dark Theme
- Deep navy/indigo color scheme (#1a1a2e base)
- Styled: QGroupBox, QLineEdit, QComboBox, QCheckBox, QPushButton, QMessageBox, QScrollBar
- Blue (#4c6ef5) record button, red (#e03131) stop button
- High-DPI aware

#### `meetily/main.py` — Entry Point
- Sets up logging, creates QApplication, applies dark theme, shows MainWindow

### Phase 3: Cloud Transcription — TODO

- Add Deepgram WebSocket streaming for real-time transcripts during recording
- Fallback: OpenAI Whisper API batch upload after stop
- Add Groq Whisper as alternative
- Display transcript segments in real-time scrollable panel
- API key management (keyring for secure storage)
- New files needed:
  - `meetily/transcription/deepgram_client.py`
  - `meetily/transcription/openai_client.py`
  - `meetily/ui/transcript_panel.py`

### Phase 4: Summarization — TODO

- Post-recording: send transcript to Claude/OpenAI API
- Configurable system prompt / summary template
- Display summary in rich text panel
- New files needed:
  - `meetily/summarization/claude_client.py`
  - `meetily/ui/summary_panel.py`

### Phase 5: Meeting Management — TODO

- SQLite storage (meetings, transcripts, summaries)
- Sidebar with meeting history list + search
- Meeting detail view (transcript + summary)
- Copy/export functionality
- New files needed:
  - `meetily/storage/database.py`
  - `meetily/ui/sidebar.py`
  - `meetily/ui/meeting_detail.py`

### Phase 6: Settings & Polish — TODO

- Settings panel: API keys, provider selection, audio preferences
- Secure API key storage (keyring library)
- Toast notifications
- Error handling and recovery

### Phase 7: Packaging — TODO

- PyInstaller for .app (macOS) and .exe (Windows)
- App icon, code signing
- Auto-updater (optional)

## How to Run

```bash
cd python-frontend
pip install -e .
python -m meetily.main
```

Or without installing:
```bash
pip install PySide6 sounddevice numpy soundfile PyAudioWPatch
python meetily/main.py
```

## Platform Notes

### Windows
- System audio: PyAudioWPatch WASAPI loopback captures from speakers directly — no extra drivers needed
- `PyAudioWPatch` is a Windows-only dependency (conditional in pyproject.toml)

### macOS
- System audio: Requires BlackHole (`brew install blackhole-2ch`) or similar virtual audio device
- No native loopback without ScreenCaptureKit (would need Swift/ObjC interop)

### Linux
- System audio: PulseAudio/PipeWire monitor sources auto-detected
- Check with: `pactl list sources | grep monitor`

## Key Design Decisions

1. **sounddevice for mic, PyAudioWPatch for system (Windows)** — sounddevice/PortAudio cannot do WASAPI loopback
2. **Polling thread for loopback** — PyAudio callbacks are unreliable with WASAPI loopback mode
3. **16kHz mono** — standard for speech recognition APIs, saves bandwidth
4. **Callbacks not Qt signals in AudioManager** — keeps audio module UI-agnostic; MainWindow bridges via Qt signals
5. **Auto-detect with manual override** — users shouldn't need to understand audio devices
6. **Loopback auto-gain** — WASAPI loopback delivers quiet signals; boost up to 10x with 0.8 peak target
