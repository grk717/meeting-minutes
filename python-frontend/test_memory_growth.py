#!/usr/bin/env python3
"""Stress tests for diagnosing long-meeting crashes.

Simulates audio buffer accumulation, Qt widget growth, and
level-callback flooding WITHOUT requiring a real microphone
or a 30-minute recording session.

Usage:
    python test_memory_growth.py                # run all tests
    python test_memory_growth.py chunks         # audio buffer growth only
    python test_memory_growth.py concat         # concatenation peak memory
    python test_memory_growth.py widgets        # Qt widget accumulation
    python test_memory_growth.py levels         # level callback throughput
    python test_memory_growth.py monitor        # DebugMonitor integration
"""

from __future__ import annotations

import sys
import time
import tracemalloc

import numpy as np

SAMPLE_RATE = 16_000
BLOCK_SIZE = 1024
BYTES_PER_SAMPLE = 4  # float32


def _mb(n_bytes: int) -> float:
    return n_bytes / 1e6


def _estimate_mb(n_samples: int) -> float:
    return _mb(n_samples * BYTES_PER_SAMPLE)


# ── Test 1: Audio chunk accumulation ─────────────────────────

def test_chunk_accumulation(minutes: int = 30) -> None:
    """Simulate appending audio chunks for N minutes.

    This is the primary suspect for OOM crashes: mic_chunks and
    sys_chunks grow unboundedly during recording.
    """
    print(f"\n{'='*60}")
    print(f"TEST: Audio chunk accumulation ({minutes} min)")
    print(f"{'='*60}")

    tracemalloc.start()
    mic_chunks: list[np.ndarray] = []
    sys_chunks: list[np.ndarray] = []

    total_blocks = (minutes * 60 * SAMPLE_RATE) // BLOCK_SIZE
    print(f"  Blocks to simulate: {total_blocks:,}")
    print(f"  Expected memory: ~{_estimate_mb(minutes * 60 * SAMPLE_RATE) * 2:.0f}MB (mic + sys)")
    print()

    milestones = [5, 10, 15, 20, 25, 30, 45, 60]
    next_milestone_idx = 0

    for i in range(total_blocks):
        chunk = np.random.randn(BLOCK_SIZE).astype(np.float32)
        mic_chunks.append(chunk.copy())
        sys_chunks.append(chunk.copy())

        elapsed_min = (i * BLOCK_SIZE) / SAMPLE_RATE / 60

        if next_milestone_idx < len(milestones) and elapsed_min >= milestones[next_milestone_idx]:
            current, peak = tracemalloc.get_traced_memory()
            mic_samples = sum(len(c) for c in mic_chunks)
            sys_samples = sum(len(c) for c in sys_chunks)
            print(
                f"  {milestones[next_milestone_idx]:3d}min | "
                f"mem={_mb(current):6.1f}MB peak={_mb(peak):6.1f}MB | "
                f"mic_chunks={len(mic_chunks):,} sys_chunks={len(sys_chunks):,} | "
                f"mic={_estimate_mb(mic_samples):.1f}MB sys={_estimate_mb(sys_samples):.1f}MB"
            )
            next_milestone_idx += 1

    current, peak = tracemalloc.get_traced_memory()
    print(f"\n  FINAL: mem={_mb(current):.1f}MB, peak={_mb(peak):.1f}MB")

    if _mb(peak) > 300:
        print(f"  *** WARNING: Peak memory {_mb(peak):.0f}MB exceeds 300MB threshold ***")
    else:
        print(f"  OK: Peak memory within bounds")

    tracemalloc.stop()


# ── Test 2: Concatenation peak memory ────────────────────────

def test_concat_peak(minutes: int = 30) -> None:
    """Simulate the _save_audio() concatenation step.

    At stop time, np.concatenate creates a second copy of all
    audio data. This test measures the peak memory during that
    operation.
    """
    print(f"\n{'='*60}")
    print(f"TEST: Concatenation peak memory ({minutes} min)")
    print(f"{'='*60}")

    tracemalloc.start()
    total_samples = minutes * 60 * SAMPLE_RATE
    total_blocks = total_samples // BLOCK_SIZE

    # Accumulate chunks
    mic_chunks = [
        np.random.randn(BLOCK_SIZE).astype(np.float32)
        for _ in range(total_blocks)
    ]
    sys_chunks = [
        np.random.randn(BLOCK_SIZE).astype(np.float32)
        for _ in range(total_blocks)
    ]

    pre_concat, _ = tracemalloc.get_traced_memory()
    print(f"  Pre-concat memory: {_mb(pre_concat):.1f}MB")

    # This is what _save_audio() does
    mic_audio = np.concatenate(mic_chunks)
    sys_audio = np.concatenate(sys_chunks)

    post_concat, peak = tracemalloc.get_traced_memory()
    print(f"  Post-concat memory: {_mb(post_concat):.1f}MB")
    print(f"  Peak memory: {_mb(peak):.1f}MB")
    print(f"  Concat overhead: {_mb(post_concat - pre_concat):.1f}MB")

    # Simulate mixing (another allocation)
    max_len = max(len(mic_audio), len(sys_audio))
    mixed = mic_audio[:max_len] * 0.5 + sys_audio[:max_len] * 0.5

    post_mix, peak = tracemalloc.get_traced_memory()
    print(f"  Post-mix memory: {_mb(post_mix):.1f}MB")
    print(f"  Overall peak: {_mb(peak):.1f}MB")

    if _mb(peak) > 500:
        print(f"  *** WARNING: Peak {_mb(peak):.0f}MB — likely OOM on 4GB systems ***")
    else:
        print(f"  OK: Peak memory within bounds")

    tracemalloc.stop()


# ── Test 3: Qt widget accumulation ───────────────────────────

def test_widget_accumulation(n_segments: int = 500) -> None:
    """Simulate adding many transcript segments to TranscriptPanel.

    Each segment creates multiple QWidgets. This test checks if
    the Qt app becomes unresponsive with many segments.
    """
    print(f"\n{'='*60}")
    print(f"TEST: Qt widget accumulation ({n_segments} segments)")
    print(f"{'='*60}")

    try:
        from PySide6.QtWidgets import QApplication
        from meetily.ui.transcript_panel import TranscriptPanel
    except ImportError:
        print("  SKIPPED: PySide6 not available in this environment")
        return

    app = QApplication.instance() or QApplication(sys.argv)
    panel = TranscriptPanel()

    start = time.monotonic()
    for i in range(n_segments):
        ts = f"{i // 60:02d}:{i % 60:02d}"
        panel.add_segment(f"This is test segment number {i} with some text content.", ts)
        if (i + 1) % 100 == 0:
            elapsed = time.monotonic() - start
            print(f"  {i+1:4d} segments | elapsed={elapsed:.2f}s")

    total = time.monotonic() - start
    print(f"\n  Total: {n_segments} segments in {total:.2f}s")
    print(f"  Avg: {total/n_segments*1000:.1f}ms per segment")
    if total > 5.0:
        print(f"  *** WARNING: UI will lag — consider virtualizing the list ***")
    else:
        print(f"  OK: Widget creation is fast enough")

    panel.deleteLater()


# ── Test 4: Level callback throughput ────────────────────────

def test_level_callback_throughput(seconds: int = 10) -> None:
    """Measure how many level updates would be generated vs throttled.

    Without throttling, each audio block triggers a level update.
    With ~30fps throttling, most updates are dropped.
    """
    print(f"\n{'='*60}")
    print(f"TEST: Level callback throughput ({seconds}s)")
    print(f"{'='*60}")

    blocks_per_second = SAMPLE_RATE / BLOCK_SIZE
    total_blocks = int(blocks_per_second * seconds)
    target_fps = 30

    unthrottled = total_blocks
    throttled = seconds * target_fps

    print(f"  Blocks/sec: {blocks_per_second:.1f}")
    print(f"  Unthrottled updates: {unthrottled:,} ({unthrottled/seconds:.0f}/sec)")
    print(f"  Throttled updates (~{target_fps}fps): {throttled:,} ({target_fps}/sec)")
    print(f"  Reduction: {(1 - throttled/unthrottled)*100:.1f}%")
    print()

    # Simulate throttled vs unthrottled
    LEVEL_UPDATE_INTERVAL = 1.0 / target_fps
    emitted = 0
    dropped = 0
    last_emit = 0.0

    for i in range(total_blocks):
        now = i / blocks_per_second  # simulated time
        if (now - last_emit) >= LEVEL_UPDATE_INTERVAL:
            last_emit = now
            emitted += 1
        else:
            dropped += 1

    print(f"  Simulation result: emitted={emitted:,}, dropped={dropped:,}")
    print(f"  Over 30min unthrottled: {int(blocks_per_second * 30 * 60):,} Qt events queued")
    print(f"  Over 30min throttled: {30 * 60 * target_fps:,} Qt events queued")


# ── Test 5: DebugMonitor integration ─────────────────────────

def test_debug_monitor() -> None:
    """Verify the DebugMonitor tracks metrics and produces a report."""
    print(f"\n{'='*60}")
    print("TEST: DebugMonitor integration")
    print(f"{'='*60}")

    try:
        from meetily.debug import DebugMonitor
    except ImportError:
        print("  SKIPPED: meetily.debug not importable")
        return

    mon = DebugMonitor.instance()
    mon.start()

    # Simulate 60 seconds of recording at high speed
    for sec in range(60):
        chunks = (sec + 1) * (SAMPLE_RATE // BLOCK_SIZE)
        samples = chunks * BLOCK_SIZE
        mon.track_chunks("mic", chunks, samples)
        mon.track_chunks("sys", chunks // 2, samples // 2)
        mon.track_transcript_count(sec // 5)

    snap = mon.snapshot("test_complete")
    print(f"  Last snapshot: {snap.summary_line()}")

    report_path = mon.dump_report()
    print(f"  Report saved: {report_path}")

    mon.stop()
    print(f"  Status: {mon.get_status_text()}")
    print("  OK: Monitor collected and reported data")


# ── Main ─────────────────────────────────────────────────────

TESTS = {
    "chunks": test_chunk_accumulation,
    "concat": test_concat_peak,
    "widgets": test_widget_accumulation,
    "levels": test_level_callback_throughput,
    "monitor": test_debug_monitor,
}


def main() -> None:
    args = sys.argv[1:]

    if args:
        for name in args:
            if name in TESTS:
                TESTS[name]()
            else:
                print(f"Unknown test: {name}")
                print(f"Available: {', '.join(TESTS)}")
                sys.exit(1)
    else:
        print("Meetily Long-Meeting Crash Diagnostics")
        print("=" * 60)
        for name, fn in TESTS.items():
            try:
                fn()
            except Exception as e:
                print(f"\n  FAILED: {e}")

    print(f"\n{'='*60}")
    print("All tests complete.")


if __name__ == "__main__":
    main()
