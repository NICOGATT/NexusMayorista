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
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402, F401  (registra las tablas en Base.metadata)
from app.config import get_settings  # noqa: E402
from app.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

SECRETO = os.environ["SUPABASE_JWT_SECRET"]


@pytest.fixture
def fabrica_sesiones() -> Iterator[sessionmaker[Session]]:
    """SQLite en memoria con las tablas de los modelos, nueva en cada test.

    StaticPool comparte una única conexión: el TestClient atiende en otro hilo y,
    sin esto, cada conexión vería una base en memoria distinta y vacía.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _get_db() -> Iterator[Session]:
        with fabrica() as db:
            yield db

    app.dependency_overrides[get_db] = _get_db
    yield fabrica
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


@pytest.fixture
def client(fabrica_sesiones: sessionmaker[Session]) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def api(client: TestClient) -> TestClient:
    """Cliente con un JWT válido en todas las peticiones."""
    client.headers["Authorization"] = f"Bearer {crear_token()}"
    return client


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
