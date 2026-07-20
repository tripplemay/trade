"""B109 F001 — vintage 探针纯逻辑单测（离线，不联网）。

只测判定逻辑：修订检出、检出机制拆分、as-of 可重建性判据。
网络路径（`fetch_period` / `run`）不在此覆盖——★按 B108 E01 的教训，
无法在单测中执行的路径必须显式标注为未验证，不得用「代码看起来对」冒充已验证。
本探针的联网路径已由实际运行验证（见 `docs/audits/B109-F001-vintage-probe-2026-07-20.md` §6）。
"""

from __future__ import annotations

import pandas as pd

from scripts.research.ashare_pit.vintage_probe import (
    measure_period,
    measure_reconstructability,
)


def _rows(records: list[tuple[str, str, str, str, float]]) -> pd.DataFrame:
    """(ts_code, ann_date, f_ann_date, update_flag, n_income_attr_p)"""
    return pd.DataFrame(
        [
            {
                "ts_code": code,
                "ann_date": ann,
                "f_ann_date": f_ann,
                "report_type": "1",
                "update_flag": flag,
                "n_income_attr_p": value,
            }
            for code, ann, f_ann, flag, value in records
        ]
    )


def test_identical_values_across_flags_is_not_a_revision() -> None:
    """同键两行但数值相同 = 重复行，不是修订。

    这是三问探针的第一个发现：600519 的 flag=0/1 两行数值完全一致。
    把重复行当修订会把修订率抬高一个量级。
    """
    df = _rows(
        [
            ("600519.SH", "20230331", "20230331", "0", 100.0),
            ("600519.SH", "20230331", "20230331", "1", 100.0),
        ]
    )
    assert measure_period(df, "20221231")["revised"] == 0


def test_flag_pair_with_different_values_is_detected() -> None:
    df = _rows(
        [
            ("000547.SZ", "20230422", "20230422", "0", 34_679_532.18),
            ("000547.SZ", "20230422", "20250121", "1", 32_973_069.04),
        ]
    )
    measured = measure_period(df, "20221231")
    assert measured["revised"] == 1
    assert measured["detected_by_flag_pair"] == 1
    assert measured["detected_by_multi_flag1"] == 0


def test_multiple_flag1_rows_are_also_detected() -> None:
    """★2023/2024 的主导检出机制：flag=0 缺失时靠多条 flag=1 带不同 f_ann_date。

    缺了这条，低 flag=0 保留期的修订会被整体漏掉。
    """
    df = _rows(
        [
            ("001278.SZ", "20230210", "20230210", "1", 112_397_678.99),
            ("001278.SZ", "20230426", "20230426", "1", 110_543_710.04),
        ]
    )
    measured = measure_period(df, "20221231")
    assert measured["revised"] == 1
    assert measured["detected_by_flag_pair"] == 0
    assert measured["detected_by_multi_flag1"] == 1


def test_flag0_retention_and_group_rates() -> None:
    df = _rows(
        [
            ("A.SZ", "20230422", "20230422", "0", 10.0),
            ("A.SZ", "20230422", "20250121", "1", 11.0),  # 有 flag=0 且被修订
            ("B.SZ", "20230422", "20230422", "1", 20.0),  # 无 flag=0，未修订
        ]
    )
    measured = measure_period(df, "20221231")
    assert measured["stocks"] == 2
    assert measured["flag0_retention"] == 0.5
    assert measured["rate_within_flag0_group"] == 1.0
    assert measured["rate_without_flag0_group"] == 0.0


def test_reconstructable_when_values_map_one_to_one_to_f_ann_date() -> None:
    df = _rows(
        [
            ("A.SZ", "20230422", "20230422", "0", 10.0),
            ("A.SZ", "20230422", "20250121", "1", 11.0),
        ]
    )
    assert measure_reconstructability(df)["as_of_reconstructable"] == 1


def test_not_reconstructable_when_values_share_one_f_ann_date() -> None:
    """★多个数值共用同一 f_ann_date 时无法分辨先后，必须判为不可重建。

    这类占已知修订的 1.0%，F002 须对它 fail closed（FACT_VERSION_AMBIGUOUS），
    禁止按行序或抓取顺序任选一条（上游禁令 #13）。
    """
    df = _rows(
        [
            ("A.SZ", "20230422", "20230422", "0", 10.0),
            ("A.SZ", "20230422", "20230422", "1", 11.0),
        ]
    )
    kinds = measure_reconstructability(df)
    assert kinds["as_of_reconstructable"] == 0
    assert kinds["not_reconstructable_same_f_ann_date"] == 1


def test_unrevised_stock_contributes_nothing_to_reconstructability() -> None:
    df = _rows([("A.SZ", "20230422", "20230422", "1", 10.0)])
    assert sum(measure_reconstructability(df).values()) == 0
