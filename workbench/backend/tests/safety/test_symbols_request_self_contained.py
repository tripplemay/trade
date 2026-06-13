"""B059 F001 — symbol-lookup layer §12.10.2 self-containment.

The "look up any ticker" surface fetches free yfinance EOD data on the
**request path** (yfinance_loader does not import ``trade``, confirmed B059
planning), behind a cache + rate-limit guard. Unlike recommendations /
backtests there is no async worker here — so EVERY symbols module must stay
clean of ``trade``: a regression that imported the heavy scoring stack from
the request path would work in CI (trade is installed) but couple the lookup
read path to the engine — exactly the §12.10.2 class this guard prevents.

There is no allowlisted importer for this feature (no module may import
``trade``); the positive side is asserted by the loader reuse staying on the
free yfinance path.
"""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = BACKEND_ROOT / "workbench_api"
SYMBOLS = PACKAGE_ROOT / "symbols"

REQUEST_PATH_MODULES = (
    PACKAGE_ROOT / "routes" / "symbols.py",
    SYMBOLS / "__init__.py",
    SYMBOLS / "provider.py",
    SYMBOLS / "yfinance_provider.py",
    SYMBOLS / "service.py",
    SYMBOLS / "stats.py",
    SYMBOLS / "fundamentals.py",
)


def _imports_trade(py_path: Path) -> bool:
    """True if the module imports the top-level ``trade`` package (absolute)."""

    tree = ast.parse(py_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "trade" or alias.name.startswith("trade."):
                    return True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level == 0 and (module == "trade" or module.startswith("trade.")):
                return True
    return False


def test_symbols_request_path_does_not_import_trade() -> None:
    offenders = sorted(
        str(path.relative_to(BACKEND_ROOT))
        for path in REQUEST_PATH_MODULES
        if path.is_file() and _imports_trade(path)
    )
    assert not offenders, (
        "§12.10.2 violated: the symbol-lookup request path imports the trade "
        f"package {offenders}. The lookup surface must serve from the free "
        "yfinance EOD feed + the isolated symbol_price_cache table only — never "
        "import trade on the request path (there is no async worker here)."
    )


def test_every_symbols_module_is_scanned() -> None:
    """Pin coverage: every shipped ``symbols/`` module must be listed in
    REQUEST_PATH_MODULES so a future module can't slip in unscanned."""

    on_disk = {
        path.name for path in SYMBOLS.glob("*.py") if path.is_file()
    }
    scanned = {path.name for path in REQUEST_PATH_MODULES if path.parent == SYMBOLS}
    missing = on_disk - scanned
    assert not missing, (
        "new symbols/ modules are not covered by the §12.10.2 guard: "
        f"{sorted(missing)} — add them to REQUEST_PATH_MODULES."
    )
