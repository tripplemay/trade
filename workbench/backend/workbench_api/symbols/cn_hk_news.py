"""B064 F002 — on-demand CN/HK individual-stock news ingest (akshare 东财).

The US news surface (B034/B035) is a *batch* job (SEC/Yahoo, universe-bound).
But the symbol-lookup surface is **any ticker** — we cannot pre-ingest the whole
A-share / HK universe. So CN/HK news is **on-demand cache-first** (B064 spec
§4 F002, planner decision):

1. request `/{symbol}/news` for a CN/HK ticker →
2. EOD cache-first: if eastmoney news for this ticker was already ingested today
   (UTC), skip the fetch and serve the rows already in the ``news`` table;
3. otherwise lazy-call akshare ``stock_news_em`` (§23-verified reachable for
   **both** CN ``600519`` and HK ``00700`` — Chinese headlines, no translation
   needed), normalise to ``NewsItem`` rows, and ``save_if_new`` (idempotent by
   ``(source, source_id)``) into the shared ``news`` table keyed to the
   canonical ticker. The existing ``get_symbol_news`` read then surfaces them.

**Snapshot handling (deliberate deviation from the batch adapters):** the batch
adapters write each raw body to disk and store a ``data/snapshots/news/…``
relative path. The lookup surface never *reads* the snapshot (it shows
title / url / published_at only), and request-path disk I/O + a writable
snapshot dir are undesirable couplings. Since nothing reads ``snapshot_path``
for served news, we store the upstream article URL as ``snapshot_path`` (the
body lives at eastmoney, not on our disk) and a content hash for drift / dedup.
The ``news`` table schema + metadata-only boundary (no raw-body column) are
untouched.

**Titles already Simplified-Chinese** (§23) → ``title_zh`` is set to the source
title so (a) the lookup shows Chinese and (b) the B054 translation batch job
skips them (it only picks ``title_zh IS NULL``) — no Chinese→Chinese LLM spend.
The B054 translation boundary itself is untouched.

request-path safe (§12.10.2): imports neither ``trade`` nor a broker SDK;
akshare is lazy-imported inside ``_default_fetcher``. Every external call is
wrapped by the caller so an akshare failure degrades to the honest empty state
(no rows), never a 500.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from workbench_api.data.market_context_common import NoOpRateLimitGuard, RateLimitGuard
from workbench_api.db.repositories.news import NewsRepository
from workbench_api.news.adapters.base import NewsItem
from workbench_api.symbols.symbol_ref import SymbolRef

EASTMONEY_SOURCE = "eastmoney"
# 东财 publishes Beijing time (UTC+8); normalise to aware UTC like the other feeds.
_BEIJING = timezone(timedelta(hours=8))
# Cap how many headlines we persist per fetch (akshare returns ~10).
_MAX_ITEMS = 20

# Injectable fetcher: canonical-native code → list of akshare news records.
NewsFetcher = Callable[[str], list[dict[str, Any]]]


def _default_fetcher(code: str) -> list[dict[str, Any]]:
    """Lazy akshare ``stock_news_em`` fetch (CN 6-digit / HK 5-digit code).

    Returns ``[]`` on any failure (akshare absent, host unreachable, bad frame)
    so the caller degrades to the honest empty state."""

    try:
        import akshare as ak  # lazy — module loads where akshare is absent

        frame = ak.stock_news_em(symbol=code)
    except Exception:
        return []
    if frame is None:
        return []
    try:
        records: list[dict[str, Any]] = frame.to_dict("records")
    except Exception:
        return []
    return records


def _native_code(ref: SymbolRef) -> str:
    """akshare-native code: CN keeps the 6-digit code; HK zero-pads to 5."""
    return ref.code.zfill(5) if ref.market == "HK" else ref.code


def _parse_published(raw: object) -> datetime | None:
    """东财 ``发布时间`` 'YYYY-MM-DD HH:MM:SS' (Beijing) → aware UTC, or None."""
    text = str(raw or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            naive = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return naive.replace(tzinfo=_BEIJING).astimezone(UTC)
    return None


def _article_id(url: str) -> str:
    """Stable source_id for idempotency: the eastmoney article id from the URL
    (…/a/<id>.html), falling back to a hash of the URL."""
    match = re.search(r"/([0-9A-Za-z]+)\.html", url)
    if match:
        return match.group(1)
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]


def _to_news_item(record: dict[str, Any], ref: SymbolRef) -> NewsItem | None:
    """Normalise one akshare ``stock_news_em`` record → :class:`NewsItem`.

    Returns None when the required fields (title / url / published_at) are
    missing or unparseable — those rows are skipped rather than persisted with
    a NULL that violates the ``news`` NOT NULL constraints."""

    title = str(record.get("新闻标题") or "").strip()
    url = str(record.get("新闻链接") or "").strip()
    published_at = _parse_published(record.get("发布时间"))
    if not title or not url or published_at is None:
        return None
    content = str(record.get("新闻内容") or "").strip() or None
    return NewsItem(
        source=EASTMONEY_SOURCE,
        source_id=_article_id(url),
        url=url,
        title=title,
        summary=content,
        ticker=ref.canonical,
        form_type=None,
        published_at=published_at,
        raw_body=(content or title).encode("utf-8"),
        raw_ext="txt",
    )


def _content_sha256(item: NewsItem) -> str:
    payload = f"{item.title}\n{item.summary or ''}\n{item.url}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def ingest_symbol_news(
    session: Session,
    ref: SymbolRef,
    *,
    fetcher: NewsFetcher | None = None,
    guard: RateLimitGuard | None = None,
    now: datetime | None = None,
) -> int:
    """On-demand cache-first ingest of CN/HK news for ``ref``; returns the count
    of newly-persisted rows (0 when cache-fresh or the source is unreachable).

    Best-effort by contract: callers wrap this so any failure degrades to the
    honest empty state. Cache-first bounds akshare to ≤1 fetch / ticker / UTC
    day; ``save_if_new`` makes re-ingest idempotent."""

    stamp = now or datetime.now(UTC)
    repo = NewsRepository(session)

    latest = repo.latest_fetched_at_for_ticker(ref.canonical, source=EASTMONEY_SOURCE)
    if latest is not None and _utc_date(latest) >= stamp.astimezone(UTC).date():
        return 0  # already ingested today → serve from the table

    (guard or NoOpRateLimitGuard()).check_and_increment()
    records = (fetcher or _default_fetcher)(_native_code(ref))

    ingested = 0
    for record in records[:_MAX_ITEMS]:
        item = _to_news_item(record, ref)
        if item is None:
            continue
        row = repo.save_if_new(
            item,
            snapshot_path=item.url,
            content_sha256=_content_sha256(item),
            fetched_at=stamp,
        )
        if row is not None:
            # Chinese headline → set title_zh so the B054 translation job skips
            # it (Chinese→Chinese is wasteful) and the lookup shows Chinese.
            row.title_zh = item.title
            ingested += 1
    return ingested


def _utc_date(stamp: datetime) -> Any:
    """Calendar date of ``stamp`` in UTC, tolerating naive timestamps SQLite
    hands back for ``DateTime(timezone=True)`` columns."""
    if stamp.tzinfo is None:
        return stamp.date()
    return stamp.astimezone(UTC).date()
