"""
Blocking SQLAlchemy session factory for background job threads.

Request handlers use the async engine. Jobs run in worker threads outside the event loop, where
a plain synchronous session is simpler and safe. Both talk to the same database.
"""

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_kwargs = {}
if settings.sync_database_url.startswith("sqlite"):
    _kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}

sync_engine = create_engine(settings.sync_database_url, future=True, **_kwargs)
if settings.sync_database_url.startswith("sqlite"):
    from sqlalchemy import event

    @event.listens_for(sync_engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

_SessionFactory = sessionmaker(bind=sync_engine, expire_on_commit=False, autoflush=False)


@contextmanager
def sync_session() -> Iterator[Session]:
    """Commit on success, roll back on error."""
    s = _SessionFactory()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
