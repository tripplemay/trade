"""B049 F001 — snapshots request-path §12.10.2 self-containment.

The Snapshots refresh streams the *real* on-disk data state (the unified CSVs
the B045 data-refresh job wrote) and records a SnapshotMeta row. It must stay
off the heavy ``trade`` stack and introduce no execution path: the request
handler reads CSV/DB and writes only its own SnapshotMeta row.

Contract:
- ``routes/snapshots.py`` + ``services/snapshots.py`` + the helper
  ``data_refresh/inventory.py`` they pull in must NEVER import ``trade``. The
  daily heavy data fetch lives in ``data_refresh/cli.py`` (the systemd timer
  job), off the request path.
"""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = BACKEND_ROOT / "workbench_api"

REQUEST_PATH_MODULES = (
    PACKAGE_ROOT / "routes" / "snapshots.py",
    PACKAGE_ROOT / "services" / "snapshots.py",
    PACKAGE_ROOT / "data_refresh" / "inventory.py",
)


def _imports_trade(py_path: Path) -> bool:
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


def test_snapshots_request_path_does_not_import_trade() -> None:
    offenders = sorted(
        str(path.relative_to(BACKEND_ROOT))
        for path in REQUEST_PATH_MODULES
        if path.is_file() and _imports_trade(path)
    )
    assert not offenders, (
        "§12.10.2 violated: the snapshots request path imports the trade "
        f"package {offenders}. The refresh must only read the data the "
        "data_refresh timer job wrote + write its own SnapshotMeta row — never "
        "import trade on the request path."
    )
