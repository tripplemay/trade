#!/usr/bin/env python
"""Probe whether CNInfo PDFs can seed a versioned A-share as-filed archive.

This evaluator-owned pilot downloads a frozen 50-document sample in memory:
48 regular Q1/H1/Q3 reports across 2015/2019/2023/2025 plus one original and
corrected report pair.  It records immutable announcement identifiers, URLs and
hashes, tests PDF text extraction, and compares extracted parent net profit with
the repository's current structured snapshot when available.

The pilot never computes signal returns or a CNY 2.1m portfolio backtest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = (
    REPO_ROOT
    / "docs/test-reports/ashare-as-filed-data-pilot-2026-07-12.json"
)
TEST_PATH = REPO_ROOT / "tests/unit/test_ashare_as_filed_data_pilot.py"
CURRENT_REPORTS_PATH = (
    REPO_ROOT / "data/research/codex_quality_sue/raw_reports.csv.gz"
)

QUERY_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
DETAIL_URL = "https://www.cninfo.com.cn/new/announcement/bulletin_detail"
STATIC_BASE = "https://static.cninfo.com.cn/"
SAMPLE_YEARS = (2015, 2019, 2023, 2025)
DOCUMENTS_PER_BUCKET = 4
MAX_QUERY_PAGES = 6
MAX_PDF_BYTES = 20 * 1024 * 1024
SAMPLE_TARGET = 50

REPORT_SPECS = (
    {
        "key": "q1",
        "category": "category_yjdbg_szsh;",
        "start": "04-01",
        "end": "05-10",
        "period": "03-31",
        "pattern": r"年(?:第)?一季度报告",
    },
    {
        "key": "h1",
        "category": "category_bndbg_szsh;",
        "start": "07-01",
        "end": "09-30",
        "period": "06-30",
        "pattern": r"年半年度报告",
    },
    {
        "key": "q3",
        "category": "category_sjdbg_szsh;",
        "start": "10-01",
        "end": "11-15",
        "period": "09-30",
        "pattern": r"年(?:第)?三季度报告",
    },
)

PARENT_PROFIT_LABEL = "归属于上市公司股东的净利润"
CONSOLIDATED_PARENT_PROFIT_LABELS = (
    "归属于母公司所有者的净利润",
    "归属于母公司股东的净利润",
)
BASIC_EPS_LABEL = "基本每股收益"
EXCLUDED_TITLE_MARKERS = (
    "摘要",
    "英文",
    "更正",
    "修订",
    "修正",
    "补充",
    "更新",
    "图文版",
    "H股公告",
    "取消",
    "问询",
    "提示",
    "关于",
)


@dataclass(frozen=True, slots=True)
class Announcement:
    sec_code: str
    sec_name: str
    org_id: str
    announcement_id: str
    title: str
    announcement_time_ms: int
    adjunct_url: str
    report_key: str
    report_period: str
    bucket: str

    @property
    def pdf_url(self) -> str:
        return STATIC_BASE + self.adjunct_url.lstrip("/")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_title(value: Any) -> str:
    text = re.sub(r"<[^>]+>", "", str(value or ""))
    return re.sub(r"\s+", "", text)


def is_regular_report_title(title: str, year: int, pattern: str) -> bool:
    cleaned = clean_title(title)
    if str(year) not in cleaned or re.search(pattern, cleaned) is None:
        return False
    return not any(marker in cleaned for marker in EXCLUDED_TITLE_MARKERS)


def compact_text(value: str) -> str:
    return re.sub(r"\s+", "", value).replace("，", ",")


def extract_number_after_label(text: str, label: str) -> float | None:
    flat = re.sub(r"\s+", " ", text).replace("，", ",")
    position = flat.find(label)
    if position >= 0:
        segment = flat[position + len(label) : position + len(label) + 160]
    elif label == PARENT_PROFIT_LABEL:
        prefix = "归属于上市公司股东的净利"
        position = flat.find(prefix)
        if position < 0:
            return None
        segment = flat[position + len(prefix) : position + len(prefix) + 160]
    else:
        return None
    match = re.search(
        r"(?:（[^）]{0,12}）)?[^\d-]{0,24}(-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)",
        segment,
    )
    if match is None:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _label_context(text: str, label: str) -> tuple[str, str] | None:
    flat = re.sub(r"\s+", " ", text).replace("，", ",")
    position = flat.find(label)
    label_length = len(label)
    if position < 0 and label == PARENT_PROFIT_LABEL:
        prefix = "归属于上市公司股东的净利"
        position = flat.find(prefix)
        label_length = len(prefix)
    if position < 0:
        return None
    before = flat[max(0, position - 1_600) : position]
    after = flat[position + label_length : position + label_length + 360]
    return before, after


def _non_percent_numbers(value: str) -> list[float]:
    numbers: list[float] = []
    pattern = re.compile(r"-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")
    for match in pattern.finditer(value):
        tail = value[match.end() : match.end() + 2]
        if "%" in tail:
            continue
        try:
            numbers.append(float(match.group(0).replace(",", "")))
        except ValueError:
            continue
    return numbers


def _unit_scale(before: str, after: str) -> tuple[str | None, float]:
    context = before + after[:60]
    matches = re.findall(
        r"(?:金额)?单位\s*[:：]?\s*(?:人民币)?\s*(百万元|万元|千元|元)",
        context,
    )
    unit = matches[-1] if matches else None
    scale = {"元": 1.0, "千元": 1_000.0, "万元": 10_000.0, "百万元": 1_000_000.0}
    return unit, scale.get(unit, 1.0)


def _split_consolidated_row(text: str) -> tuple[str, str] | None:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        compact = re.sub(r"\s+", "", line)
        marker = compact.find("归属于母公")
        if marker < 0:
            continue
        block = " ".join(lines[index : index + 3])
        compact_block = re.sub(r"\s+", "", block)
        if "净利润" not in compact_block or "权益" in compact_block.split("净利润", 1)[0]:
            continue
        before = " ".join(lines[max(0, index - 35) : index])
        position = block.find("归属于")
        return before, block[position:]
    return None


def extract_parent_profit(
    text: str, report_key: str
) -> dict[str, float | str | int | None]:
    split_context = _split_consolidated_row(text)
    if split_context is not None:
        before, after = split_context
        numbers = _non_percent_numbers(after)
        selected_index = 2 if report_key == "q3" and len(numbers) >= 4 else 0
        raw_value = numbers[selected_index] if len(numbers) > selected_index else None
        if raw_value is not None:
            unit, scale = _unit_scale(before, after)
            return {
                "raw_value": raw_value,
                "value": raw_value * scale,
                "unit": unit,
                "selected_index": selected_index,
                "source_label": "split_consolidated_income_statement",
            }
    for label in (*CONSOLIDATED_PARENT_PROFIT_LABELS, PARENT_PROFIT_LABEL):
        context = _label_context(text, label)
        if context is None:
            continue
        before, after = context
        numbers = _non_percent_numbers(after)
        if label == PARENT_PROFIT_LABEL and report_key == "q3":
            selected_index = 2 if len(numbers) >= 4 else (1 if len(numbers) >= 2 else 0)
        else:
            selected_index = 0
        raw_value = numbers[selected_index] if len(numbers) > selected_index else None
        if raw_value is None:
            continue
        unit, scale = _unit_scale(before, after)
        return {
            "raw_value": raw_value,
            "value": raw_value * scale,
            "unit": unit,
            "selected_index": selected_index,
            "source_label": label,
        }
    return {
        "raw_value": None,
        "value": None,
        "unit": None,
        "selected_index": None,
        "source_label": None,
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


class CninfoClient:
    def __init__(self, *, timeout: float = 45.0, attempts: int = 4) -> None:
        self.timeout = timeout
        self.attempts = attempts
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.cninfo.com.cn/",
                "X-Requested-With": "XMLHttpRequest",
            }
        )

    def _post_json(
        self, url: str, *, data: dict[str, str] | None = None, params: dict[str, str] | None = None
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            try:
                response = self.session.post(
                    url,
                    data=data,
                    params=params,
                    timeout=(10, self.timeout),
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("CNInfo response is not an object")
                return payload
            except Exception as exc:  # noqa: BLE001 - bounded public-source retry
                last_error = exc
                if attempt + 1 < self.attempts:
                    time.sleep(0.75 * (attempt + 1))
        raise RuntimeError(f"CNInfo request failed: {url}") from last_error

    def query(
        self,
        *,
        page: int,
        start: str,
        end: str,
        category: str,
        search_key: str = "",
        stock: str = "",
        page_size: int = 30,
    ) -> dict[str, Any]:
        return self._post_json(
            QUERY_URL,
            data={
                "pageNum": str(page),
                "pageSize": str(page_size),
                "column": "szse",
                "tabName": "fulltext",
                "plate": "",
                "stock": stock,
                "searchkey": search_key,
                "secid": "",
                "category": category,
                "trade": "",
                "seDate": f"{start}~{end}",
                "sortName": "",
                "sortType": "",
                "isHLtitle": "true",
            },
        )

    def detail(self, announcement: Announcement) -> dict[str, Any]:
        date = datetime.fromtimestamp(
            announcement.announcement_time_ms / 1000, tz=UTC
        ).date().isoformat()
        return self._post_json(
            DETAIL_URL,
            params={
                "announceId": announcement.announcement_id,
                "flag": "true",
                "announceTime": date,
            },
        )

    def download(self, url: str) -> tuple[bytes, dict[str, str | int | None]]:
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            try:
                with self.session.get(url, stream=True, timeout=(10, self.timeout)) as response:
                    response.raise_for_status()
                    chunks: list[bytes] = []
                    size = 0
                    for chunk in response.iter_content(1024 * 1024):
                        if not chunk:
                            continue
                        size += len(chunk)
                        if size > MAX_PDF_BYTES:
                            raise ValueError(f"PDF exceeds {MAX_PDF_BYTES} bytes")
                        chunks.append(chunk)
                    body = b"".join(chunks)
                    return body, {
                        "http_status": response.status_code,
                        "content_type": response.headers.get("Content-Type"),
                        "last_modified": response.headers.get("Last-Modified"),
                        "content_length": len(body),
                    }
            except Exception as exc:  # noqa: BLE001 - bounded public-source retry
                last_error = exc
                if attempt + 1 < self.attempts:
                    time.sleep(0.75 * (attempt + 1))
        raise RuntimeError(f"CNInfo PDF download failed: {url}") from last_error


def _announcement_from_row(
    row: dict[str, Any], *, report_key: str, report_period: str, bucket: str
) -> Announcement:
    return Announcement(
        sec_code=str(row.get("secCode") or ""),
        sec_name=str(row.get("secName") or ""),
        org_id=str(row.get("orgId") or ""),
        announcement_id=str(row.get("announcementId") or ""),
        title=clean_title(row.get("announcementTitle")),
        announcement_time_ms=int(row.get("announcementTime") or 0),
        adjunct_url=str(row.get("adjunctUrl") or ""),
        report_key=report_key,
        report_period=report_period,
        bucket=bucket,
    )


def select_regular_sample(
    client: CninfoClient,
) -> tuple[list[Announcement], list[dict[str, Any]]]:
    selected: list[Announcement] = []
    diagnostics: list[dict[str, Any]] = []
    for year in SAMPLE_YEARS:
        for spec in REPORT_SPECS:
            start = f"{year}-{spec['start']}"
            end = f"{year}-{spec['end']}"
            bucket = f"{year}-{spec['key']}"
            rows_seen = 0
            candidates: list[Announcement] = []
            seen_codes: set[str] = set()
            pages_used = 0
            for page in range(1, MAX_QUERY_PAGES + 1):
                payload = client.query(
                    page=page,
                    start=start,
                    end=end,
                    category=str(spec["category"]),
                )
                pages_used = page
                rows = list(payload.get("announcements") or [])
                rows_seen += len(rows)
                for row in rows:
                    code = str(row.get("secCode") or "")
                    title = clean_title(row.get("announcementTitle"))
                    if not re.fullmatch(r"[036]\d{5}", code):
                        continue
                    if code in seen_codes or not is_regular_report_title(
                        title, year, str(spec["pattern"])
                    ):
                        continue
                    announcement = _announcement_from_row(
                        row,
                        report_key=str(spec["key"]),
                        report_period=f"{year}-{spec['period']}",
                        bucket=bucket,
                    )
                    if not announcement.announcement_id or not announcement.adjunct_url:
                        continue
                    seen_codes.add(code)
                    candidates.append(announcement)
                    if len(candidates) >= DOCUMENTS_PER_BUCKET:
                        break
                if len(candidates) >= DOCUMENTS_PER_BUCKET:
                    break
                if not payload.get("hasMore"):
                    break
            if len(candidates) != DOCUMENTS_PER_BUCKET:
                raise RuntimeError(
                    f"sample bucket {bucket} has {len(candidates)} eligible reports"
                )
            selected.extend(candidates)
            diagnostics.append(
                {
                    "bucket": bucket,
                    "query_start": start,
                    "query_end": end,
                    "pages_used": pages_used,
                    "rows_seen": rows_seen,
                    "selected": len(candidates),
                }
            )
    return selected, diagnostics


def discover_revision_pair(client: CninfoClient) -> tuple[Announcement, Announcement]:
    spec = REPORT_SPECS[0]
    payload = client.query(
        page=1,
        start="2024-04-01",
        end="2024-05-10",
        category=str(spec["category"]),
        search_key="更正后",
    )
    for row in list(payload.get("announcements") or []):
        corrected_title = clean_title(row.get("announcementTitle"))
        code = str(row.get("secCode") or "")
        org_id = str(row.get("orgId") or "")
        if (
            not re.fullmatch(r"[036]\d{5}", code)
            or "更正" not in corrected_title
            or re.search(str(spec["pattern"]), corrected_title) is None
        ):
            continue
        history = client.query(
            page=1,
            start="2024-01-01",
            end="2024-12-31",
            category=str(spec["category"]),
            stock=f"{code},{org_id}",
        )
        original_row: dict[str, Any] | None = None
        corrected_row: dict[str, Any] | None = None
        for candidate in list(history.get("announcements") or []):
            title = clean_title(candidate.get("announcementTitle"))
            if re.search(str(spec["pattern"]), title) is None:
                continue
            if "更正" in title:
                corrected_row = candidate
            elif is_regular_report_title(title, 2024, str(spec["pattern"])):
                original_row = candidate
        if original_row is None or corrected_row is None:
            continue
        original = _announcement_from_row(
            original_row,
            report_key="q1_revision_original",
            report_period="2024-03-31",
            bucket="revision-pair",
        )
        corrected = _announcement_from_row(
            corrected_row,
            report_key="q1_revision_corrected",
            report_period="2024-03-31",
            bucket="revision-pair",
        )
        if corrected.announcement_time_ms > original.announcement_time_ms:
            return original, corrected
    raise RuntimeError("no deterministic CNInfo original/corrected Q1 pair found")


def _pdfinfo_pages(path: Path) -> int | None:
    result = subprocess.run(
        ["pdfinfo", str(path)], capture_output=True, text=True, check=False
    )
    match = re.search(r"^Pages:\s+(\d+)$", result.stdout, flags=re.MULTILINE)
    return int(match.group(1)) if match else None


def _pdftotext(path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.decode("utf-8", errors="replace")


def inspect_document(client: CninfoClient, announcement: Announcement) -> dict[str, Any]:
    base = {
        "sec_code": announcement.sec_code,
        "sec_name": announcement.sec_name,
        "org_id": announcement.org_id,
        "announcement_id": announcement.announcement_id,
        "title": announcement.title,
        "announcement_time_ms": announcement.announcement_time_ms,
        "announcement_time_utc": datetime.fromtimestamp(
            announcement.announcement_time_ms / 1000, tz=UTC
        ).isoformat(),
        "adjunct_url": announcement.adjunct_url,
        "pdf_url": announcement.pdf_url,
        "report_key": announcement.report_key,
        "report_period": announcement.report_period,
        "bucket": announcement.bucket,
    }
    try:
        body, headers = client.download(announcement.pdf_url)
        valid_pdf = body.startswith(b"%PDF")
        with tempfile.NamedTemporaryFile(suffix=".pdf") as handle:
            handle.write(body)
            handle.flush()
            pages = _pdfinfo_pages(Path(handle.name)) if valid_pdf else None
            text = _pdftotext(Path(handle.name)) if valid_pdf else ""
        compact = compact_text(text)
        parent_profit = extract_parent_profit(text, announcement.report_key)
        basic_eps = extract_number_after_label(text, BASIC_EPS_LABEL)
        return base | headers | {
            "valid_pdf": valid_pdf,
            "pdf_sha256": _sha256_bytes(body),
            "pages": pages,
            "text_chars": len(compact),
            "text_replacement_fraction": (
                text.count("�") / max(len(text), 1)
            ),
            "parent_profit_label": (
                _split_consolidated_row(text) is not None
                or any(
                    _label_context(text, label) is not None
                    for label in (*CONSOLIDATED_PARENT_PROFIT_LABELS, PARENT_PROFIT_LABEL)
                )
            ),
            "parent_profit_raw_value": parent_profit["raw_value"],
            "parent_profit_value": parent_profit["value"],
            "parent_profit_unit": parent_profit["unit"],
            "parent_profit_selected_index": parent_profit["selected_index"],
            "parent_profit_source_label": parent_profit["source_label"],
            "basic_eps_label": BASIC_EPS_LABEL in compact,
            "basic_eps_value": basic_eps,
            "yuan_unit_present": "单位：元" in compact or "单位:元" in compact,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001 - each sample failure is evidence
        return base | {
            "valid_pdf": False,
            "pdf_sha256": None,
            "pages": None,
            "text_chars": 0,
            "text_replacement_fraction": None,
            "parent_profit_label": False,
            "parent_profit_raw_value": None,
            "parent_profit_value": None,
            "parent_profit_unit": None,
            "parent_profit_selected_index": None,
            "parent_profit_source_label": None,
            "basic_eps_label": False,
            "basic_eps_value": None,
            "yuan_unit_present": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def load_current_profit_lookup(path: Path = CURRENT_REPORTS_PATH) -> dict[tuple[str, str], float]:
    if not path.is_file():
        return {}
    frame = pd.read_csv(
        path,
        usecols=["SECUCODE", "REPORTDATE", "UPDATE_DATE", "PARENT_NETPROFIT"],
        low_memory=False,
    )
    frame["sec_code"] = frame["SECUCODE"].astype(str).str.extract(r"(\d{6})")[0]
    frame["report_period"] = pd.to_datetime(frame["REPORTDATE"], errors="coerce").dt.strftime(
        "%Y-%m-%d"
    )
    frame["update_date"] = pd.to_datetime(frame["UPDATE_DATE"], errors="coerce")
    frame["profit"] = pd.to_numeric(frame["PARENT_NETPROFIT"], errors="coerce")
    frame = (
        frame.dropna(subset=["sec_code", "report_period", "profit"])
        .sort_values(["sec_code", "report_period", "update_date"], kind="stable")
        .drop_duplicates(["sec_code", "report_period"], keep="last")
    )
    return {
        (str(row.sec_code), str(row.report_period)): float(row.profit)
        for row in frame.itertuples()
    }


def attach_current_snapshot_comparison(
    documents: list[dict[str, Any]], lookup: dict[tuple[str, str], float]
) -> None:
    for document in documents:
        current = lookup.get((document["sec_code"], document["report_period"]))
        extracted = document.get("parent_profit_value")
        document["current_snapshot_parent_profit"] = current
        if current is None or extracted is None:
            document["current_snapshot_relative_error"] = None
            document["current_snapshot_match_05pct"] = None
            continue
        relative_error = abs(float(extracted) - current) / max(abs(current), 1.0)
        document["current_snapshot_relative_error"] = relative_error
        document["current_snapshot_match_05pct"] = relative_error <= 0.005


def _fraction(documents: list[dict[str, Any]], key: str) -> float:
    return float(sum(bool(item.get(key)) for item in documents) / max(len(documents), 1))


def evaluate_pilot(documents: list[dict[str, Any]]) -> dict[str, Any]:
    revision = [item for item in documents if item["bucket"] == "revision-pair"]
    ordered_revision = sorted(
        revision, key=lambda item: int(item.get("announcement_time_ms") or 0)
    )
    revision_is_semantically_ordered = (
        len(ordered_revision) == 2
        and len({item.get("sec_code") for item in revision}) == 1
        and len({item.get("org_id") for item in revision}) == 1
        and len({item.get("report_period") for item in revision}) == 1
        and int(ordered_revision[0].get("announcement_time_ms") or 0)
        < int(ordered_revision[1].get("announcement_time_ms") or 0)
        and "更正" not in clean_title(ordered_revision[0].get("title"))
        and "更正" in clean_title(ordered_revision[1].get("title"))
    )
    matched = [
        item
        for item in documents
        if item.get("current_snapshot_match_05pct") is not None
    ]
    metrics = {
        "documents": len(documents),
        "valid_pdf_fraction": _fraction(documents, "valid_pdf"),
        "text_layer_fraction": float(
            sum(int(item.get("text_chars") or 0) >= 500 for item in documents)
            / max(len(documents), 1)
        ),
        "parent_profit_label_fraction": _fraction(documents, "parent_profit_label"),
        "parent_profit_value_fraction": float(
            sum(item.get("parent_profit_value") is not None for item in documents)
            / max(len(documents), 1)
        ),
        "basic_eps_label_fraction": _fraction(documents, "basic_eps_label"),
        "basic_eps_value_fraction": float(
            sum(item.get("basic_eps_value") is not None for item in documents)
            / max(len(documents), 1)
        ),
        "current_snapshot_comparable": len(matched),
        "current_snapshot_match_fraction": (
            float(
                sum(bool(item["current_snapshot_match_05pct"]) for item in matched)
                / len(matched)
            )
            if matched
            else None
        ),
        "revision_pair_documents": len(revision),
        "revision_pair_distinct_ids": len({item["announcement_id"] for item in revision}),
        "revision_pair_distinct_hashes": len(
            {item["pdf_sha256"] for item in revision if item.get("pdf_sha256")}
        ),
        "revision_pair_distinct_sec_codes": len(
            {item.get("sec_code") for item in revision}
        ),
        "revision_pair_distinct_org_ids": len(
            {item.get("org_id") for item in revision}
        ),
        "revision_pair_distinct_report_periods": len(
            {item.get("report_period") for item in revision}
        ),
        "revision_pair_semantically_ordered": revision_is_semantically_ordered,
    }
    archive_acquisition_gates = {
        "sample_exactly_50_documents": len(documents) == SAMPLE_TARGET,
        "valid_pdf_ge_95pct": metrics["valid_pdf_fraction"] >= 0.95,
        "text_layer_ge_90pct": metrics["text_layer_fraction"] >= 0.90,
        "parent_profit_label_ge_90pct": metrics["parent_profit_label_fraction"] >= 0.90,
        "parent_profit_value_ge_80pct": metrics["parent_profit_value_fraction"] >= 0.80,
        "basic_eps_value_ge_80pct": metrics["basic_eps_value_fraction"] >= 0.80,
        "revision_chain_is_ordered_original_and_correction": (
            metrics["revision_pair_documents"] == 2
            and metrics["revision_pair_distinct_ids"] == 2
            and metrics["revision_pair_distinct_hashes"] == 2
            and metrics["revision_pair_semantically_ordered"]
        ),
    }
    current_match_fraction = metrics["current_snapshot_match_fraction"]
    structured_extraction_qa_gates = {
        "current_snapshot_comparable_ge_30": (
            metrics["current_snapshot_comparable"] >= 30
        ),
        "current_snapshot_match_ge_95pct": (
            current_match_fraction is not None and current_match_fraction >= 0.95
        ),
    }
    archive_acquisition_pass = all(archive_acquisition_gates.values())
    structured_extraction_qa_pass = all(structured_extraction_qa_gates.values())
    pilot_pass = archive_acquisition_pass and structured_extraction_qa_pass
    if not archive_acquisition_pass:
        pilot_verdict = "AS_FILED_ARCHIVE_PILOT_NO_GO"
    elif not structured_extraction_qa_pass:
        pilot_verdict = "ARCHIVE_ACQUISITION_GO_EXTRACTION_QA_NO_GO"
    else:
        pilot_verdict = "AS_FILED_ARCHIVE_PILOT_GO"
    return {
        "metrics": metrics,
        "archive_acquisition_gates": archive_acquisition_gates,
        "structured_extraction_qa_gates": structured_extraction_qa_gates,
        "archive_acquisition_pass": archive_acquisition_pass,
        "structured_extraction_qa_pass": structured_extraction_qa_pass,
        "pilot_pass": pilot_pass,
        "pilot_verdict": pilot_verdict,
        "ep_signal_data_ready": False,
        "pead_signal_data_ready": False,
        "cny_2_1m_portfolio_backtest_allowed": False,
    }


def run(*, workers: int = 6) -> dict[str, Any]:
    client = CninfoClient()
    regular, bucket_diagnostics = select_regular_sample(client)
    revision_original, revision_corrected = discover_revision_pair(client)
    sample = regular + [revision_original, revision_corrected]
    if len(sample) != SAMPLE_TARGET:
        raise RuntimeError(f"unexpected sample size: {len(sample)}")

    documents: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(inspect_document, CninfoClient(), announcement): announcement
            for announcement in sample
        }
        for future in as_completed(futures):
            documents.append(future.result())
    documents.sort(key=lambda item: (item["bucket"], item["announcement_id"]))
    attach_current_snapshot_comparison(documents, load_current_profit_lookup())
    evaluation = evaluate_pilot(documents)

    return _jsonable(
        {
            "study": "A-share CNInfo as-filed archive feasibility pilot",
            "analysis_date": "2026-07-12",
            "capital_cny": 2_100_000,
            "protocol": {
                "sample_years": list(SAMPLE_YEARS),
                "regular_report_types": [spec["key"] for spec in REPORT_SPECS],
                "regular_documents_per_year_type": DOCUMENTS_PER_BUCKET,
                "regular_documents": len(regular),
                "revision_documents": 2,
                "sample_target": SAMPLE_TARGET,
                "selection": (
                    "first four eligible SH/SZ full reports in CNInfo result order for "
                    "each frozen year/report bucket; summaries, English, revisions, "
                    "supplements and notices excluded; plus first discoverable 2024 Q1 "
                    "original/corrected pair"
                ),
                "purpose": (
                    "data foundation only; no signal return or portfolio computation"
                ),
                "public_sources": {
                    "cninfo_search": QUERY_URL,
                    "cninfo_detail": DETAIL_URL,
                    "cninfo_static": STATIC_BASE,
                    "cninfo_commercial_api": "https://webapi.cninfo.com.cn/#/apiDoc",
                },
            },
            "bucket_diagnostics": bucket_diagnostics,
            "documents": documents,
            "evaluation": evaluation,
            "input_evidence": {
                "current_structured_snapshot": str(
                    CURRENT_REPORTS_PATH.relative_to(REPO_ROOT)
                ),
                "current_structured_snapshot_available": CURRENT_REPORTS_PATH.is_file(),
                "current_structured_snapshot_sha256": (
                    _sha256_file(CURRENT_REPORTS_PATH)
                    if CURRENT_REPORTS_PATH.is_file()
                    else None
                ),
                "runner_sha256": _sha256_file(Path(__file__)),
                "test_sha256": _sha256_file(TEST_PATH) if TEST_PATH.is_file() else None,
                "pdftotext_version": subprocess.run(
                    ["pdftotext", "-v"], capture_output=True, text=True, check=False
                ).stderr.strip(),
            },
            "strategy_readiness": {
                "ep": {
                    "verdict": "DATA_NO_GO",
                    "missing": [
                        "full-market versioned as-filed archive",
                        "PIT total shares and total market capitalization",
                        "PIT industry and execution ledger",
                    ],
                },
                "pead": {
                    "verdict": "DATA_NO_GO",
                    "missing": [
                        "full forecast/express/report/correction event chain",
                        "historical expectations or PIT seasonal-SUE vintages",
                        "precise event execution and historical ST/limit ledger",
                    ],
                },
            },
            "interpretation_limits": [
                "A 50-document pilot cannot certify full-market extraction coverage.",
                "PDF text extraction is not a substitute for a contracted XBRL vintage feed.",
                "The public website endpoints have no documented SLA or stable API contract.",
                "Current-snapshot agreement validates parsing, not historical as-filed semantics.",
                "No product, broker, paper account, or production strategy was touched.",
            ],
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    payload = run(workers=args.workers)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["evaluation"], ensure_ascii=True, sort_keys=True, indent=2))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
