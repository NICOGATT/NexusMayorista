"""Validación del JWT de Supabase Auth (parte backend de HU-08).

Se aplica como dependencia a todo el router `/api/v1`. `/health` y `/webhooks/*`
quedan afuera: los webhooks se autentican con la firma de Meta.
"""

import logging
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.errores import ErrorAPI

logger = logging.getLogger(__name__)

# auto_error=False para devolver 401 con nuestro formato (por defecto FastAPI da 403).
_bearer = HTTPBearer(auto_error=False, description="JWT de Supabase Auth")

ALGORITMO_SECRETO = "HS256"  # JWT Secret "legacy" del proyecto
ALGORITMOS_ASIMETRICOS = ("ES256", "RS256")  # claves de firma nuevas, publicadas en JWKS


@lru_cache
def _cliente_jwks(url: str) -> jwt.PyJWKClient:
    # Cachea las claves 10 minutos; si llega un `kid` desconocido (rotación), las vuelve a pedir.
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=600, timeout=5)


def clave_publica(token: str, settings: Settings):
    """Clave pública del JWKS de Supabase que corresponde al `kid` del token."""
    if not settings.supabase_url:
        raise _no_autenticado("El backend no tiene SUPABASE_URL para validar el token.")
    try:
        return _cliente_jwks(settings.supabase_jwks_url).get_signing_key_from_jwt(token).key
    except jwt.PyJWKClientConnectionError as exc:
        logger.warning("No se pudieron obtener las claves de Supabase: %s", exc)
        raise ErrorAPI(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "servicio_no_disponible",
            "No se pudieron obtener las claves de Supabase para validar el token.",
        ) from exc
    except jwt.PyJWKClientError as exc:  # p. ej. el `kid` no está en el JWKS
        logger.info("JWT rechazado: %s", exc)
        raise _no_autenticado("Token inválido.") from exc


class Usuario(BaseModel):
    id: str
    email: str | None = None
    rol: str | None = None


def _no_autenticado(detalle: str) -> ErrorAPI:
    return ErrorAPI(
        status.HTTP_401_UNAUTHORIZED,
        "no_autenticado",
        detalle,
        headers={"WWW-Authenticate": "Bearer"},
    )


def decodificar_token(token: str, settings: Settings) -> Usuario:
    try:
        algoritmo = jwt.get_unverified_header(token).get("alg")
        if algoritmo == ALGORITMO_SECRETO and settings.supabase_jwt_secret:
            clave = settings.supabase_jwt_secret
        elif algoritmo in ALGORITMOS_ASIMETRICOS:
            clave = clave_publica(token, settings)
        else:
            raise jwt.InvalidAlgorithmError(f"Algoritmo no admitido: {algoritmo}")
        claims = jwt.decode(
            token,
            clave,
            algorithms=[algoritmo],
            audience=settings.supabase_jwt_audience,
            options={"require": ["exp", "sub", "aud"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise _no_autenticado("El token expiró.") from exc
    except jwt.InvalidTokenError as exc:
        logger.info("JWT rechazado: %s", exc)
        raise _no_autenticado("Token inválido.") from exc

    return Usuario(id=claims["sub"], email=claims.get("email"), rol=claims.get("role"))


def usuario_actual(
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Usuario:
    if credenciales is None or credenciales.scheme.lower() != "bearer":
        raise _no_autenticado("Falta el encabezado Authorization: Bearer <token>.")
    return decodificar_token(credenciales.credentials, settings)


UsuarioActual = Annotated[Usuario, Depends(usuario_actual)]
