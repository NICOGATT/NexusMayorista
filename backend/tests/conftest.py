import os
import time
from collections.abc import Iterator

import jwt
import pytest

# Variables mínimas para que la app arranque sin .env ni base real (CI incluida).
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SUPABASE_JWT_SECRET", "secreto-de-prueba-con-longitud-suficiente-32b")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import get_db  # noqa: E402
from app.main import app  # noqa: E402

SECRETO = os.environ["SUPABASE_JWT_SECRET"]


@pytest.fixture
def db_sqlite() -> Iterator[None]:
    """Reemplaza la base por SQLite en memoria: alcanza para `SELECT 1`."""
    engine = create_engine("sqlite://")
    fabrica = sessionmaker(bind=engine)

    def _get_db() -> Iterator[Session]:
        with fabrica() as db:
            yield db

    app.dependency_overrides[get_db] = _get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


@pytest.fixture
def client(db_sqlite: None) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def crear_token(
    *,
    sub: str = "11111111-1111-1111-1111-111111111111",
    email: str = "vendedor@example.com",
    aud: str = "authenticated",
    expira_en: int = 3600,
    secreto: str = SECRETO,
    algoritmo: str = "HS256",
) -> str:
    ahora = int(time.time())
    claims = {
        "sub": sub,
        "email": email,
        "role": "authenticated",
        "aud": aud,
        "iat": ahora,
        "exp": ahora + expira_en,
    }
    return jwt.encode(claims, secreto, algorithm=algoritmo)


@pytest.fixture
def token() -> str:
    return crear_token()


@pytest.fixture(autouse=True)
def _limpiar_cache_settings() -> Iterator[None]:
    yield
    get_settings.cache_clear()
