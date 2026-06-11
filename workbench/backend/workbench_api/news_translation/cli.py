"""B054 F-news — ``python -m workbench_api.news_translation.cli`` batch job.

Translates the Simplified-Chinese headline (``news.title_zh``) for rows that
do not have one yet, then commits. Run **after** the news ingest CLI on the
production VM (manual trigger / oneshot, and a daily timer chained after
``workbench-news.timer`` — no in-process scheduler, matching the news ingest
boundary). Idempotent: a row already carrying ``title_zh`` is skipped, so a
re-run only spends LLM budget on genuinely-new headlines.

Off the request path (boundary preservation): this is the only place a
generative ``advise`` call touches the news domain, and it writes a
pre-computed column the read path merely selects.

Resilience (the aigc-gateway rate-limits bursts of chat calls):

* The loop **paces** requests (``--sleep`` seconds between rows) to stay
  under the gateway's rate window; the gateway itself already retries a 429
  three times with backoff.
* A per-row **transient HTTP error** (rate-limit retries exhausted, network)
  is caught — that row keeps ``title_zh`` NULL and the batch moves on, so a
  single 429 never aborts a 1700-row run. The next run retries it.
* Progress is **committed incrementally** (every ``commit_every`` rows) so a
  killed / interrupted run never loses the headlines it already translated.
* A real budget-cap trip (``BudgetExceeded``) is **not** caught — it
  propagates so the batch halts instead of hammering an exhausted cap.

Flags:

``--limit``  Max rows to translate in one run (default 2000). Newest-first,
             so a capped run always localizes the freshest headlines first.
``--sleep``  Seconds to pause between rows (default 0.6) — the rate-limit
             throttle.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.news import NewsRepository
from workbench_api.news_translation.service import (
    NewsTranslationService,
    build_default_translator,
)

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 2000
DEFAULT_SLEEP_SECONDS = 0.6
DEFAULT_COMMIT_EVERY = 25


@dataclass(frozen=True, slots=True)
class TranslateSummary:
    """Aggregate result of one translation batch run.

    ``translated`` wrote a ``title_zh``; ``skipped`` got an empty / over-long
    model output (left NULL, retried next run); ``failed`` hit a transient
    gateway error after retries (left NULL, retried next run)."""

    translated: int
    skipped: int
    failed: int


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m workbench_api.news_translation.cli",
        description="B054 news headline → Simplified Chinese translation batch.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help="Max untranslated rows to process this run (default: %(default)s).",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=DEFAULT_SLEEP_SECONDS,
        help="Seconds to pause between rows, rate-limit throttle (default: %(default)s).",
    )
    return parser.parse_args(argv)


def run_translation(
    session: Session,
    translator: NewsTranslationService,
    *,
    limit: int = DEFAULT_LIMIT,
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
    commit_every: int = DEFAULT_COMMIT_EVERY,
    sleep: Callable[[float], None] = time.sleep,
) -> TranslateSummary:
    """Translate up to ``limit`` untranslated headlines, committing as it goes.

    Transient gateway errors are absorbed per-row (the row stays NULL for the
    next run); a ``BudgetExceeded`` cap trip propagates so the batch halts."""

    repo = NewsRepository(session)
    rows = repo.list_untranslated(limit=limit)
    translated = 0
    skipped = 0
    failed = 0
    pending = 0
    try:
        for index, row in enumerate(rows):
            try:
                zh = translator.translate_title(row.title)
            except httpx.HTTPError as exc:
                # Rate-limit retries exhausted / network blip — leave NULL,
                # the next run picks it up. Does not abort the batch.
                logger.warning(
                    "news_translate_row_failed",
                    extra={"news_id": str(row.id), "error": str(exc)},
                )
                failed += 1
                zh = None
            if zh:
                row.title_zh = zh
                translated += 1
                pending += 1
            else:
                skipped += 1
            if pending >= commit_every:
                session.commit()
                pending = 0
            if sleep_seconds and index < len(rows) - 1:
                sleep(sleep_seconds)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return TranslateSummary(translated=translated, skipped=skipped, failed=failed)


def main(argv: list[str] | None = None) -> int:
    """Entrypoint for ``python -m workbench_api.news_translation.cli``."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = parse_args(argv)
    translator = build_default_translator()
    if translator is None:
        # No gateway key (local / CI) — degrade cleanly. Untranslated
        # headlines fall back to English on the serving path.
        print("news translate skipped — LLM gateway unavailable (no key)")
        return 0

    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session = factory()
    try:
        summary = run_translation(
            session, translator, limit=args.limit, sleep_seconds=args.sleep
        )
    finally:
        session.close()
    print(
        f"news translate done — translated={summary.translated} "
        f"skipped={summary.skipped} failed={summary.failed}"
    )
    # Non-zero exit when every row failed transiently (so an operator / the
    # systemd timer surfaces a fully-rate-limited run); a partial run is a
    # success (progress was made, the rest retries next run).
    return 1 if summary.failed > 0 and summary.translated == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
