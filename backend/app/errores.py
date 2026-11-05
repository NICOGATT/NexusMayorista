"""Formato de error único para toda la API: `{"error": ..., "detalle": ...}`.

- `error`: código corto y estable, en snake_case, para que el frontend lo pueda evaluar.
- `detalle`: texto legible o, en errores de validación, la lista de campos con problema.
"""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

# Códigos por defecto para las excepciones HTTP que no traen uno propio.
CODIGOS_POR_ESTADO: dict[int, str] = {
    400: "solicitud_invalida",
    401: "no_autenticado",
    403: "sin_permiso",
    404: "no_encontrado",
    405: "metodo_no_permitido",
    409: "conflicto",
    422: "validacion",
    500: "error_interno",
    502: "servicio_externo",
    503: "servicio_no_disponible",
}


class ErrorAPI(Exception):
    """Error de negocio que se devuelve tal cual al cliente."""

    def __init__(
        self,
        status_code: int,
        error: str,
        detalle: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(error)
        self.status_code = status_code
        self.error = error
        self.detalle = detalle
        self.headers = headers


def respuesta_error(
    status_code: int,
    error: str,
    detalle: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "detalle": detalle},
        headers=headers,
    )


def _codigo_para(status_code: int) -> str:
    if status_code in CODIGOS_POR_ESTADO:
        return CODIGOS_POR_ESTADO[status_code]
    try:
        return HTTPStatus(status_code).phrase.lower().replace(" ", "_")
    except ValueError:
        return "error"


async def _manejar_error_api(_: Request, exc: ErrorAPI) -> JSONResponse:
    return respuesta_error(exc.status_code, exc.error, exc.detalle, exc.headers)


async def _manejar_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return respuesta_error(
        exc.status_code,
        _codigo_para(exc.status_code),
        exc.detail,
        getattr(exc, "headers", None),
    )


async def _manejar_validacion(_: Request, exc: RequestValidationError) -> JSONResponse:
    campos = [
        {
            "campo": ".".join(str(parte) for parte in err.get("loc", ())),
            "mensaje": err.get("msg"),
            "tipo": err.get("type"),
        }
        for err in exc.errors()
    ]
    return respuesta_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "validacion", campos)


async def _manejar_inesperado(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Error no controlado en %s %s", request.method, request.url.path)
    return respuesta_error(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "error_interno",
        "Ocurrió un error inesperado.",
    )


def registrar_manejadores(app: FastAPI) -> None:
    app.add_exception_handler(ErrorAPI, _manejar_error_api)
    app.add_exception_handler(StarletteHTTPException, _manejar_http)
    app.add_exception_handler(RequestValidationError, _manejar_validacion)
    app.add_exception_handler(Exception, _manejar_inesperado)
