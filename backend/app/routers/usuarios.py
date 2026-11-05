from fastapi import APIRouter

from app.auth import Usuario, UsuarioActual

router = APIRouter(tags=["usuarios"])


@router.get("/yo", summary="Usuario autenticado según el JWT")
def yo(usuario: UsuarioActual) -> Usuario:
    return usuario
