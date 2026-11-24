import logging
from asyncio import timeout
from collections import deque
from time import monotonic

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("uvicorn.error.fortress.requests")


class RequestLimits:
    def __init__(self, app: ASGIApp, *, requests_per_minute: int, max_request_bytes: int) -> None:
        self.app = app
        self.requests_per_minute = requests_per_minute
        self.max_request_bytes = max_request_bytes
        self.arrivals: deque[float] = deque()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in {"/health", "/ready"}:
            await self.app(scope, receive, send)
            return

        started = monotonic()
        status = 500

        async def logged_send(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            while self.arrivals and self.arrivals[0] <= started - 60:
                self.arrivals.popleft()
            if len(self.arrivals) >= self.requests_per_minute:
                await JSONResponse(
                    {"detail": "Too many requests. Try again later."},
                    status_code=429,
                    headers={"Retry-After": "60"},
                )(scope, receive, logged_send)
                return
            self.arrivals.append(started)

            if scope["method"] == "POST" and scope["path"].rstrip("/") == "/api/v1/answers":
                body = bytearray()
                try:
                    async with timeout(10):
                        while True:
                            message = await receive()
                            if message["type"] == "http.disconnect":
                                status = 499
                                return
                            chunk = message.get("body", b"")
                            if len(body) + len(chunk) > self.max_request_bytes:
                                await JSONResponse(
                                    {"detail": "The request body is too large."}, status_code=413
                                )(scope, receive, logged_send)
                                return
                            body.extend(chunk)
                            if not message.get("more_body"):
                                break
                except TimeoutError:
                    await JSONResponse({"detail": "The request body timed out."}, status_code=408)(
                        scope, receive, logged_send
                    )
                    return

                async def replay() -> Message:
                    return {"type": "http.request", "body": bytes(body), "more_body": False}

                await self.app(scope, replay, logged_send)
            else:
                await self.app(scope, receive, logged_send)
        finally:
            logger.log(
                logging.WARNING if status >= 400 else logging.INFO,
                "request method=%s status=%d duration_ms=%.1f",
                scope["method"],
                status,
                (monotonic() - started) * 1000,
            )
