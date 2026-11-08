import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app import auth
from app.config import get_settings
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


# ------------------------------------- claves de firma nuevas de Supabase (ES256 + JWKS)

CLAVE_EC = ec.generate_private_key(ec.SECP256R1())
OTRA_CLAVE_EC = ec.generate_private_key(ec.SECP256R1())
KID = "clave-de-prueba"


def token_es256(*, clave=CLAVE_EC, kid: str = KID, expira_en: int = 3600) -> str:
    ahora = int(time.time())
    claims = {
        "sub": "22222222-2222-2222-2222-222222222222",
        "email": "nico@example.com",
        "role": "authenticated",
        "aud": "authenticated",
        "iat": ahora,
        "exp": ahora + expira_en,
    }
    return jwt.encode(claims, clave, algorithm="ES256", headers={"kid": kid})


class JwksFalso:
    """Reemplaza a PyJWKClient: publica solo la clave pública de CLAVE_EC."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def get_signing_key_from_jwt(self, token: str):
        if self.error:
            raise self.error
        if jwt.get_unverified_header(token)["kid"] != KID:
            raise jwt.PyJWKClientError("Unable to find a signing key that matches")
        return SimpleNamespace(key=CLAVE_EC.public_key())


@pytest.fixture
def jwks(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SUPABASE_URL", "https://proyecto.supabase.co")
    urls: list[str] = []

    def instalar(cliente: JwksFalso) -> list[str]:
        def _cliente(url: str) -> JwksFalso:
            urls.append(url)
            return cliente

        monkeypatch.setattr(auth, "_cliente_jwks", _cliente)
        return urls

    return instalar


def test_token_es256_valido_con_jwks(client: TestClient, jwks) -> None:
    urls = jwks(JwksFalso())

    respuesta = client.get(RUTA_PROTEGIDA, headers={"Authorization": f"Bearer {token_es256()}"})

    assert respuesta.status_code == 200
    assert respuesta.json()["email"] == "nico@example.com"
    assert urls == ["https://proyecto.supabase.co/auth/v1/.well-known/jwks.json"]


@pytest.mark.parametrize(
    "token",
    [
        token_es256(clave=OTRA_CLAVE_EC),  # firma que no corresponde a la clave publicada
        token_es256(kid="kid-desconocido"),
        token_es256(expira_en=-10),
    ],
)
def test_token_es256_invalido_responde_401(client: TestClient, jwks, token: str) -> None:
    jwks(JwksFalso())

    respuesta = client.get(RUTA_PROTEGIDA, headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 401


def test_sin_acceso_al_jwks_responde_503(client: TestClient, jwks) -> None:
    jwks(JwksFalso(error=jwt.PyJWKClientConnectionError("timeout")))

    respuesta = client.get(RUTA_PROTEGIDA, headers={"Authorization": f"Bearer {token_es256()}"})

    assert respuesta.status_code == 503
    assert respuesta.json()["error"] == "servicio_no_disponible"


def test_token_hs256_sin_secreto_configurado_responde_401(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, token: str
) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "")

    respuesta = client.get(RUTA_PROTEGIDA, headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 401


def test_token_sin_firma_responde_401(client: TestClient) -> None:
    token = jwt.encode({"sub": "x", "aud": "authenticated", "exp": 9999999999}, None, "none")

    respuesta = client.get(RUTA_PROTEGIDA, headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 401


@pytest.mark.parametrize(
    "url",
    [
        "https://proyecto.supabase.co",
        "https://proyecto.supabase.co/",
        "https://proyecto.supabase.co/rest/v1/",
    ],
)
def test_url_del_jwks_usa_solo_el_dominio(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    monkeypatch.setenv("SUPABASE_URL", url)

    assert get_settings().supabase_jwks_url == (
        "https://proyecto.supabase.co/auth/v1/.well-known/jwks.json"
    )
