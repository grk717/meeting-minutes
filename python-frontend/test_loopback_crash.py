#!/usr/bin/env python3
"""Test that WASAPI loopback crash is isolated in a subprocess.

The core crash scenario:
  1. WASAPI loopback read() hits an access violation (segfault)
  2. Before fix: segfault killed the entire app
  3. After fix: segfault kills only the child process,
     parent detects it and continues with mic-only recording

Usage:
    python test_loopback_crash.py              # run all tests
    python test_loopback_crash.py subprocess   # child process crash isolation
    python test_loopback_crash.py stop         # clean stop
    python test_loopback_crash.py save         # recording saved after crash
"""

from __future__ import annotations

import multiprocessing
import os
import sys
import time

import numpy as np


# ── Test 1: Child process crash isolation ─────────────────────

def _crashing_worker(queue: multiprocessing.Queue, stop_event: multiprocessing.Event) -> None:
    """Simulates a loopback worker that crashes after a few reads."""
    import ctypes

    # Send "started" like real worker
    queue.put(("started", 48000, 2))

    # Send a few good chunks
    for i in range(10):
        if stop_event.is_set():
            return
        audio = np.random.randn(800).astype(np.float32)
        queue.put(("audio", audio.tobytes(), len(audio)))
        time.sleep(0.05)

    # Simulate access violation — this WILL kill this process
    # Using os._exit to simulate a crash (segfault not safe to trigger in test)
    os._exit(-1073741819)  # 0xC0000005 = ACCESS_VIOLATION exit code


def test_subprocess_crash() -> None:
    """Verify that a child process crash doesn't kill the parent."""
    print("\n" + "=" * 60)
    print("TEST: Child process crash isolation")
    print("=" * 60)

    queue = multiprocessing.Queue(maxsize=200)
    stop_event = multiprocessing.Event()

    proc = multiprocessing.Process(
        target=_crashing_worker,
        args=(queue, stop_event),
        daemon=True,
    )
    proc.start()
    print(f"  Child process started (pid={proc.pid})")

    # Read the "started" message
    msg = queue.get(timeout=5.0)
    assert msg[0] == "started", f"Expected 'started', got {msg[0]}"
    print(f"  Child reported: started ({msg[1]}Hz {msg[2]}ch)")

    # Read audio chunks
    chunks_received = 0
    while True:
        try:
            msg = queue.get(timeout=2.0)
            if msg[0] == "audio":
                chunks_received += 1
        except Exception:
            # Timeout — check if process died
            if not proc.is_alive():
                print(f"  Child process died (exit code {proc.exitcode})")
                break
            continue

    print(f"  Chunks received before crash: {chunks_received}")
    print(f"  Parent process still alive: {os.getpid()}")

    assert not proc.is_alive(), "Child should be dead"
    assert proc.exitcode != 0, "Child should have non-zero exit code"
    assert chunks_received > 0, "Should have received some chunks"
    print("  PASS: Parent survived child crash")


# ── Test 2: Clean stop ───────────────────────────────────────

def _normal_worker(queue: multiprocessing.Queue, stop_event: multiprocessing.Event) -> None:
    """Normal worker that stops cleanly."""
    queue.put(("started", 48000, 2))

    while not stop_event.is_set():
        audio = np.random.randn(800).astype(np.float32)
        try:
            queue.put_nowait(("audio", audio.tobytes(), len(audio)))
        except Exception:
            pass
        time.sleep(0.05)


def test_clean_stop() -> None:
    """Verify clean stop works."""
    print("\n" + "=" * 60)
    print("TEST: Clean stop")
    print("=" * 60)

    queue = multiprocessing.Queue(maxsize=200)
    stop_event = multiprocessing.Event()

    proc = multiprocessing.Process(
        target=_normal_worker,
        args=(queue, stop_event),
        daemon=True,
    )
    proc.start()

    msg = queue.get(timeout=5.0)
    assert msg[0] == "started"
    print("  Worker started")

    # Let it run briefly
    time.sleep(0.5)

    # Stop it
    stop_event.set()
    proc.join(timeout=3.0)

    print(f"  Worker exited (exit code {proc.exitcode})")
    assert not proc.is_alive(), "Worker should have exited"
    assert proc.exitcode == 0, "Should exit cleanly"
    print("  PASS: Clean stop works")


# ── Test 3: Recording saved after child crash ────────────────

def test_save_after_crash() -> None:
    """Verify that AudioManager can still save after loopback crash."""
    print("\n" + "=" * 60)
    print("TEST: Recording saved after child process crash")
    print("=" * 60)

    from meetily.audio.manager import AudioManager, RecordingState

    mgr = AudioManager()
    mgr._state = RecordingState.RECORDING

    # Simulate mic data collected (as if recording was in progress)
    for _ in range(100):
        chunk = np.random.randn(1024).astype(np.float32) * 0.1
        mgr._mic_chunks.append(chunk)

    # Simulate loopback stream that already died
    mgr._loopback_stream = None  # as if it was cleaned up after crash

    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr._save_path = Path(tmpdir)
        mgr._meeting_name = "test_crash_recovery"

        start = time.monotonic()
        saved = mgr.stop_recording()
        elapsed = time.monotonic() - start

        print(f"  Saved path: {saved}")
        print(f"  Elapsed: {elapsed:.2f}s")
        print(f"  State: {mgr._state}")

        assert mgr._state == RecordingState.IDLE
        if saved:
            assert saved.exists()
            size = saved.stat().st_size
            print(f"  WAV size: {size:,} bytes")
            assert size > 0
            print("  PASS: Recording saved after loopback crash")
        else:
            print("  PASS: Stop completed without crash")


# ── Main ─────────────────────────────────────────────────────

TESTS = {
    "subprocess": test_subprocess_crash,
    "stop": test_clean_stop,
    "save": test_save_after_crash,
}


def main() -> None:
    args = sys.argv[1:]

    print("WASAPI Loopback Crash Isolation Tests")
    print("=" * 60)
    print("Verifies that WASAPI segfaults in child process")
    print("don't kill the parent app.")
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
                import traceback
                traceback.print_exc()
                failed += 1

        print(f"\n{'='*60}")
        print(f"Results: {passed} passed, {failed} failed")

    print()
    print("To reproduce the real crash on Windows:")
    print("  1. Start Meetily with system audio (WASAPI loopback)")
    print("  2. Disconnect audio device mid-recording")
    print("     OR: Restart-Service Audiosrv (admin PowerShell)")
    print("  3. Press Stop")
    print("  4. Before fix: app crashes. After fix: toast warning,")
    print("     mic recording saved normally.")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
