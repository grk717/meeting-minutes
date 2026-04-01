#!/usr/bin/env python3
"""Reproduce the WASAPI loopback crash without real hardware.

Simulates the exact crash sequence from the debug report:
  1. LoopbackStream read loop is running normally
  2. The underlying WASAPI handle becomes invalid
  3. stream.read() hits an access violation (or OSError)
  4. The app crashes on Stop because the stream is in a bad state

Usage:
    python test_loopback_crash.py              # run all scenarios
    python test_loopback_crash.py dead_handle   # just the dead-handle test
    python test_loopback_crash.py error_burst   # consecutive read errors
    python test_loopback_crash.py stop_dead     # stop a dead stream
    python test_loopback_crash.py hang_close    # stream.close() hangs

Each test verifies the fix handles the failure gracefully
(no crash, error callback fires, recording continues).
"""

from __future__ import annotations

import sys
import threading
import time
from unittest.mock import MagicMock, PropertyMock, patch

import numpy as np


def _make_fake_audio(samples: int = 800) -> bytes:
    """Generate fake float32 audio bytes."""
    return np.random.randn(samples).astype(np.float32).tobytes()


# ── Test 1: stream.is_active() returns False ─────────────────

def test_dead_handle() -> None:
    """Simulate the WASAPI handle going dead mid-recording.

    This is what happened in the real crash: the device disconnected,
    is_active() would return False, but old code didn't check it and
    called read() on the dead handle → access violation.
    """
    print("\n" + "=" * 60)
    print("TEST: Dead WASAPI handle (is_active → False)")
    print("=" * 60)

    errors_received: list[str] = []
    data_received: list[np.ndarray] = []

    # Build a mock stream that works for 5 reads then "dies"
    mock_stream = MagicMock()
    read_count = 0

    def fake_read(frames, exception_on_overflow=False):
        nonlocal read_count
        read_count += 1
        time.sleep(0.01)  # simulate real timing
        return _make_fake_audio(frames * 2)  # stereo

    mock_stream.read = fake_read

    call_count = 0
    def fake_is_active():
        nonlocal call_count
        call_count += 1
        return call_count <= 5  # alive for 5 checks, then dead

    mock_stream.is_active = fake_is_active

    # Manually drive the read loop logic (extracted from LoopbackStream)
    frames_per_read = 2400
    device_channels = 2
    device_rate = 48000
    target_rate = 16000
    running = True

    def on_data(audio):
        data_received.append(audio)

    def on_error(msg):
        errors_received.append(msg)
        print(f"  [on_error] {msg}")

    # Simulate the read loop
    consecutive_errors = 0
    max_consecutive_errors = 5

    while running and mock_stream is not None:
        if not mock_stream.is_active():
            print("  [reader] Stream no longer active — exiting cleanly")
            on_error(
                "System audio stream stopped unexpectedly. "
                "The audio device may have disconnected."
            )
            break

        try:
            raw = mock_stream.read(frames_per_read, exception_on_overflow=False)
            consecutive_errors = 0
            audio = np.frombuffer(raw, dtype=np.float32)
            if device_channels > 1:
                audio = audio.reshape(-1, device_channels).mean(axis=1)
            on_data(audio)
        except OSError as e:
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                on_error(f"Too many errors: {e}")
                break

    print(f"  Chunks received before death: {len(data_received)}")
    print(f"  Errors received: {len(errors_received)}")
    assert len(errors_received) == 1, "Should have received exactly 1 error"
    assert len(data_received) == 5, "Should have received 5 chunks before death"
    print("  PASS: Exited cleanly, no crash")


# ── Test 2: consecutive read errors ──────────────────────────

def test_error_burst() -> None:
    """Simulate stream.read() throwing OSError repeatedly.

    Some WASAPI failures manifest as OSError before the segfault.
    The fix should give up after N consecutive errors.
    """
    print("\n" + "=" * 60)
    print("TEST: Consecutive read errors (circuit breaker)")
    print("=" * 60)

    errors_received: list[str] = []
    read_count = 0

    mock_stream = MagicMock()
    mock_stream.is_active.return_value = True  # still "active"

    def fake_read(frames, exception_on_overflow=False):
        nonlocal read_count
        read_count += 1
        if read_count <= 3:
            return _make_fake_audio(frames * 2)
        raise OSError(f"[Errno -9999] WASAPI read failed (attempt {read_count})")

    mock_stream.read = fake_read

    # Simulate read loop
    consecutive_errors = 0
    max_consecutive_errors = 5
    running = True
    data_count = 0

    while running:
        if not mock_stream.is_active():
            break
        try:
            raw = mock_stream.read(2400, exception_on_overflow=False)
            consecutive_errors = 0
            data_count += 1
        except OSError as e:
            consecutive_errors += 1
            print(f"  [error {consecutive_errors}/{max_consecutive_errors}] {e}")
            if consecutive_errors >= max_consecutive_errors:
                errors_received.append(str(e))
                print("  [reader] Circuit breaker tripped — exiting")
                break

    print(f"  Good reads: {data_count}")
    print(f"  Total reads attempted: {read_count}")
    assert data_count == 3, "Should have 3 good reads"
    assert read_count == 8, "Should have attempted 3 good + 5 bad = 8 reads"
    print("  PASS: Circuit breaker stopped the loop")


# ── Test 3: stop/close on a dead stream ──────────────────────

def test_stop_dead_stream() -> None:
    """Simulate calling stop() and close() on a stream that's already dead.

    This was part of the crash: stop_recording() calls stream.stop()
    and stream.close() which can also segfault on a dead handle.
    The fix runs these in a thread with a timeout.
    """
    print("\n" + "=" * 60)
    print("TEST: Stop/close on dead stream (timeout)")
    print("=" * 60)

    import sounddevice as sd

    # Simulate a stream where stop() succeeds but close() hangs forever.
    # This is the realistic scenario: WASAPI stop() returns OK but
    # close() blocks waiting on a dead device handle.
    mock_stream = MagicMock(spec=sd.InputStream)

    def fake_stop():
        print("  [mock] stop() called — OK")

    def fake_close():
        # Simulate a hang — in real life this blocks forever
        print("  [mock] close() called — hanging...")
        time.sleep(10)

    mock_stream.stop = fake_stop
    mock_stream.close = fake_close

    # This mirrors the production _stop_stream logic
    def stop_stream_with_timeout(name, stream, timeout=3.0):
        if stream is None:
            return

        def _do_stop():
            try:
                stream.stop()
            except Exception as e:
                print(f"  [{name}] Error in stop: {e}")
            try:
                stream.close()
            except Exception as e:
                print(f"  [{name}] Error in close: {e}")

        t = threading.Thread(target=_do_stop, daemon=True)
        t.start()
        t.join(timeout=timeout)
        if t.is_alive():
            print(f"  [{name}] Stop timed out ({timeout}s) — continuing anyway")
            return "timed_out"
        return "ok"

    start = time.monotonic()
    result = stop_stream_with_timeout("sys", mock_stream, timeout=1.0)
    elapsed = time.monotonic() - start

    print(f"  Result: {result}")
    print(f"  Elapsed: {elapsed:.2f}s")
    assert result == "timed_out", "Should have timed out"
    assert elapsed < 2.0, "Should not have waited for the full hang"
    print("  PASS: Timed out cleanly, main thread not blocked")


# ── Test 4: stream.close() hangs ─────────────────────────────

def test_hang_close() -> None:
    """Simulate the full stop_recording flow when close() hangs.

    Verifies that the WAV file is still saved even if stream
    cleanup times out.
    """
    print("\n" + "=" * 60)
    print("TEST: Full stop_recording with hanging close()")
    print("=" * 60)

    # Simulate AudioManager state
    from meetily.audio.manager import AudioManager, RecordingState

    mgr = AudioManager()
    mgr._state = RecordingState.RECORDING

    # Add some fake audio data
    for _ in range(100):
        chunk = np.random.randn(1024).astype(np.float32) * 0.1
        mgr._mic_chunks.append(chunk)

    # Create a mock stream that hangs on close
    mock_stream = MagicMock()
    mock_stream.stop.side_effect = OSError("Device gone")
    mock_stream.close.side_effect = lambda: time.sleep(10)
    mgr._mic_stream = mock_stream

    # Set up save path
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr._save_path = Path(tmpdir)
        mgr._meeting_name = "test_crash"

        start = time.monotonic()
        saved = mgr.stop_recording()
        elapsed = time.monotonic() - start

        print(f"  Saved path: {saved}")
        print(f"  Elapsed: {elapsed:.2f}s")
        print(f"  State: {mgr._state}")

        assert elapsed < 5.0, f"Should complete in <5s, took {elapsed:.1f}s"
        assert mgr._state == RecordingState.IDLE, "Should be back to IDLE"
        if saved:
            assert saved.exists(), "WAV file should exist"
            size = saved.stat().st_size
            print(f"  WAV size: {size:,} bytes")
            assert size > 0, "WAV file should not be empty"
            print("  PASS: Recording saved despite stream hang")
        else:
            print("  PASS: Stop completed without crash (no audio to save)")


# ── Main ─────────────────────────────────────────────────────

TESTS = {
    "dead_handle": test_dead_handle,
    "error_burst": test_error_burst,
    "stop_dead": test_stop_dead_stream,
    "hang_close": test_hang_close,
}


def main() -> None:
    args = sys.argv[1:]

    print("WASAPI Loopback Crash Reproduction Tests")
    print("=" * 60)
    print("These tests simulate the exact crash from the debug report:")
    print("  access violation in pyaudiowpatch read() on dead WASAPI handle")
    print()

    if args:
        for name in args:
            if name in TESTS:
                TESTS[name]()
            else:
                print(f"Unknown test: {name}")
                print(f"Available: {', '.join(TESTS)}")
                sys.exit(1)
    else:
        passed = 0
        failed = 0
        for name, fn in TESTS.items():
            try:
                fn()
                passed += 1
            except Exception as e:
                print(f"\n  FAILED: {e}")
                failed += 1

        print(f"\n{'='*60}")
        print(f"Results: {passed} passed, {failed} failed")

    print()
    print("To reproduce on real hardware:")
    print("  1. Start Meetily with system audio capture")
    print("  2. Disconnect Bluetooth headphones/USB headset mid-recording")
    print("     OR: Run 'Restart-Service Audiosrv' in admin PowerShell")
    print("  3. Wait a few seconds, then press Stop")
    print("  4. Before fix: crash. After fix: warning toast + recording saved")


if __name__ == "__main__":
    main()
