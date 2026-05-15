"""Request-id middleware.

Each request gets a server-minted UUID v4 unless the caller already
provided ``X-Request-ID`` (Cloud Run / nginx upstream paths sometimes
do). The value lands on ``request.state.request_id`` for handlers /
dependencies to read, on the ``REQUEST_ID_VAR`` contextvar so the JSON
formatter can pick it up without an explicit kwarg, and on the response
header so the caller can correlate a log line to a server-side line.

The middleware is a plain ASGI implementation rather than
``BaseHTTPMiddleware`` because the latter swallows ``ContextVar.set``
across the await boundary in some Starlette versions; doing it at the
raw scope/send level keeps the variable bound for the entire request.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from workbench_api.observability.logging import REQUEST_ID_VAR, USER_ID_VAR

if TYPE_CHECKING:
    pass

REQUEST_HEADER_NAME = b"x-request-id"
RESPONSE_HEADER_NAME = b"x-request-id"


class RequestIDMiddleware:
    """ASGI middleware that mints / forwards ``X-Request-ID``."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = _read_header(scope, REQUEST_HEADER_NAME)
        request_id = incoming or uuid.uuid4().hex
        token = REQUEST_ID_VAR.set(request_id)
        user_token = USER_ID_VAR.set(None)

        # Make the id visible to route handlers via request.state.
        scope.setdefault("state", {})
        scope["state"]["request_id"] = request_id

        async def send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                # Replace any upstream-issued header to avoid duplicates.
                headers = [(k, v) for (k, v) in headers if k.lower() != RESPONSE_HEADER_NAME]
                headers.append((RESPONSE_HEADER_NAME, request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        finally:
            REQUEST_ID_VAR.reset(token)
            USER_ID_VAR.reset(user_token)


def _read_header(scope: Scope, name: bytes) -> str | None:
    headers = scope.get("headers")
    if not headers:
        return None
    for key, value in headers:
        if isinstance(key, bytes) and key.lower() == name and isinstance(value, bytes):
            try:
                decoded: str = value.decode("ascii")
            except UnicodeDecodeError:
                return None
            return decoded
    return None
