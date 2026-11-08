from dataclasses import asdict
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import UsuarioActual
from app.db import get_db
from app.models import ReglasComerciales
from app.schemas.reglas_comerciales import FichaSalida, ReglasEntrada, ReglasSalida
from app.services import reglas_comerciales as servicio

router = APIRouter(prefix="/reglas-comerciales", tags=["reglas comerciales"])

DB = Annotated[Session, Depends(get_db)]


def _salida(fila: ReglasComerciales) -> ReglasSalida:
    return ReglasSalida(
        **{c: getattr(fila, c) for c in (*servicio.CAMPOS, *servicio.CAMPOS_CONFIRMACION)},
        preguntas=[
            {
                **asdict(p),
                "aplica": servicio.aplica(p.campo, fila),
                "respondida": servicio.respondida(p.campo, fila),
            }
            for p in servicio.PREGUNTAS
        ],
        pendientes=len(servicio.pendientes(fila)),
        actualizado_por=fila.actualizado_por,
        actualizado_en=fila.actualizado_en,
    )


@router.get(
    "",
    summary="Preguntas a la fábrica y sus respuestas",
    description="Un campo en null es una pregunta sin responder: el cálculo usa el valor "
    "por defecto (escala por producto, precios tal como están en la lista).",
)
def obtener(db: DB) -> ReglasSalida:
    return _salida(servicio.obtener(db))


@router.put(
    "",
    summary="Guarda las respuestas de la fábrica",
    description="Reemplaza todas las respuestas. Desde ese momento el cálculo de "
    "presupuestos las aplica.",
)
def guardar(datos: ReglasEntrada, db: DB, usuario: UsuarioActual) -> ReglasSalida:
    fila = servicio.guardar(db, datos.model_dump(), usuario=usuario.email or usuario.id)
    db.commit()
    db.refresh(fila)
    return _salida(fila)


@router.get(
    "/ficha",
    summary="Ficha para que la fábrica confirme las respuestas",
    description="Resumen en lenguaje llano, con las preguntas que faltan y un texto listo "
    "para pegar en WhatsApp.",
)
def ficha(db: DB) -> FichaSalida:
    resultado = servicio.generar_ficha(servicio.obtener(db), hoy=date.today())
    return FichaSalida.model_validate(asdict(resultado))
