"""B064 F002 — on-demand CN/HK news ingest (akshare stock_news_em → news table).

DB-backed (the shared ``news`` table) with an injected fake fetcher returning
real-shape akshare records (关键词/新闻标题/新闻内容/发布时间/文章来源/新闻链接).
Pins: field mapping + Beijing→UTC published time, canonical ticker keying,
``title_zh`` set (Chinese headline → translation job skips), idempotent
re-ingest, EOD cache-first skip, and honest empty on an unreachable source.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.news import NewsRepository
from workbench_api.symbols.cn_hk_news import (
    EASTMONEY_SOURCE,
    _to_news_item,
    ingest_symbol_news,
)
from workbench_api.symbols.symbol_ref import SymbolRef

_NOW = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)


def _record(title: str, url: str, when: str = "2026-06-12 10:27:00") -> dict[str, object]:
    return {
        "关键词": "600519",
        "新闻标题": title,
        "新闻内容": "贵州茅台公告披露……（摘要）",
        "发布时间": when,
        "文章来源": "南方财经网",
        "新闻链接": url,
    }


_CN_RECORDS = [
    _record("贵州茅台：余思明获聘董事会秘书", "http://finance.eastmoney.com/a/202606123769599746.html"),
    _record("贵州茅台：聘任余思明为董秘", "http://finance.eastmoney.com/a/202606113768543493.html"),
]


def test_to_news_item_maps_fields_and_beijing_to_utc() -> None:
    ref = SymbolRef.parse("600519.SH")
    item = _to_news_item(_CN_RECORDS[0], ref)
    assert item is not None
    assert item.source == EASTMONEY_SOURCE
    assert item.source_id == "202606123769599746"  # article id from URL
    assert item.ticker == "600519.SH"  # canonical, so list_by_ticker finds it
    assert item.title == "贵州茅台：余思明获聘董事会秘书"
    assert item.summary is not None
    # 2026-06-12 10:27 Beijing (UTC+8) → 02:27 UTC.
    assert item.published_at == datetime(2026, 6, 12, 2, 27, tzinfo=UTC)


def test_to_news_item_skips_rows_missing_required_fields() -> None:
    ref = SymbolRef.parse("600519.SH")
    ts = "2026-06-12 10:00:00"
    assert _to_news_item({"新闻标题": "", "新闻链接": "x", "发布时间": ts}, ref) is None
    assert _to_news_item({"新闻标题": "t", "新闻链接": "", "发布时间": ts}, ref) is None
    assert _to_news_item({"新闻标题": "t", "新闻链接": "u", "发布时间": "garbage"}, ref) is None


def test_ingest_persists_rows_keyed_to_canonical_with_title_zh(initialised_db: str) -> None:
    ref = SymbolRef.parse("600519.SH")
    with Session(get_engine()) as session:
        n = ingest_symbol_news(session, ref, fetcher=lambda _c: list(_CN_RECORDS), now=_NOW)
        session.commit()
        assert n == 2
        repo = NewsRepository(session)
        rows = repo.list_by_ticker("600519.SH", limit=10)
        assert len(rows) == 2
        for row in rows:
            assert row.source == "eastmoney"
            assert row.ticker == "600519.SH"
            assert row.title_zh == row.title  # Chinese → translation job skips
            assert row.snapshot_path.startswith("http")  # virtual: upstream URL


def test_ingest_is_idempotent_on_reingest(initialised_db: str) -> None:
    ref = SymbolRef.parse("600519.SH")
    with Session(get_engine()) as session:
        first = ingest_symbol_news(session, ref, fetcher=lambda _c: list(_CN_RECORDS), now=_NOW)
        session.commit()
        # Re-ingest the SAME articles a day later → no duplicates (save_if_new).
        later = _NOW + timedelta(days=1)
        again = ingest_symbol_news(
            session, ref, fetcher=lambda _c: list(_CN_RECORDS), now=later
        )
        session.commit()
        assert first == 2
        assert again == 0  # (source, source_id) dedup
        assert NewsRepository(session).count() == 2


def test_ingest_cache_first_skips_same_day_fetch(initialised_db: str) -> None:
    ref = SymbolRef.parse("600519.SH")
    calls: list[str] = []

    def _counting_fetcher(code: str) -> list[dict[str, object]]:
        calls.append(code)
        return list(_CN_RECORDS)

    with Session(get_engine()) as session:
        ingest_symbol_news(session, ref, fetcher=_counting_fetcher, now=_NOW)
        session.commit()
        # Same UTC day → cache-first short-circuits before the fetcher.
        ingest_symbol_news(session, ref, fetcher=_counting_fetcher, now=_NOW + timedelta(hours=2))
        assert calls == ["600519"]  # fetched once


def test_hk_ingest_uses_5digit_native_code(initialised_db: str) -> None:
    ref = SymbolRef.parse("0700.HK")
    seen: list[str] = []

    def _fetcher(code: str) -> list[dict[str, object]]:
        seen.append(code)
        return [_record("腾讯控股回购", "http://finance.eastmoney.com/a/202606173774831315.html")]

    with Session(get_engine()) as session:
        n = ingest_symbol_news(session, ref, fetcher=_fetcher, now=_NOW)
        session.commit()
        assert seen == ["00700"]  # HK zero-padded native code
        assert n == 1
        rows = NewsRepository(session).list_by_ticker("0700.HK", limit=5)
        assert len(rows) == 1
        assert rows[0].ticker == "0700.HK"


def test_ingest_empty_source_yields_zero(initialised_db: str) -> None:
    ref = SymbolRef.parse("600519.SH")
    with Session(get_engine()) as session:
        n = ingest_symbol_news(session, ref, fetcher=lambda _c: [], now=_NOW)
        session.commit()
        assert n == 0
        assert NewsRepository(session).count() == 0
