"""Shared 501-stub helper for F002 schema-registration routes.

F002 only registers schemas in OpenAPI; the actual handlers are filled
in by F006-F012 vertical slices. Each stub route still requires the
auth dependency (so the auth surface is stable from day one) and raises
``501 Not Implemented`` with a marker pointing at the feature that
finishes it. Tests assert the 501 path so we notice if a route ever
ships without a real implementation.
"""

from __future__ import annotations

from fastapi import HTTPException, status


def not_implemented(feature: str) -> HTTPException:
    """Construct the canonical 501 raised by F002 stub routes.

    The ``feature`` argument identifies the B022 feature id (e.g.
    ``"F006"``) that will replace this stub, so an evaluator hitting
    the route in CI gets a self-describing failure message.
    """

    return HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"Not implemented; schema registered in B022-F002, handler lands in B022-{feature}.",
    )
