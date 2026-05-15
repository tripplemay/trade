"""Parse the workbench backup log to surface freshness on /api/health.

``workbench-backup.sh`` appends one ``OK backup`` line per successful run
with a structured payload:

    2026-05-15T03:00:01Z OK backup snapshot_bytes=1234 gzip_bytes=567 duration_s=4 remote=gs://...

We tail the file, find the latest ``OK backup`` line, extract the
timestamp + gzip size, and translate to seconds-since-now / bytes for
the JSON payload. A missing file, an unparseable line, or zero ``OK``
lines all degrade to ``BackupStatus(None, None)`` rather than raising —
the spec wants ``/api/health`` to stay green even when backups have
never run, so the deploy healthcheck can still pass.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

_OK_LINE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\s+OK backup\b.*?\bgzip_bytes=(?P<bytes>\d+)\b",
)
"""Match lines emitted by workbench-backup.sh on success.

Anchored on the timestamp + literal `OK backup` so partial / FAIL lines
do not poison the result. ``gzip_bytes=`` is required because that is
the field the spec asks ``last_backup_size_bytes`` to surface.
"""


@dataclass(frozen=True, slots=True)
class BackupStatus:
    """Result of parsing the backup log.

    ``None`` on either field means the metric is unknown (no backup has
    ever finished cleanly, or the log file is missing). Handlers should
    serialise these as JSON ``null`` rather than 0 so monitoring can
    distinguish "no backups yet" from "fresh successful backup of size 0".
    """

    last_backup_age_seconds: float | None
    last_backup_size_bytes: int | None


def read_backup_status(log_path: str | Path, *, now: float | None = None) -> BackupStatus:
    path = Path(log_path)
    if not path.is_file():
        return BackupStatus(None, None)

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return BackupStatus(None, None)

    last_ts: str | None = None
    last_bytes: int | None = None
    for line in text.splitlines():
        match = _OK_LINE.match(line)
        if match is None:
            continue
        last_ts = match.group("ts")
        last_bytes = int(match.group("bytes"))

    if last_ts is None or last_bytes is None:
        return BackupStatus(None, None)

    last_epoch = _iso_z_to_epoch(last_ts)
    if last_epoch is None:
        return BackupStatus(None, last_bytes)

    now_epoch = now if now is not None else time.time()
    age = max(0.0, now_epoch - last_epoch)
    return BackupStatus(age, last_bytes)


def _iso_z_to_epoch(value: str) -> float | None:
    """Convert ``YYYY-MM-DDTHH:MM:SSZ`` (UTC) to a POSIX timestamp."""

    try:
        struct = time.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    return _calendar_gm(struct)


def _calendar_gm(struct: time.struct_time) -> float:
    """``calendar.timegm`` equivalent without the extra import."""

    import calendar

    return float(calendar.timegm(struct))
