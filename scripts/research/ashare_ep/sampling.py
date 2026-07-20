"""B108 F002 — 确定性分层抽样（纯逻辑，无网络）。

取代 pilot 里 ``select_regular_sample`` 的「取巨潮返回顺序前 4 个」。原做法有两个
致命问题：巨潮的返回顺序**随时间变化**（样本不可复现），且顺序**非随机**（系统性
偏向特定公司，holdout 会带隐性选择偏差）。

确定性的边界要说清楚：**给定同一份候选池**，同 seed 同参数必然产出同一份样本。
候选池本身依赖巨潮当时返回什么，这一层无法由本模块保证——所以 manifest 里冻结的是
选中项，provenance 里另记查询参数与抓取时间，两者分开。
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

# 板块由证券代码前缀判定。002/003 原为中小板，2021 年并入深交所主板，
# 因此这里归入「深主板」——分层的目的是覆盖不同披露模板，合并后模板已统一。
_BOARD_PREFIXES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("科创板", ("688", "689")),
    ("沪主板", ("600", "601", "603", "605")),
    ("创业板", ("300", "301")),
    ("深主板", ("000", "001", "002", "003")),
)

REPORT_TYPES: tuple[str, ...] = ("Q1", "H1", "Q3", "FY")


@dataclass(frozen=True)
class Candidate:
    """一份候选公告。字段全部来自巨潮检索结果，本模块不发起任何网络请求。"""

    announcement_id: str
    sec_code: str
    title: str
    year: int
    report_type: str
    url: str

    @property
    def board(self) -> str:
        return classify_board(self.sec_code)

    @property
    def report_period(self) -> str:
        return f"{self.year}-{self.report_type}"

    @property
    def stratum(self) -> tuple[int, str, str]:
        return (self.year, self.board, self.report_type)


def classify_board(sec_code: str) -> str:
    """按代码前缀判板块。无法归类的返回 ``UNKNOWN``（不猜）。"""
    for board, prefixes in _BOARD_PREFIXES:
        if sec_code.startswith(prefixes):
            return board
    return "UNKNOWN"


def _derive_seed(seed: int, stratum: tuple[int, str, str]) -> int:
    """从主 seed 和层键派生子 seed。

    ★不能用内置 ``hash()``：CPython 对 str 的 hash 每进程加盐，跨运行不稳定，
    会让「同 seed 复现」这条核心保证在第二次运行时静默失效。
    """
    material = f"{seed}:{stratum[0]}:{stratum[1]}:{stratum[2]}".encode()
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


def group_by_stratum(
    candidates: list[Candidate],
) -> dict[tuple[int, str, str], list[Candidate]]:
    grouped: dict[tuple[int, str, str], list[Candidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.stratum, []).append(candidate)
    return grouped


def select_stratified(
    candidates: list[Candidate],
    *,
    quota_per_stratum: int,
    seed: int,
    exclude_ids: frozenset[str] = frozenset(),
) -> list[Candidate]:
    """按层抽样。返回结果按 ``(层键, announcement_id)`` 排序，保证字节级可复现。

    每层用独立派生的子 seed，因此增删某一层不会扰动其它层的抽样结果。
    """
    pool = [item for item in candidates if item.announcement_id not in exclude_ids]
    selected: list[Candidate] = []

    for stratum, members in sorted(group_by_stratum(pool).items()):
        # 先做规范排序再抽样——否则候选池的到达顺序会渗进结果，确定性就假了
        ordered = sorted(members, key=lambda item: item.announcement_id)
        rng = random.Random(_derive_seed(seed, stratum))
        take = min(quota_per_stratum, len(ordered))
        selected.extend(rng.sample(ordered, take))

    return sorted(selected, key=lambda item: (item.stratum, item.announcement_id))


def coverage_report(
    candidates: list[Candidate],
    selected: list[Candidate],
    *,
    quota_per_stratum: int,
) -> list[dict[str, object]]:
    """逐层报告候选数与实际抽中数。

    配额没满必须显式暴露——静默少抽会让下游把「这一层不好抽」误读成「这一层没问题」。
    """
    available = group_by_stratum(candidates)
    taken = group_by_stratum(selected)
    rows: list[dict[str, object]] = []
    for stratum in sorted(set(available) | set(taken)):
        year, board, report_type = stratum
        got = len(taken.get(stratum, []))
        rows.append(
            {
                "year": year,
                "board": board,
                "report_type": report_type,
                "available": len(available.get(stratum, [])),
                "selected": got,
                "quota": quota_per_stratum,
                "quota_met": got >= quota_per_stratum,
            }
        )
    return rows
