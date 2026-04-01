"""SQLite storage for meeting history."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class Meeting:
    """Represents a stored meeting."""

    id: int | None = None
    name: str = ""
    created_at: str = ""
    duration_secs: float = 0.0
    wav_path: str = ""
    transcript_text: str = ""
    transcript_segments: list[tuple] = field(default_factory=list)  # (ts, text) or (ts, text, speaker_id)
    summary_text: str = ""
    speaker_names: dict[str, str] = field(default_factory=dict)  # {speaker_id: name}
    updated_at: str = ""


class MeetingDatabase:
    """Synchronous SQLite storage for meetings.

    Thread-safety: this class should be called from a single thread
    (the Qt main thread). SQLite calls are sub-millisecond for typical
    operations, so no worker thread is needed.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            db_path = Path.home() / "Documents" / "ZennoCall" / "zennocall.db"
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                duration_secs REAL DEFAULT 0.0,
                wav_path TEXT DEFAULT '',
                transcript_text TEXT DEFAULT '',
                transcript_segments TEXT DEFAULT '[]',
                summary_text TEXT DEFAULT '',
                updated_at TEXT NOT NULL
            )"""
        )
        # Migration: add speaker_names column if missing
        cols = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(meetings)")
        }
        if "speaker_names" not in cols:
            self._conn.execute(
                "ALTER TABLE meetings ADD COLUMN speaker_names TEXT DEFAULT '{}'"
            )
        self._conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def save_meeting(self, meeting: Meeting) -> int:
        """Insert a new meeting. Returns the new row id."""
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        segments_json = json.dumps(meeting.transcript_segments)
        speaker_names_json = json.dumps(meeting.speaker_names)
        cursor = self._conn.execute(
            """INSERT INTO meetings
               (name, created_at, duration_secs, wav_path,
                transcript_text, transcript_segments, summary_text,
                speaker_names, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                meeting.name,
                meeting.created_at or now,
                meeting.duration_secs,
                meeting.wav_path,
                meeting.transcript_text,
                segments_json,
                meeting.summary_text,
                speaker_names_json,
                now,
            ),
        )
        self._conn.commit()
        return cursor.lastrowid

    def update_name(self, meeting_id: int, name: str) -> None:
        """Update name for an existing meeting."""
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._conn.execute(
            "UPDATE meetings SET name = ?, updated_at = ? WHERE id = ?",
            (name, now, meeting_id),
        )
        self._conn.commit()

    def update_summary(self, meeting_id: int, summary_text: str) -> None:
        """Update summary for an existing meeting."""
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._conn.execute(
            "UPDATE meetings SET summary_text = ?, updated_at = ? WHERE id = ?",
            (summary_text, now, meeting_id),
        )
        self._conn.commit()

    def update_transcript(
        self,
        meeting_id: int,
        transcript_text: str,
        segments: list[tuple],
    ) -> None:
        """Replace transcript for a meeting (after retranscription)."""
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        segments_json = json.dumps(segments)
        self._conn.execute(
            """UPDATE meetings
               SET transcript_text = ?, transcript_segments = ?, updated_at = ?
               WHERE id = ?""",
            (transcript_text, segments_json, now, meeting_id),
        )
        self._conn.commit()

    def update_speaker_names(
        self, meeting_id: int, speaker_names: dict[str, str]
    ) -> None:
        """Update speaker name mapping for a meeting."""
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._conn.execute(
            "UPDATE meetings SET speaker_names = ?, updated_at = ? WHERE id = ?",
            (json.dumps(speaker_names), now, meeting_id),
        )
        self._conn.commit()

    def get_meeting(self, meeting_id: int) -> Meeting | None:
        """Load a single meeting by ID."""
        row = self._conn.execute(
            "SELECT * FROM meetings WHERE id = ?", (meeting_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_meeting(row)

    def list_meetings(self) -> list[Meeting]:
        """Return all meetings, newest first."""
        rows = self._conn.execute(
            "SELECT * FROM meetings ORDER BY created_at DESC"
        ).fetchall()
        return [self._row_to_meeting(r) for r in rows]

    def search_meetings(self, query: str) -> list[Meeting]:
        """Search by name or transcript content (case-insensitive)."""
        pattern = f"%{query}%"
        rows = self._conn.execute(
            """SELECT * FROM meetings
               WHERE name LIKE ? OR transcript_text LIKE ?
               ORDER BY created_at DESC""",
            (pattern, pattern),
        ).fetchall()
        return [self._row_to_meeting(r) for r in rows]

    def delete_meeting(self, meeting_id: int) -> bool:
        """Delete a meeting. Returns True if a row was deleted."""
        cursor = self._conn.execute(
            "DELETE FROM meetings WHERE id = ?", (meeting_id,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_meeting(row: sqlite3.Row) -> Meeting:
        segments = (
            json.loads(row["transcript_segments"])
            if row["transcript_segments"]
            else []
        )
        speaker_names_raw = row["speaker_names"] if "speaker_names" in row.keys() else "{}"
        speaker_names = json.loads(speaker_names_raw) if speaker_names_raw else {}
        return Meeting(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
            duration_secs=row["duration_secs"],
            wav_path=row["wav_path"] or "",
            transcript_text=row["transcript_text"] or "",
            transcript_segments=[tuple(s) for s in segments],
            summary_text=row["summary_text"] or "",
            speaker_names=speaker_names if isinstance(speaker_names, dict) else {},
            updated_at=row["updated_at"],
        )
