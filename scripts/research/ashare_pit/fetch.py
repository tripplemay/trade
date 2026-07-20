"""B109 F002 — Tushare 分页拉取与**静默截断**防护。

★★ 本模块因一个实测发现而存在：**Tushare 单次调用会静默截断，且不报错、不置任何标志位。**

2026-07-20 实测（`.venv/bin/python`，真实 API）：

============  ==============  ==============  ====================================
接口           单次返回          分页全量          漏掉
============  ==============  ==============  ====================================
`income_vip`  9,000 行（2022FY） 10,093 行        1,093 行（10.8%），311 只证券
`namechange`  10,000 行         11,414 行        1,414 行（12.4%），全为最早期记录
============  ==============  ==============  ====================================

**截断不是均匀的**，这是最危险的部分。2022 年报单次调用漏掉的行里：

- ``update_flag=0``：4,206 → 3,419（**漏 18.7%**）
- ``update_flag=1``：5,887 → 5,581（漏 5.2%）

即被砍掉的恰恰富集了 **vintage 记录**——而 `flag=0` 保留率、修订检出率正是靠这些行算的。
一个只做单次调用的探针，会系统性低估自己能看见的历史版本数，
却因为「返回了一个很像全量的整数」而毫无察觉。

因此本模块的立场是：**永远分页，并且把触顶当作错误信号而非正常返回。**
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

# 观测到的单次上限。**不作为分页依据**（上限可能随接口/权限变化），
# 只用于 :func:`looks_truncated` 的告警——真正的判据是「短页才是最后一页」。
KNOWN_ROW_CAPS: tuple[int, ...] = (1000, 2000, 3000, 5000, 6000, 8000, 9000, 10000)

DEFAULT_PAGE_SIZE = 5000
_THROTTLE_SECONDS = 0.6
_MAX_ATTEMPTS = 3
_MAX_PAGES = 200

# 重试退避基数。单独提出来是为了让单测把它置零——否则一条失败路径的用例
# 要空等 9 秒，慢到没人愿意在本地跑全量。
RETRY_BACKOFF_SECONDS = 3.0


@dataclass
class FetchReport:
    """一次分页拉取的可审计记录。**页数与行数必须能被复核**，不得只交一个 DataFrame。"""

    endpoint: str
    params: dict[str, Any]
    pages: int = 0
    rows: int = 0
    truncation_suspected: bool = False
    failures: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "params": self.params,
            "pages": self.pages,
            "rows": self.rows,
            "truncation_suspected": self.truncation_suspected,
            "failures": list(self.failures),
        }


def looks_truncated(row_count: int) -> bool:
    """行数是否**恰好**落在已知上限上——单次调用最可疑的信号。

    真实数据几乎不会恰好停在 9000 或 10000。见模块 docstring 的实测。
    """
    return row_count in KNOWN_ROW_CAPS


def fetch_paged(
    fn: Callable[..., Any],
    *,
    endpoint: str,
    page_size: int = DEFAULT_PAGE_SIZE,
    throttle: float = _THROTTLE_SECONDS,
    **params: Any,
) -> tuple[pd.DataFrame, FetchReport]:
    """分页拉全一个 Tushare 接口。

    终止条件是**短页**（``len(page) < page_size``），不是任何预设的总数——
    这正是单次调用踩坑的地方：它拿到一个满页就当成了全量。

    拉取失败经有界重试后记入 ``report.failures`` 并**中止分页**，
    不返回半截数据冒充全量（H4：缺口必须可见）。
    """
    report = FetchReport(endpoint=endpoint, params=dict(params))
    chunks: list[pd.DataFrame] = []
    offset = 0

    for _ in range(_MAX_PAGES):
        page = _call_with_retry(fn, offset=offset, limit=page_size, **params)
        if page is None:
            report.failures.append(f"{endpoint}:offset={offset}")
            break
        if page.empty:
            break

        chunks.append(page)
        report.pages += 1
        report.rows += len(page)
        offset += len(page)

        if len(page) < page_size:
            break
        time.sleep(throttle)
    else:
        # 页数触到上限 = 可能还有更多数据没拉到，必须显式暴露
        report.failures.append(f"{endpoint}:hit_max_pages={_MAX_PAGES}")

    if not chunks:
        return pd.DataFrame(), report

    frame = pd.concat(chunks, ignore_index=True)
    # 分页边界上供应商可能重复返回同一行；去重后行数变化本身也值得记录
    deduped = frame.drop_duplicates().reset_index(drop=True)
    report.rows = len(deduped)
    return deduped, report


def fetch_single_checked(
    fn: Callable[..., Any],
    *,
    endpoint: str,
    **params: Any,
) -> tuple[pd.DataFrame, FetchReport]:
    """单次拉取 + 触顶检查。**只用于确信不会分页的小接口**（如 `stock_basic`）。

    返回行数落在已知上限上时置 ``truncation_suspected``——调用方必须改走
    :func:`fetch_paged`，而不是把这个整数当成全量。
    """
    report = FetchReport(endpoint=endpoint, params=dict(params))
    frame = _call_with_retry(fn, **params)
    if frame is None:
        report.failures.append(endpoint)
        return pd.DataFrame(), report

    report.pages = 1
    report.rows = len(frame)
    report.truncation_suspected = looks_truncated(len(frame))
    return frame, report


def _call_with_retry(fn: Callable[..., Any], **kwargs: Any) -> pd.DataFrame | None:
    """有界重试。最终失败返回 ``None``，由调用方显式记录——不静默跳过（H4）。"""
    for attempt in range(_MAX_ATTEMPTS):
        try:
            return fn(**kwargs)
        except Exception:  # noqa: BLE001 - 有界重试后以 None 显式暴露
            if attempt + 1 < _MAX_ATTEMPTS:
                time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
    return None
