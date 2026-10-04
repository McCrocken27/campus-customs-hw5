"""Append-only audit trail at output/audit_trail.json.

The file is one JSON array. Every event is appended to it as agents run; nothing
is ever removed, and the file is never reset between runs or loops. If the file
exists but isn't valid JSON, we stop instead of overwriting it.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic_core import to_jsonable_python

AUDIT_PATH = Path(__file__).resolve().parent.parent / "output" / "audit_trail.json"
_lock = threading.Lock()


def _read_existing() -> list[Any]:
    if not AUDIT_PATH.exists() or AUDIT_PATH.stat().st_size == 0:
        return []
    events = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    if not isinstance(events, list):
        raise ValueError(f"{AUDIT_PATH} should hold a JSON array; refusing to overwrite it.")
    return events


def read_events() -> list[dict]:
    """Every event so far, oldest first."""
    with _lock:
        return _read_existing()


def append_event(event: str, **fields: Any) -> None:
    """Add one event to the end of the audit trail."""
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event, **fields}
    with _lock:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        events = _read_existing()
        events.append(to_jsonable_python(record, fallback=str))
        tmp = AUDIT_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(events, indent=2, ensure_ascii=False), encoding="utf-8")
        for attempt in range(5):  # OneDrive can briefly lock the file while syncing
            try:
                os.replace(tmp, AUDIT_PATH)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.2)
