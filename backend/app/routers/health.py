import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.errores import respuesta_error

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sistema"])


@router.get("/health", summary="Estado del servicio y de la conexión a la base")
def health(db: Annotated[Session, Depends(get_db)]) -> JSONResponse:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Health check: la base no responde")
        return respuesta_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "base_no_disponible",
            "No se pudo conectar a la base de datos.",
        )
    return JSONResponse({"estado": "ok", "base_datos": "ok"})
