"""Validación del JWT de Supabase Auth (parte backend de HU-08).

Se aplica como dependencia a todo el router `/api/v1`. `/health` y `/webhooks/*`
quedan afuera: los webhooks se autentican con la firma de Meta.
"""

import logging
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

ALGORITMOS = ["HS256"]


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
        claims = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=ALGORITMOS,
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
