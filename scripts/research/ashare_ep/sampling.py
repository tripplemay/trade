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

UNKNOWN_BOARD = "UNKNOWN"

# 参与分层的板块。UNKNOWN（B 股 200xxx/900xxx、北交所）不在本项目宇宙内，
# 见上游报告 §2.1「暂不纳入：北京证券交易所、B 股、基金、ETF、债券、优先股、存托凭证」。
TARGET_BOARDS: tuple[str, ...] = tuple(board for board, _ in _BOARD_PREFIXES)


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
    return UNKNOWN_BOARD


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

    ★E10 修复：``UNKNOWN`` 板块不参与抽样。B 股（``200xxx``/``900xxx``）与北交所
    不在本项目宇宙内（上游报告 §2.1「暂不纳入」），原实现却让 ``UNKNOWN`` 作为
    第 5 个板块照常占配额，等于把宇宙外的证券塞进 holdout。
    """
    pool = [
        item
        for item in candidates
        if item.announcement_id not in exclude_ids and item.board != UNKNOWN_BOARD
    ]
    selected: list[Candidate] = []

    for stratum, members in sorted(group_by_stratum(pool).items()):
        # 先做规范排序再抽样——否则候选池的到达顺序会渗进结果，确定性就假了
        ordered = sorted(members, key=lambda item: item.announcement_id)
        rng = random.Random(_derive_seed(seed, stratum))
        take = min(quota_per_stratum, len(ordered))
        selected.extend(rng.sample(ordered, take))

    return sorted(selected, key=lambda item: (item.stratum, item.announcement_id))


def expected_strata(
    years: tuple[int, ...],
    report_types: tuple[str, ...] = REPORT_TYPES,
    boards: tuple[str, ...] = TARGET_BOARDS,
) -> set[tuple[int, str, str]]:
    """按参数枚举**应当存在**的全部层，与候选池里实际有什么无关。"""
    return {
        (year, board, report_type)
        for year in years
        for board in boards
        for report_type in report_types
    }


def coverage_report(
    candidates: list[Candidate],
    selected: list[Candidate],
    *,
    quota_per_stratum: int,
    expected: set[tuple[int, str, str]] | None = None,
) -> list[dict[str, object]]:
    """逐层报告候选数与实际抽中数。

    配额没满必须显式暴露——静默少抽会让下游把「这一层不好抽」误读成「这一层没问题」。

    ★E08 修复：必须传 ``expected``，否则**候选数为 0 的整层根本不会出现在报告里**。
    原实现只遍历候选池里存在的层，于是「这一层一份都没抓到」——恰恰是最严重的缺口——
    表现为报告里安静地少一行，no-silent-caps 对最该保护的情形失效。
    """
    available = group_by_stratum(candidates)
    taken = group_by_stratum(selected)
    strata = set(available) | set(taken) | (expected or set())
    rows: list[dict[str, object]] = []
    for stratum in sorted(strata):
        year, board, report_type = stratum
        got = len(taken.get(stratum, []))
        # ★N05 修复：UNKNOWN 是 E10 **故意**排除的宇宙外证券（B股/北交所），
        # 报成「未达配额」会把一个有意的设计决策伪装成缺陷，淹没真正的缺口。
        out_of_universe = board == UNKNOWN_BOARD
        rows.append(
            {
                "year": year,
                "board": board,
                "report_type": report_type,
                "available": len(available.get(stratum, [])),
                "selected": got,
                "quota": 0 if out_of_universe else quota_per_stratum,
                "quota_met": True if out_of_universe else got >= quota_per_stratum,
                "excluded_from_universe": out_of_universe,
            }
        )
    return rows
