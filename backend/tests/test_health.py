from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db import get_db
from app.main import app


def test_health_responde_200_sin_token(client: TestClient) -> None:
    respuesta = client.get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok", "base_datos": "ok"}


def test_health_responde_503_si_la_base_no_responde() -> None:
    class SesionRota:
        def execute(self, *_args: object, **_kwargs: object) -> None:
            raise OperationalError("SELECT 1", {}, Exception("sin conexión"))

    def _get_db() -> Iterator[SesionRota]:
        yield SesionRota()

    app.dependency_overrides[get_db] = _get_db
    try:
        respuesta = TestClient(app).get("/health")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert respuesta.status_code == 503
    assert respuesta.json()["error"] == "base_no_disponible"
