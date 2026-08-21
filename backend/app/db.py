import os
from collections.abc import Generator

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

DB_PATH = os.getenv("CODEFORGE_DB_PATH", "codeforge.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# check_same_thread=False is safe here because FastAPI + SQLModel manage a
# short-lived session per request rather than sharing one connection across threads.
_engine_kwargs = {"connect_args": {"check_same_thread": False}}
if DB_PATH == ":memory:":
    # A plain sqlite in-memory DB is per-connection — without StaticPool,
    # every new request would get a *different*, empty in-memory database.
    # This branch only matters for tests (see tests/test_auth.py).
    _engine_kwargs["poolclass"] = StaticPool

engine = create_engine(DATABASE_URL, **_engine_kwargs)


def init_db() -> None:
    """Create all tables. Called once on application startup."""
    # Importing here (not at module top) avoids circular imports between
    # db.py and the model modules that import `engine`/`Session` from db.py.
    from app.auth.models import RefreshToken, User  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
