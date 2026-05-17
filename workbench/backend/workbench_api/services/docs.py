"""``/api/docs/{path}`` path resolver + reader (B022 F007 → F009 reuse).

The endpoint exposes a controlled view onto the repo so the frontend can
deep-link spec and code paths inline (per F007 / F009 acceptance). Two
hard rules:

1. **Path traversal sanitisation.** The supplied path must be relative,
   contain no ``..`` segments, and resolve under the configured root.
   Any violation raises ``InvalidDocsPathError`` which the route layer
   translates to HTTP 400 — never 500 / 200, so a probing client gets
   a clear deny rather than an oracle.
2. **Existence-or-404.** A clean path that doesn't resolve to a file
   raises ``DocsNotFoundError`` → 404. We do **not** distinguish
   "directory" from "missing" so an attacker can't enumerate the tree.

The default root is the repo root (computed from this module's path).
``WORKBENCH_DOCS_ROOT`` is intentionally *not* introduced as a settings
field — F007 + F009 both want repo-wide read access, and a separate
env var would invite drift.
"""

from __future__ import annotations

from pathlib import Path

from workbench_api.schemas.reports import DocsResponse


class InvalidDocsPathError(ValueError):
    """The supplied path failed traversal sanitisation."""


class DocsNotFoundError(LookupError):
    """The sanitised path did not resolve to an existing file."""


# Walk up from ``workbench_api/services/docs.py`` five ``parents`` levels
# to land at the repo root: services/ → workbench_api/ → backend/ →
# workbench/ → repo. Mirrored from ``workbench_api/cli/bootstrap.py``
# which uses parents[4] from a file at the same depth. The B022 F014
# blocker fix corrected the prior parents[3] anchor, which silently
# stopped at ``workbench/`` and made docs/ / trade/ files inaccessible
# through ``/api/docs/{path}``.
#
# Production note: when the package is installed as a wheel into
# ``/opt/workbench/.venv``, ``__file__`` points inside site-packages
# and parents[4] no longer reaches the release tree. The route handler
# is permitted to pass an explicit ``root=`` to override; B023 may
# need a settings field if the docs viewer is reused in production.
DEFAULT_REPO_ROOT: Path = Path(__file__).resolve().parents[4]


_CONTENT_TYPE_MAP: dict[str, str] = {
    ".md": "markdown",
    ".py": "python",
    ".json": "json",
    ".txt": "text",
    ".yml": "text",
    ".yaml": "text",
}


def sanitize_repo_path(relative_path: str, *, root: Path = DEFAULT_REPO_ROOT) -> Path:
    """Translate a user-supplied path into a safe absolute Path.

    Raises ``InvalidDocsPathError`` for any of:

    * an empty string (no path),
    * an absolute path,
    * any segment equal to ``..``,
    * a resolved path that escapes ``root`` (defence-in-depth in case
      Path's normalisation differs across platforms).
    """

    candidate_raw = (relative_path or "").strip()
    if not candidate_raw:
        raise InvalidDocsPathError("Empty path is not allowed.")
    candidate = Path(candidate_raw)
    if candidate.is_absolute():
        raise InvalidDocsPathError("Absolute paths are not allowed.")
    if any(part == ".." for part in candidate.parts):
        raise InvalidDocsPathError("Parent-traversal ('..') segments are not allowed.")

    resolved = (root / candidate).resolve()
    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise InvalidDocsPathError("Resolved path escapes the docs root.") from exc
    return resolved


def load_doc(relative_path: str, *, root: Path = DEFAULT_REPO_ROOT) -> DocsResponse:
    """Read a repo-relative file and wrap it in a DocsResponse.

    Raises ``InvalidDocsPathError`` on a bad path, ``DocsNotFoundError``
    when the resolved file does not exist. The route layer converts both
    to HTTP responses.
    """

    resolved = sanitize_repo_path(relative_path, root=root)
    if not resolved.is_file():
        raise DocsNotFoundError(f"No such file: {relative_path}")

    body = resolved.read_text(encoding="utf-8", errors="replace")
    content_type = _CONTENT_TYPE_MAP.get(resolved.suffix.lower(), "text")
    return DocsResponse(path=relative_path, content_type=content_type, body=body)
