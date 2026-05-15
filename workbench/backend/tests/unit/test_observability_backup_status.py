"""Tests for ``read_backup_status``."""

from __future__ import annotations

from pathlib import Path

from workbench_api.observability.backup_status import BackupStatus, read_backup_status


def test_returns_none_when_log_absent(tmp_path: Path) -> None:
    status = read_backup_status(tmp_path / "no-such.log")
    assert status == BackupStatus(None, None)


def test_returns_none_when_log_has_no_ok_lines(tmp_path: Path) -> None:
    log = tmp_path / "backup.log"
    log.write_text(
        "2026-05-15T03:00:01Z BEGIN backup db=/var/lib/workbench/db/workbench.db\n"
        "2026-05-15T03:00:02Z FAIL: DB not readable\n",
        encoding="utf-8",
    )
    status = read_backup_status(log)
    assert status == BackupStatus(None, None)


def test_parses_latest_ok_line(tmp_path: Path) -> None:
    log = tmp_path / "backup.log"
    log.write_text(
        "2026-05-14T03:00:01Z OK backup snapshot_bytes=1000 gzip_bytes=400 duration_s=2 remote=gs://b/daily/x.gz\n"
        "2026-05-15T03:00:01Z BEGIN backup\n"
        "2026-05-15T03:00:05Z OK backup snapshot_bytes=2048 gzip_bytes=789 duration_s=3 remote=gs://b/daily/y.gz\n",
        encoding="utf-8",
    )
    # Pin "now" to a known epoch so the age is deterministic.
    # 2026-05-15T03:01:05Z is 60 seconds after the latest OK line.
    import calendar
    import time

    now_epoch = calendar.timegm(time.strptime("2026-05-15T03:01:05Z", "%Y-%m-%dT%H:%M:%SZ"))
    status = read_backup_status(log, now=now_epoch)
    assert status.last_backup_size_bytes == 789
    assert status.last_backup_age_seconds == 60.0


def test_ignores_malformed_lines(tmp_path: Path) -> None:
    log = tmp_path / "backup.log"
    log.write_text(
        "garbage line without timestamp\n"
        "2026-05-15T03:00:05Z OK backup snapshot_bytes=2048 gzip_bytes=789 duration_s=3 remote=gs://b/daily/y.gz\n"
        "another garbage line\n",
        encoding="utf-8",
    )
    status = read_backup_status(log, now=None)
    assert status.last_backup_size_bytes == 789
    assert status.last_backup_age_seconds is not None
    assert status.last_backup_age_seconds >= 0.0
