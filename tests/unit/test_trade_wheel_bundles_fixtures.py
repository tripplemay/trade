"""BL-B011-S2 F003 fix-round — the trade wheel must bundle the satellite
strategy fixtures.

Root cause of the F004 Finding #1 regression: the us_quality + hk_china
loaders resolve their universe (and us_quality's earnings calendar) from
``<repo_root>/data/fixtures/...`` (``repo_root = parents[2]`` of the loader
module). In a wheel install ``repo_root`` is ``site-packages``; without
shipping the fixtures there, ``load_universe`` raises on the VM and both
satellite sleeves stub. The wheel's ``force-include`` lands them at
``site-packages/data/fixtures/...``.

This test pins the packaging config so the bundling can never silently
regress (building + installing a wheel here would be too slow for unit CI).
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"

_REQUIRED_FIXTURE_DIRS = (
    "data/fixtures/us_quality_momentum",
    "data/fixtures/hk_china_momentum",
)


def _force_include() -> dict[str, str]:
    with _PYPROJECT.open("rb") as fh:
        data = tomllib.load(fh)
    return (
        data.get("tool", {})
        .get("hatch", {})
        .get("build", {})
        .get("targets", {})
        .get("wheel", {})
        .get("force-include", {})
    )


def test_pyproject_force_includes_satellite_fixtures() -> None:
    force_include = _force_include()
    for fixture_dir in _REQUIRED_FIXTURE_DIRS:
        assert force_include.get(fixture_dir) == fixture_dir, (
            f"trade wheel must force-include '{fixture_dir}' so the wheel-"
            f"installed strategy loaders resolve their fixtures on the VM "
            f"(else the sleeve stubs). force-include={force_include}"
        )


def test_bundled_fixture_dirs_exist_with_universe_csv() -> None:
    """The force-included paths must actually exist with the universe.csv the
    loaders read — a stale path in pyproject would ship nothing."""

    for fixture_dir in _REQUIRED_FIXTURE_DIRS:
        universe = _REPO_ROOT / fixture_dir / "universe.csv"
        assert universe.is_file(), f"missing {universe}"


def test_tomllib_available() -> None:
    # tomllib is stdlib on the 3.11 target; pin so the test env matches.
    assert sys.version_info >= (3, 11)
