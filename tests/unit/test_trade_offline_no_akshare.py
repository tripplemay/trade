"""B062 F002 — the ``trade`` engine must stay offline: no akshare / baostock.

akshare / baostock are the workbench ``data_refresh`` job's tools: they fetch
A-share / HK prices and write them into the unified prices CSV. ``trade`` — the
deterministic, offline strategy engine — only **reads** that CSV; it must never
import a network data library (B061 F003 / B062 §3 offline edge). This AST guard
locks the invariant so a future edit can't quietly couple the engine to akshare.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

_TRADE_ROOT = Path(__file__).resolve().parents[2] / "trade"
_FORBIDDEN: frozenset[str] = frozenset({"akshare", "baostock"})


def _forbidden_imports(path: Path) -> Iterator[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in _FORBIDDEN:
                    yield alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level == 0 and module.split(".")[0] in _FORBIDDEN:
                yield module


def test_trade_engine_imports_no_akshare_or_baostock() -> None:
    offenders: list[tuple[str, str]] = []
    for path in sorted(_TRADE_ROOT.rglob("*.py")):
        for module in _forbidden_imports(path):
            offenders.append((str(path.relative_to(_TRADE_ROOT.parent)), module))
    assert offenders == [], (
        "trade/ must stay offline — it reads the unified CSV, never imports a "
        f"network data library. Forbidden import(s) found: {offenders}"
    )
