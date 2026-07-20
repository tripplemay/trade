"""F003 复验 — resolver 语义离线回归（D1 为纯 docstring 变更，确认零行为改动）。"""

from decimal import Decimal

from scripts.research.ashare_pit.codes import FactStatus, FactVersion
from scripts.research.ashare_pit.resolver import resolve_as_of

v1 = FactVersion("T.SZ", "20211231", "20220330", "20220330", "0", Decimal("100"))
v2 = FactVersion("T.SZ", "20211231", "20230415", "20220330", "1", Decimal("250"))
clash = FactVersion("T.SZ", "20211231", "20220330", "20220330", "1", Decimal("999"))

checks = [
    ("修订前形成日返回首版", resolve_as_of([v1, v2], "20220701").value == Decimal("100")),
    ("修订后形成日返回修正版", resolve_as_of([v1, v2], "20230801").value == Decimal("250")),
    (
        "形成日早于首版 -> NOT_YET_PUBLISHED",
        resolve_as_of([v1, v2], "20220101").status is FactStatus.NOT_YET_PUBLISHED,
    ),
    ("旧形成日正确置 superseded_later", resolve_as_of([v1, v2], "20220701").superseded_later),
    (
        "同 f_ann_date 矛盾值 -> fail closed",
        resolve_as_of([v1, clash], "20220701").status is FactStatus.FACT_VERSION_AMBIGUOUS,
    ),
    (
        "注入未来修订后旧形成日取值不变",
        resolve_as_of([v1], "20220701").value == resolve_as_of([v1, v2], "20220701").value,
    ),
]

for name, ok in checks:
    print(f"  {'OK  ' if ok else 'FAIL'} {name}")
print("全部通过" if all(ok for _, ok in checks) else "★有回归")
