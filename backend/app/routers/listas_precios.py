import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.errores import ErrorAPI
from app.models import ListaPrecios, Precio, Producto
from app.schemas.catalogo import (
    ImportacionResultado,
    ListaPreciosDetalle,
    ListaPreciosSalida,
    PrecioSalida,
)
from app.services import listas_precios as servicio
from app.services.importar_csv import TAMANIO_MAXIMO, decodificar, validar_csv

router = APIRouter(prefix="/listas-precios", tags=["listas de precios"])

DB = Annotated[Session, Depends(get_db)]


def _detalle(db: Session, lista: ListaPrecios) -> ListaPreciosDetalle:
    filas = db.execute(
        select(Precio, Producto.codigo, Producto.nombre)
        .join(Producto, Producto.id == Precio.producto_id)
        .where(Precio.lista_id == lista.id)
        .order_by(Producto.codigo, func.coalesce(Precio.talle, ""), Precio.cantidad_minima)
    ).all()
    return ListaPreciosDetalle(
        **ListaPreciosSalida.model_validate(lista).model_dump(),
        precios=[
            PrecioSalida(
                id=precio.id,
                producto_id=precio.producto_id,
                codigo=codigo,
                producto=nombre,
                talle=precio.talle,
                cantidad_minima=precio.cantidad_minima,
                precio_unitario=precio.precio_unitario,
            )
            for precio, codigo, nombre in filas
        ],
    )


def _obtener(db: Session, lista_id: uuid.UUID) -> ListaPrecios:
    lista = db.get(ListaPrecios, lista_id)
    if lista is None:
        raise ErrorAPI(status.HTTP_404_NOT_FOUND, "lista_no_encontrada", str(lista_id))
    return lista


@router.get("", summary="Todas las listas, la más reciente primero")
def listar_listas(db: DB) -> list[ListaPreciosSalida]:
    listas = db.scalars(
        select(ListaPrecios).order_by(ListaPrecios.creado_en.desc(), ListaPrecios.nombre)
    )
    return [ListaPreciosSalida.model_validate(lista) for lista in listas]


@router.get("/activa", summary="Lista vigente con sus precios")
def lista_activa(db: DB) -> ListaPreciosDetalle:
    lista = db.scalar(select(ListaPrecios).where(ListaPrecios.activa.is_(True)))
    if lista is None:
        raise ErrorAPI(
            status.HTTP_404_NOT_FOUND,
            "sin_lista_activa",
            "No hay una lista de precios activa. Importá una y activala.",
        )
    return _detalle(db, lista)


@router.get("/{lista_id}", summary="Detalle de una lista con sus precios")
def obtener_lista(lista_id: uuid.UUID, db: DB) -> ListaPreciosDetalle:
    return _detalle(db, _obtener(db, lista_id))


@router.post(
    "/importar",
    status_code=status.HTTP_201_CREATED,
    summary="Carga una lista nueva (inactiva) desde CSV",
    description=(
        "CSV con cabecera `codigo,talle,cantidad_minima,precio_unitario` "
        "(también `;` y coma decimal). Se validan todas las filas: si alguna falla "
        "no se guarda nada y la respuesta indica línea, código y motivo."
    ),
)
def importar_lista(
    db: DB,
    archivo: Annotated[UploadFile, File(description="Archivo .csv")],
    nombre: Annotated[str, Form(examples=["Mayorista Noviembre 2026"])],
    vigente_desde: Annotated[date, Form()],
    vigente_hasta: Annotated[date | None, Form()] = None,
    moneda: Annotated[str, Form(min_length=3, max_length=3)] = "ARS",
) -> ImportacionResultado:
    nombre = nombre.strip()
    if not nombre:
        raise ErrorAPI(status.HTTP_422_UNPROCESSABLE_CONTENT, "validacion", "Falta el nombre.")
    if vigente_hasta and vigente_hasta < vigente_desde:
        raise ErrorAPI(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "validacion",
            "vigente_hasta no puede ser anterior a vigente_desde.",
        )

    contenido = archivo.file.read(TAMANIO_MAXIMO + 1)
    if len(contenido) > TAMANIO_MAXIMO:
        raise ErrorAPI(
            status.HTTP_413_CONTENT_TOO_LARGE, "archivo_muy_grande", "El CSV supera los 2 MB."
        )

    resultado = validar_csv(decodificar(contenido), servicio.catalogo_por_codigo(db))
    if not resultado.es_valido:
        raise ErrorAPI(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "csv_invalido",
            [e.a_dict() for e in resultado.errores],
        )

    lista = servicio.crear_lista(
        db,
        resultado,
        nombre=nombre,
        vigente_desde=vigente_desde,
        vigente_hasta=vigente_hasta,
        moneda=moneda,
    )
    db.commit()  # una sola transacción: la lista y todas sus escalas
    db.refresh(lista)
    return ImportacionResultado(
        lista=ListaPreciosSalida.model_validate(lista),
        filas_cargadas=len(resultado.filas),
    )


@router.post(
    "/{lista_id}/activar",
    summary="Activa la lista y desactiva la anterior en una transacción",
)
def activar_lista(lista_id: uuid.UUID, db: DB) -> ListaPreciosSalida:
    lista = db.get(ListaPrecios, lista_id, with_for_update=True)
    if lista is None:
        raise ErrorAPI(status.HTTP_404_NOT_FOUND, "lista_no_encontrada", str(lista_id))
    if not lista.activa:
        try:
            servicio.activar(db, lista)
            db.commit()
        except IntegrityError as exc:
            # Otra activación ganó la carrera: el índice único impidió dos activas.
            db.rollback()
            raise ErrorAPI(
                status.HTTP_409_CONFLICT,
                "activacion_concurrente",
                "Otra lista se activó al mismo tiempo. Reintentá.",
            ) from exc
        db.refresh(lista)
    return ListaPreciosSalida.model_validate(lista)
