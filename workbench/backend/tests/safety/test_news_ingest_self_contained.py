"""B038 F003 fix-round — news-ingest deploy-artifact self-containment.

v0.9.32 §12.10: the production deploy artifact ships only the
``workbench_api/`` package — never the repo-root ``scripts/`` helper
package. Any module under ``workbench_api/`` that imports ``scripts`` at
import/run time works locally + in CI (editable install carries the repo
root) but raises ``ModuleNotFoundError`` on the VM.

This was latent until B038: ``workbench_api/news/cli.py:_default_universe``
imported ``scripts.universe_us_quality``, but news ingest was manual-only
(boundary (q)) so the CLI never ran in production. B038 wired the CLI into
the ``workbench-news`` systemd timer (boundary (q)→(r)); the first oneshot
on the VM hit the missing ``scripts`` module (Codex F003 L2 blocker,
docs/test-reports/B038-home-market-news-blocker-2026-06-06.md).

These guards lock the whole package self-contained so a future edit can't
re-introduce a repo-root import on any production run path.
"""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = BACKEND_ROOT / "workbench_api"


def _imports_repo_root_scripts(py_path: Path) -> bool:
    """True if the module imports the repo-root ``scripts`` package.

    Only absolute imports of the top-level ``scripts`` package count — a
    relative import (``from .scripts``) or an attribute named ``scripts``
    is not the repo-root helper. Docstring/comment mentions are ignored
    (we walk the AST, not the source text)."""

    tree = ast.parse(py_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "scripts" or alias.name.startswith("scripts."):
                    return True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level == 0 and (module == "scripts" or module.startswith("scripts.")):
                return True
    return False


def test_workbench_api_package_does_not_import_repo_root_scripts() -> None:
    """No module shipped in the deploy artifact may import repo-root
    ``scripts`` — it isn't on the VM (v0.9.32 §12.10)."""

    offenders = sorted(
        str(path.relative_to(BACKEND_ROOT))
        for path in PACKAGE_ROOT.rglob("*.py")
        if _imports_repo_root_scripts(path)
    )
    assert not offenders, (
        "deploy-artifact self-containment violated (v0.9.32 §12.10): these "
        f"workbench_api modules import the repo-root scripts package {offenders}. "
        "scripts/ is NOT shipped to the VM — materialise the needed constant into "
        "the workbench_api package (see news/ticker_match._UNIVERSE_NAMES) instead."
    )


def test_news_cli_default_universe_is_self_contained_and_correct() -> None:
    """The news timer's default universe resolves from in-package data and
    yields the B025 27 real tickers + the 4 master ETFs."""

    from workbench_api.news.cli import _default_universe
    from workbench_api.news.ticker_match import equity_universe_tickers

    universe = _default_universe()
    equity = equity_universe_tickers()  # in-package, no scripts / pandas

    assert set(("SPY", "QQQ", "EFA", "EEM")).issubset(set(universe))
    assert set(equity).issubset(set(universe))
    # exactly the equity universe + the 4 ETFs, no duplicates.
    assert len(universe) == len(equity) + 4
    assert len(set(universe)) == len(universe)

    # The CLI module itself must not statically import scripts.
    assert not _imports_repo_root_scripts(PACKAGE_ROOT / "news" / "cli.py")
