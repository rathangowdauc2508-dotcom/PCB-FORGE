from __future__ import annotations

from threading import Lock
import time

_lock = Lock()
_runs: dict[str, tuple[str, float]] = {}


def set_run_stage(run_id: str | None, stage: str) -> None:
    if not run_id:
        return
    now = time.time()
    with _lock:
        expired = [key for key, (_, updated) in _runs.items() if now - updated > 1800]
        for key in expired:
            _runs.pop(key, None)
        if len(_runs) >= 500 and run_id not in _runs:
            oldest = min(_runs, key=lambda key: _runs[key][1])
            _runs.pop(oldest, None)
        _runs[run_id] = (stage, now)


def get_run_stage(run_id: str) -> str:
    with _lock:
        item = _runs.get(run_id)
        return item[0] if item else "queued"
