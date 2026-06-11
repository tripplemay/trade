"""B054 F-news — ``python -m workbench_api.news_translation.cli`` batch job.

Translates the Simplified-Chinese headline (``news.title_zh``) for rows that
do not have one yet, then commits. Run **after** the news ingest CLI on the
production VM (manual trigger / oneshot — no scheduler, matching the news
ingest boundary). Idempotent: a row already carrying ``title_zh`` is skipped,
so a re-run only spends LLM budget on genuinely-new headlines.

Off the request path (boundary preservation): this is the only place a
generative ``advise`` call touches the news domain, and it writes a
pre-computed column the read path merely selects.

Flags:

``--limit``  Max rows to translate in one run (default 500). Newest-first,
             so a capped run always localizes the freshest headlines first.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.news import NewsRepository
from workbench_api.news_translation.service import (
    NewsTranslationService,
    build_default_translator,
)

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 500


@dataclass(frozen=True, slots=True)
class TranslateSummary:
    """Aggregate result of one translation batch run."""

    translated: int
    skipped: int


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
    return parser.parse_args(argv)


def run_translation(
    session: Session,
    translator: NewsTranslationService,
    *,
    limit: int = DEFAULT_LIMIT,
) -> TranslateSummary:
    """Translate up to ``limit`` untranslated headlines and commit.

    A row whose translation comes back ``None`` (model misbehaved / empty)
    keeps ``title_zh`` NULL so the next run retries it; the serving path
    falls back to the English ``title`` meanwhile."""

    repo = NewsRepository(session)
    rows = repo.list_untranslated(limit=limit)
    translated = 0
    skipped = 0
    try:
        for row in rows:
            zh = translator.translate_title(row.title)
            if zh:
                row.title_zh = zh
                translated += 1
            else:
                skipped += 1
        session.commit()
    except Exception:
        session.rollback()
        raise
    return TranslateSummary(translated=translated, skipped=skipped)


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
        summary = run_translation(session, translator, limit=args.limit)
    finally:
        session.close()
    print(
        f"news translate done — translated={summary.translated} "
        f"skipped={summary.skipped}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
