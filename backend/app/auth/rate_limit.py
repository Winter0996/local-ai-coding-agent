import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

# NOTE: this is an in-memory limiter — it resets on restart and does not
# coordinate across multiple processes/instances. That's an acceptable
# tradeoff for a single-process local-first MVP. If you ever run this behind
# multiple Uvicorn workers or in a hosted multi-instance setup, swap this for
# a shared store (Redis, e.g. via `slowapi` + Redis backend) so all instances
# see the same attempt counts.
_attempts: dict[str, list[float]] = defaultdict(list)

MAX_ATTEMPTS = 5
WINDOW_SECONDS = 60


def enforce_login_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()

    window_start = now - WINDOW_SECONDS
    _attempts[client_ip] = [t for t in _attempts[client_ip] if t > window_start]

    if len(_attempts[client_ip]) >= MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again in a minute.",
        )

    _attempts[client_ip].append(now)
