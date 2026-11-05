"""Conexión a la base con SQLAlchemy 2."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Base de los modelos ORM (se usan desde HU-01)."""


@lru_cache
def get_engine() -> Engine:
    # pool_pre_ping evita usar conexiones que el pooler de Supabase ya cerró.
    return create_engine(get_settings().sqlalchemy_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dependencia de FastAPI: una sesión por petición."""
    db = get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()
