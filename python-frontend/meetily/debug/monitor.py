"""Runtime debug monitor for tracking memory, chunk growth, and Qt event queue health.

Usage:
    from meetily.debug import DebugMonitor

    monitor = DebugMonitor.instance()
    monitor.start()          # begins periodic sampling
    monitor.track_chunks("mic", len(self._mic_chunks))
    monitor.snapshot()       # force a log line now
    monitor.stop()
    monitor.dump_report()    # write full report to file
"""

from __future__ import annotations

import json
import logging
import os
import platform
import sys
import threading
import time
import tracemalloc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

_SAMPLE_INTERVAL = 5.0  # seconds between automatic snapshots


@dataclass
class Snapshot:
    """A single point-in-time measurement."""

    timestamp: float
    elapsed_secs: float
    mem_current_mb: float
    mem_peak_mb: float
    mic_chunks: int
    sys_chunks: int
    mic_samples: int
    sys_samples: int
    transcript_segments: int
    qt_pending_events: int  # -1 if unavailable
    thread_count: int
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "elapsed_s": round(self.elapsed_secs, 1),
            "mem_mb": round(self.mem_current_mb, 1),
            "mem_peak_mb": round(self.mem_peak_mb, 1),
            "mic_chunks": self.mic_chunks,
            "sys_chunks": self.sys_chunks,
            "mic_samples_k": round(self.mic_samples / 1000, 1),
            "sys_samples_k": round(self.sys_samples / 1000, 1),
            "transcripts": self.transcript_segments,
            "threads": self.thread_count,
            "notes": self.notes,
        }

    def summary_line(self) -> str:
        elapsed = time.strftime("%M:%S", time.gmtime(self.elapsed_secs))
        return (
            f"[{elapsed}] mem={self.mem_current_mb:.1f}MB (peak {self.mem_peak_mb:.1f}MB) | "
            f"mic_chunks={self.mic_chunks} sys_chunks={self.sys_chunks} | "
            f"mic_samples={self.mic_samples/1000:.1f}k sys_samples={self.sys_samples/1000:.1f}k | "
            f"transcripts={self.transcript_segments} threads={self.thread_count}"
            + (f" | {self.notes}" if self.notes else "")
        )


class DebugMonitor:
    """Singleton monitor that tracks resource usage over time.

    Designed to be low-overhead: sampling runs in a daemon thread,
    counters are updated via lightweight atomic-ish operations.
    """

    _instance: DebugMonitor | None = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> DebugMonitor:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._started = False
        self._start_time = 0.0
        self._snapshots: list[Snapshot] = []
        self._sample_thread: threading.Thread | None = None
        self._running = False

        # Counters updated externally
        self._mic_chunks = 0
        self._sys_chunks = 0
        self._mic_samples = 0
        self._sys_samples = 0
        self._transcript_segments = 0
        self._level_updates = 0
        self._level_updates_dropped = 0

        # Callbacks for fetching live data
        self._get_qt_pending: Callable[[], int] | None = None

        # Thresholds for warnings
        self.warn_mem_mb = 300.0
        self.warn_chunks = 50_000

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start tracemalloc and periodic sampling."""
        if self._started:
            return
        self._started = True
        self._start_time = time.monotonic()

        if not tracemalloc.is_tracing():
            tracemalloc.start()

        self._running = True
        self._sample_thread = threading.Thread(
            target=self._sample_loop, daemon=True, name="debug-monitor"
        )
        self._sample_thread.start()
        log.info("DebugMonitor started (sampling every %.0fs)", _SAMPLE_INTERVAL)

    def stop(self) -> None:
        """Stop periodic sampling."""
        self._running = False
        if self._sample_thread is not None:
            self._sample_thread.join(timeout=_SAMPLE_INTERVAL + 1)
            self._sample_thread = None
        log.info(
            "DebugMonitor stopped. %d snapshots collected, "
            "level_updates=%d (dropped=%d)",
            len(self._snapshots),
            self._level_updates,
            self._level_updates_dropped,
        )

    # ── External counter updates ───────────────────────────────

    def track_chunks(self, source: str, count: int, samples: int) -> None:
        """Called from audio callbacks to update chunk/sample counts."""
        if source == "mic":
            self._mic_chunks = count
            self._mic_samples = samples
        elif source == "sys":
            self._sys_chunks = count
            self._sys_samples = samples

    def track_transcript_count(self, count: int) -> None:
        self._transcript_segments = count

    def track_level_update(self, dropped: bool = False) -> None:
        self._level_updates += 1
        if dropped:
            self._level_updates_dropped += 1

    # ── Snapshot ────────────────────────────────────────────────

    def snapshot(self, note: str = "") -> Snapshot:
        """Take a snapshot now and log it."""
        current, peak = tracemalloc.get_traced_memory()
        elapsed = time.monotonic() - self._start_time

        qt_pending = -1
        if self._get_qt_pending:
            try:
                qt_pending = self._get_qt_pending()
            except Exception:
                pass

        snap = Snapshot(
            timestamp=time.time(),
            elapsed_secs=elapsed,
            mem_current_mb=current / 1e6,
            mem_peak_mb=peak / 1e6,
            mic_chunks=self._mic_chunks,
            sys_chunks=self._sys_chunks,
            mic_samples=self._mic_samples,
            sys_samples=self._sys_samples,
            transcript_segments=self._transcript_segments,
            qt_pending_events=qt_pending,
            thread_count=threading.active_count(),
            notes=note,
        )
        self._snapshots.append(snap)
        log.info("DBG %s", snap.summary_line())

        # Warn on thresholds
        if snap.mem_current_mb > self.warn_mem_mb:
            log.warning(
                "MEMORY WARNING: %.1fMB exceeds threshold %.1fMB",
                snap.mem_current_mb,
                self.warn_mem_mb,
            )
        total_chunks = snap.mic_chunks + snap.sys_chunks
        if total_chunks > self.warn_chunks:
            log.warning(
                "CHUNK WARNING: %d total chunks exceeds threshold %d",
                total_chunks,
                self.warn_chunks,
            )

        return snap

    # ── Report ─────────────────────────────────────────────────

    def dump_report(self, path: Path | None = None) -> Path:
        """Write a JSON report of all snapshots to disk."""
        if path is None:
            path = Path.home() / "Documents" / "Meetily" / "debug_reports"
        path.mkdir(parents=True, exist_ok=True)

        filename = f"debug_{time.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = path / filename

        report = {
            "system": {
                "platform": platform.platform(),
                "python": sys.version,
                "pid": os.getpid(),
            },
            "summary": {
                "duration_secs": round(time.monotonic() - self._start_time, 1),
                "total_snapshots": len(self._snapshots),
                "level_updates_total": self._level_updates,
                "level_updates_dropped": self._level_updates_dropped,
                "peak_mem_mb": max(
                    (s.mem_peak_mb for s in self._snapshots), default=0
                ),
                "peak_mic_chunks": max(
                    (s.mic_chunks for s in self._snapshots), default=0
                ),
                "peak_sys_chunks": max(
                    (s.sys_chunks for s in self._snapshots), default=0
                ),
            },
            "snapshots": [s.to_dict() for s in self._snapshots],
        }

        filepath.write_text(json.dumps(report, indent=2), encoding="utf-8")
        log.info("Debug report saved: %s", filepath)
        return filepath

    def get_status_text(self) -> str:
        """One-line status for UI display."""
        if not self._snapshots:
            return "Debug monitor: no data yet"
        s = self._snapshots[-1]
        return (
            f"Mem: {s.mem_current_mb:.0f}MB | "
            f"Chunks: {s.mic_chunks + s.sys_chunks} | "
            f"Threads: {s.thread_count}"
        )

    # ── Internal ───────────────────────────────────────────────

    def _sample_loop(self) -> None:
        while self._running:
            try:
                self.snapshot()
            except Exception as e:
                log.debug("DebugMonitor sample error: %s", e)
            # Sleep in small increments so stop() is responsive
            for _ in range(int(_SAMPLE_INTERVAL * 10)):
                if not self._running:
                    break
                time.sleep(0.1)
