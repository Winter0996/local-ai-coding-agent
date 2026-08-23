import pytest

from app.auth.rate_limit import _attempts


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """The login rate limiter tracks attempts in a module-level dict scoped
    to the whole process (app/auth/rate_limit.py) — correct for a
    single-process app, this means attempts accumulate across every test
    in the same pytest session unless reset here. Without this,
    test files that run after several login-heavy tests start getting 429'd
    even though each test is logically independent."""
    _attempts.clear()
    yield
    _attempts.clear()