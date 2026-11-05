import pytest
from fastapi.testclient import TestClient

from tests.conftest import crear_token

RUTA_PROTEGIDA = "/api/v1/yo"


def test_sin_token_responde_401(client: TestClient) -> None:
    respuesta = client.get(RUTA_PROTEGIDA)

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"
    assert respuesta.json()["error"] == "no_autenticado"


def test_token_valido_devuelve_el_usuario(client: TestClient, token: str) -> None:
    respuesta = client.get(RUTA_PROTEGIDA, headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "vendedor@example.com",
        "rol": "authenticated",
    }


@pytest.mark.parametrize(
    ("token", "detalle"),
    [
        (crear_token(expira_en=-10), "El token expiró."),
        (crear_token(secreto="otro-secreto-que-no-es-el-de-supabase-32b"), "Token inválido."),
        (crear_token(aud="anon-otro"), "Token inválido."),
        ("esto-no-es-un-jwt", "Token inválido."),
    ],
    ids=["expirado", "firma-incorrecta", "audiencia-incorrecta", "malformado"],
)
def test_token_invalido_responde_401(client: TestClient, token: str, detalle: str) -> None:
    respuesta = client.get(RUTA_PROTEGIDA, headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 401
    assert respuesta.json() == {"error": "no_autenticado", "detalle": detalle}


def test_esquema_distinto_de_bearer_responde_401(client: TestClient, token: str) -> None:
    respuesta = client.get(RUTA_PROTEGIDA, headers={"Authorization": f"Basic {token}"})

    assert respuesta.status_code == 401


def test_docs_es_publico(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
