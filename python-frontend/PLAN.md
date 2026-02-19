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
    │   ├── manager.py                 # Core audio engine (~600 lines)
    │   └── loopback_win.py            # Windows WASAPI loopback capture (~300 lines)
    ├── transcription/
    │   ├── __init__.py                # Exports TranscriptionManager
    │   ├── vad.py                     # Voice Activity Detection (~130 lines)
    │   ├── client.py                  # HTTP ASR client (~70 lines)
    │   └── manager.py                 # VAD→queue→worker orchestration (~110 lines)
    ├── summarization/
    │   ├── __init__.py                # Exports SummarizationClient
    │   └── client.py                  # HTTP LLM client (~75 lines)
    ├── ui/
    │   ├── __init__.py                # Exports MainWindow
    │   ├── main_window.py             # Main window with all controls (~360 lines)
    │   ├── level_bars.py              # Animated 3-bar audio visualizer (~150 lines)
    │   ├── device_panel.py            # Mic + system audio device selectors (~210 lines)
    │   ├── transcript_panel.py        # Live transcript display (~95 lines)
    │   ├── summary_panel.py           # LLM summary display (~65 lines)
    │   ├── settings_dialog.py         # ASR + LLM endpoint settings (~105 lines)
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

### Phase 3: Cloud Transcription — DONE

**What's implemented:**

#### `meetily/transcription/vad.py` — VadProcessor
- Voice Activity Detection using `webrtcvad` (aggressiveness=2)
- Processes float32 16kHz mono audio → splits into 30ms frames → classifies speech/silence
- State machine: speech start (3 consecutive frames ~90ms), speech end (15 silence frames ~450ms)
- Bridges natural pauses in speech, rejects segments <0.5s
- Force-flushes long segments at 30s to bound latency
- `process_chunk(audio)` → returns completed speech segments as numpy arrays
- `flush()` → returns any remaining speech at recording end

#### `meetily/transcription/client.py` — TranscriptionClient
- HTTP client for OpenAI-compatible ASR endpoint (`POST /v1/audio/transcriptions`)
- Converts numpy float32 → WAV bytes in memory via `soundfile` + `io.BytesIO`
- Sends multipart form: file=audio.wav, model=whisper-1, response_format=json
- Supports optional Bearer token API key
- 30s timeout, returns transcribed text string

#### `meetily/transcription/manager.py` — TranscriptionManager
- Orchestrates VAD → thread-safe queue → HTTP worker → callbacks
- `feed_audio(audio)` — called from audio capture thread, runs VAD, enqueues segments
- Worker daemon thread consumes queue, transcribes each segment, fires callbacks
- `on_transcript(text, timestamp)` callback for UI (called from worker thread)
- `on_error(message)` callback for error reporting
- `start()` / `stop()` lifecycle, `update_settings()` for runtime config changes

#### `meetily/ui/transcript_panel.py` — TranscriptPanel
- Scrollable `QGroupBox` displaying timestamped transcript segments
- `add_segment(text, timestamp)` — appends `[MM:SS] text` label, auto-scrolls
- `clear()` — resets for new recording with placeholder text
- `get_full_transcript()` — returns all segments as plain text
- Text-selectable labels for easy copy

#### `meetily/ui/settings_dialog.py` — SettingsDialog
- `QDialog` for configuring ASR endpoint URL and optional API key
- Persisted via `QSettings` (cross-platform: Registry on Windows, plist on macOS)
- Default endpoint: `http://localhost:8178`
- `get_settings()` static method for loading saved config

#### Integration in `main_window.py`
- Settings button in header opens `SettingsDialog`
- On recording start: creates `TranscriptionManager`, wires `AudioManager.on_audio_chunk` → `feed_audio`
- Transcript segments arrive via Qt signal bridge (worker thread → main thread)
- On recording stop: flushes remaining speech, stops worker
- Transcript panel sits below Recording group

### Phase 4: Summarization + Transcript Saving — DONE

**What's implemented:**

#### Transcript Log Saving
- On recording stop, transcript saved as `.txt` next to the `.wav` file
- Format: `Meeting: {name}\nDate: {datetime}\n\n[00:05] segment text...`
- Same filename as WAV but with `.txt` extension

#### `meetily/summarization/client.py` — SummarizationClient
- HTTP client for OpenAI-compatible chat completions (`POST /v1/chat/completions`)
- System prompt structures output as: Key Topics, Decisions Made, Action Items
- 60s timeout for long transcripts
- Supports configurable model name and optional API key

#### `meetily/ui/summary_panel.py` — SummaryPanel
- `QGroupBox` with scrollable `QLabel` displaying summary text
- `set_loading()` — shows "Generating summary..." during LLM call
- `set_summary(text)` — displays the result
- Text-selectable for copy

#### `meetily/ui/settings_dialog.py` — Updated
- Added LLM section: Endpoint URL, API Key, Model name
- Defaults: `http://localhost:11434`, model `gpt-4o-mini`
- All settings persisted via `QSettings`

#### Integration in `main_window.py`
- On recording stop:
  1. Saves transcript `.txt` next to WAV
  2. Starts summarization in background thread
  3. Summary panel shows loading → result
  4. Summary saved as `{name}_summary.txt` next to WAV
- Summary panel sits below Transcript panel
- `_summary_signal` bridges worker thread → main thread

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
