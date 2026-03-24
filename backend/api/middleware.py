import time
from collections import defaultdict
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit: int = 120, window: int = 60):
        super().__init__(app)
        self._req    = defaultdict(list)
        self._limit  = limit
        self._window = window

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in ("/metrics", "/api/v1/health"):
            return await call_next(request)
        ip  = request.client.host
        now = time.time()
        self._req[ip] = [t for t in self._req[ip] if t > now - self._window]
        if len(self._req[ip]) >= self._limit:
            return Response(
                '{"detail":"Rate limit exceeded. Please wait 60 seconds."}',
                status_code=429, media_type="application/json")
        self._req[ip].append(now)
        return await call_next(request)
