from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings


class Base(DeclarativeBase):
    pass


def build_engine(settings: Settings) -> Engine:
    common: dict[str, object] = {"pool_pre_ping": True}
    if settings.mysql_dsn.startswith("sqlite"):
        common.update(
            {
                "connect_args": {"check_same_thread": False},
                "poolclass": StaticPool,
            }
        )
    else:
        common.update(
            {
                "pool_size": settings.mysql_pool_size,
                "max_overflow": settings.mysql_max_overflow,
                "pool_recycle": settings.mysql_pool_recycle,
            }
        )
    return create_engine(settings.mysql_dsn, **common)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def session_dependency(factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = factory()
    try:
        yield session
    finally:
        session.close()
