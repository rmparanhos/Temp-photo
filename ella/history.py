from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

HISTORY_PATH = Path.home() / ".ella" / "history.json"
MAX_ENTRIES = 10


@dataclass
class HistoryEntry:
    path: Path
    last_run: datetime


def load() -> list[HistoryEntry]:
    if not HISTORY_PATH.exists():
        return []
    try:
        data = json.loads(HISTORY_PATH.read_text())
        return [
            HistoryEntry(
                path=Path(e["path"]),
                last_run=datetime.fromisoformat(e["last_run"]),
            )
            for e in data
        ]
    except Exception:
        return []


def record(path: Path) -> None:
    entries = [e for e in load() if e.path != path]
    entries.insert(0, HistoryEntry(path=path, last_run=datetime.now()))
    _save(entries[:MAX_ENTRIES])


def _save(entries: list[HistoryEntry]) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(
        json.dumps(
            [{"path": str(e.path), "last_run": e.last_run.isoformat()} for e in entries],
            indent=2,
        )
    )


def time_ago(dt: datetime) -> str:
    diff = datetime.now() - dt
    if diff.days == 0:
        hours = diff.seconds // 3600
        if hours == 0:
            mins = diff.seconds // 60
            return "just now" if mins == 0 else f"{mins}m ago"
        return f"{hours}h ago"
    if diff.days == 1:
        return "yesterday"
    if diff.days < 7:
        return f"{diff.days} days ago"
    weeks = diff.days // 7
    return f"{weeks} week{'s' if weeks > 1 else ''} ago"
