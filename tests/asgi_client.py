"""Threadless ASGI client for deterministic router tests.

FastAPI's synchronous ``TestClient`` depends on an AnyIO blocking portal and
worker threads. Those threads are unavailable in the constrained runner used
for this repository's pre-deploy gate, so requests hang before assertions run.
This adapter keeps the small request API used by the tests while driving the
ASGI app on the current thread.
"""

from __future__ import annotations

import asyncio
from typing import Any

import fastapi.dependencies.utils
import fastapi.routing
import httpx
import starlette.routing

from app.handlers import openclaw_agent_hook, openclaw_forward


async def _run_inline(function, *args, **kwargs):
    """Execute sync endpoints and dependencies inline in the test loop."""
    return function(*args, **kwargs)


# FastAPI and Starlette import this helper into their routing modules. Patch
# only the test process so sync endpoints do not require worker threads.
fastapi.dependencies.utils.run_in_threadpool = _run_inline
fastapi.routing.run_in_threadpool = _run_inline
starlette.routing.run_in_threadpool = _run_inline
openclaw_agent_hook.run_in_threadpool = _run_inline
openclaw_forward.run_in_threadpool = _run_inline


class ASGITestClient:
    """Minimal synchronous facade over HTTPX's async ASGI transport."""

    __test__ = False

    __test__ = False

    def __init__(self, app: Any) -> None:
        self.app = app

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.request(method, url, **kwargs)

        return asyncio.run(send())

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)
