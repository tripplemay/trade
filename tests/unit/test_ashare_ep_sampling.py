"""B108 F002 — 确定性分层抽样单测。

最关键的一条是**跨进程**确定性：CPython 对 str 的 ``hash()`` 每进程加盐，如果实现里
不慎用了它，同进程内测试会全绿、换一次运行样本就变了，而且不会有任何报错。
因此这里用 ``PYTHONHASHSEED`` 不同的子进程跑两次 CLI，比对产物字节。
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.research.ashare_ep.manifest import (
    build_manifest,
    load_excluded_ids,
    manifest_sha256,
)
from scripts.research.ashare_ep.sample_cli import main
from scripts.research.ashare_ep.sampling import (
    Candidate,
    classify_board,
    coverage_report,
    select_stratified,
)

_YEARS = (2015, 2023)
_TYPES = ("Q1", "FY")
_BOARD_CODES = {
    "沪主板": "600519",
    "深主板": "000001",
    "创业板": "300750",
    "科创板": "688981",
}


def _pool() -> list[Candidate]:
    """合成候选池：2 年 × 4 板块 × 2 报告类型 × 每层 6 个候选。"""
    candidates: list[Candidate] = []
    for year in _YEARS:
        for report_type in _TYPES:
            for board, base in _BOARD_CODES.items():
                for index in range(6):
                    sec_code = f"{base[:3]}{int(base[3:]) + index:03d}"
                    candidates.append(
                        Candidate(
                            announcement_id=f"{year}{report_type}{board}{index:02d}",
                            sec_code=sec_code,
                            title=f"{year}年报告",
                            year=year,
                            report_type=report_type,
                            url=f"https://example.invalid/{sec_code}.pdf",
                        )
                    )
    return candidates


# --- 板块判定 ---


@pytest.mark.parametrize(
    ("sec_code", "expected"),
    [
        ("600519", "沪主板"),
        ("601398", "沪主板"),
        ("603259", "沪主板"),
        ("688981", "科创板"),
        ("000001", "深主板"),
        ("002594", "深主板"),  # 原中小板，2021 并入深主板
        ("300750", "创业板"),
        ("301029", "创业板"),
        ("900901", "UNKNOWN"),  # B 股不在本项目宇宙内，不猜
    ],
)
def test_board_classification(sec_code: str, expected: str) -> None:
    assert classify_board(sec_code) == expected


# --- 分层与配额 ---


def test_quota_is_applied_per_stratum() -> None:
    selected = select_stratified(_pool(), quota_per_stratum=2, seed=7)
    strata = {item.stratum for item in selected}
    assert len(strata) == len(_YEARS) * len(_TYPES) * len(_BOARD_CODES)
    for stratum in strata:
        assert len([item for item in selected if item.stratum == stratum]) == 2


def test_quota_shortfall_is_reported_not_silently_swallowed() -> None:
    """抽不满必须显式暴露——静默少抽会被下游读成『这一层没问题』。"""
    pool = _pool()[:3]
    selected = select_stratified(pool, quota_per_stratum=5, seed=7)
    rows = coverage_report(pool, selected, quota_per_stratum=5)
    assert any(row["quota_met"] is False for row in rows)
    assert all(row["selected"] <= row["available"] for row in rows)


def test_selection_is_sorted_canonically() -> None:
    selected = select_stratified(_pool(), quota_per_stratum=2, seed=7)
    keys = [(item.stratum, item.announcement_id) for item in selected]
    assert keys == sorted(keys)


# --- 确定性 ---


def test_same_seed_same_pool_gives_identical_manifest() -> None:
    pool = _pool()
    first = build_manifest(
        select_stratified(pool, quota_per_stratum=2, seed=42),
        seed=42,
        quota_per_stratum=2,
        years=_YEARS,
        report_types=_TYPES,
    )
    second = build_manifest(
        select_stratified(pool, quota_per_stratum=2, seed=42),
        seed=42,
        quota_per_stratum=2,
        years=_YEARS,
        report_types=_TYPES,
    )
    assert manifest_sha256(first) == manifest_sha256(second)


def test_different_seed_gives_different_selection() -> None:
    pool = _pool()
    left = select_stratified(pool, quota_per_stratum=2, seed=1)
    right = select_stratified(pool, quota_per_stratum=2, seed=2)
    assert [item.announcement_id for item in left] != [item.announcement_id for item in right]


def test_adding_a_stratum_does_not_disturb_other_strata() -> None:
    """每层用独立派生子 seed，所以增删一层不会扰动其它层。"""
    pool = _pool()
    subset = [item for item in pool if item.year == 2015]
    full_2015 = [
        item.announcement_id
        for item in select_stratified(pool, quota_per_stratum=2, seed=9)
        if item.year == 2015
    ]
    subset_2015 = [
        item.announcement_id for item in select_stratified(subset, quota_per_stratum=2, seed=9)
    ]
    assert full_2015 == subset_2015


# --- 排除清单 ---


def test_excluded_ids_never_appear_in_selection() -> None:
    pool = _pool()
    excluded = frozenset(item.announcement_id for item in pool[:20])
    selected = select_stratified(pool, quota_per_stratum=2, seed=7, exclude_ids=excluded)
    assert not {item.announcement_id for item in selected} & excluded


def test_load_excluded_ids_accepts_pilot_report_format(tmp_path: Path) -> None:
    """已烧掉的 50 份存在 pilot 报告的 documents[] 里，必须能被解析出来。"""
    path = tmp_path / "pilot.json"
    path.write_text(
        json.dumps({"documents": [{"announcement_id": "1219822617"}, {"announcement_id": "x"}]}),
        encoding="utf-8",
    )
    assert load_excluded_ids(path) == frozenset({"1219822617", "x"})


def test_load_excluded_ids_refuses_empty_exclusion(tmp_path: Path) -> None:
    """空排除清单会让已烧样本重新进 holdout——必须拒绝，不能默默放行。"""
    path = tmp_path / "empty.json"
    path.write_text(json.dumps({"documents": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="announcement_id"):
        load_excluded_ids(path)


# --- CLI 端到端（离线） ---


def _write_pool_fixture(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "announcement_id": item.announcement_id,
                        "sec_code": item.sec_code,
                        "title": item.title,
                        "year": item.year,
                        "report_type": item.report_type,
                        "url": item.url,
                    }
                    for item in _pool()
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_cli_offline_run_writes_manifest(tmp_path: Path) -> None:
    pool_path = tmp_path / "pool.json"
    _write_pool_fixture(pool_path)
    out = tmp_path / "manifest.json"

    argv = ["--seed", "5", "--quota", "2", "--candidates-json", str(pool_path), "--out", str(out)]
    assert main(argv) == 0

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["count"] == len(payload["items"])
    assert payload["selection_params"]["seed"] == 5
    # 只产 manifest：产物里不得出现任何抽取出来的数值
    assert "parent_profit" not in out.read_text(encoding="utf-8")


def test_cli_is_deterministic_across_processes(tmp_path: Path) -> None:
    """★核心保证：换一个进程（且 PYTHONHASHSEED 不同）必须产出逐字节相同的 manifest。

    如果实现里误用了内置 ``hash()``，同进程测试会全绿而这条会红——这正是它存在的理由。
    """
    pool_path = tmp_path / "pool.json"
    _write_pool_fixture(pool_path)

    digests: list[str] = []
    for hash_seed in ("0", "12345"):
        out = tmp_path / f"manifest-{hash_seed}.json"
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.research.ashare_ep.sample_cli",
                "--seed",
                "20260720",
                "--quota",
                "3",
                "--candidates-json",
                str(pool_path),
                "--out",
                str(out),
            ],
            cwd=Path(__file__).resolve().parents[2],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        digests.append(hashlib.sha256(out.read_bytes()).hexdigest())

    assert digests[0] == digests[1], "跨进程 manifest 不一致——检查是否用了加盐的内置 hash()"
