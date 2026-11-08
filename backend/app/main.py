"""Punto de entrada de la API: `uvicorn app.main:app` desde `backend/`."""

import logging

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import usuario_actual
from app.config import get_settings
from app.errores import registrar_manejadores
from app.routers import (
    health,
    listas_precios,
    presupuestos,
    productos,
    reglas_comerciales,
    usuarios,
)


def configurar_logging(nivel: str) -> None:
    logging.basicConfig(
        level=nivel.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def create_app() -> FastAPI:
    settings = get_settings()
    configurar_logging(settings.log_level)

    app = FastAPI(
        title="NexusMayorista API",
        version="0.1.0",
        description="CRM mayorista de ropa: catálogo, presupuestos y tablero.",
    )
    registrar_manejadores(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origenes.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # Públicos: /health y, más adelante, /webhooks/* (se autentican con la firma de Meta).
    app.include_router(health.router)

    # Todo lo que cuelga de /api/v1 exige un JWT válido de Supabase.
    api = APIRouter(prefix="/api/v1", dependencies=[Depends(usuario_actual)])
    api.include_router(usuarios.router)
    api.include_router(productos.router)
    api.include_router(listas_precios.router)
    api.include_router(presupuestos.router)
    api.include_router(reglas_comerciales.router)
    app.include_router(api)

    return app


app = create_app()
