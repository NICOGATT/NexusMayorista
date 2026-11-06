import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.errores import ErrorAPI
from app.models import Producto
from app.schemas.catalogo import (
    ImportacionCatalogoResultado,
    ProductoCrear,
    ProductoEditar,
    ProductoSalida,
)
from app.services.importar_catalogo import aplicar_catalogo, validar_catalogo_csv
from app.services.importar_csv import TAMANIO_MAXIMO, decodificar

router = APIRouter(prefix="/productos", tags=["catálogo"])

DB = Annotated[Session, Depends(get_db)]


def _codigo_duplicado(codigo: str) -> ErrorAPI:
    return ErrorAPI(
        status.HTTP_409_CONFLICT,
        "codigo_duplicado",
        f"Ya existe un producto con el código {codigo}.",
    )


def _obtener(db: Session, producto_id: uuid.UUID) -> Producto:
    producto = db.get(Producto, producto_id)
    if producto is None:
        raise ErrorAPI(status.HTTP_404_NOT_FOUND, "producto_no_encontrado", str(producto_id))
    return producto


def _guardar(db: Session, producto: Producto) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _codigo_duplicado(producto.codigo) from exc
    db.refresh(producto)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Alta de producto con talles, colores y alias",
)
def crear_producto(datos: ProductoCrear, db: DB) -> ProductoSalida:
    if db.scalar(select(Producto.id).where(Producto.codigo == datos.codigo)):
        raise _codigo_duplicado(datos.codigo)
    producto = Producto(**datos.model_dump())
    db.add(producto)
    _guardar(db, producto)
    return ProductoSalida.model_validate(producto)


@router.post(
    "/importar",
    summary="Alta o actualización masiva del catálogo desde CSV",
    description=(
        "Cabecera `codigo,nombre,categoria` y, opcionales, `talles,colores,alias,"
        "descripcion,activo`. Talles, colores y alias van separados por `|` "
        "(ej. `S|M|L`). Si el código existe se actualizan las columnas presentes; si no, "
        "se crea. Se validan todas las filas: si alguna falla no se guarda nada."
    ),
)
def importar_catalogo(
    db: DB,
    archivo: Annotated[UploadFile, File(description="Archivo .csv")],
) -> ImportacionCatalogoResultado:
    contenido = archivo.file.read(TAMANIO_MAXIMO + 1)
    if len(contenido) > TAMANIO_MAXIMO:
        raise ErrorAPI(
            status.HTTP_413_CONTENT_TOO_LARGE, "archivo_muy_grande", "El CSV supera los 2 MB."
        )
    resultado = validar_catalogo_csv(decodificar(contenido))
    if not resultado.es_valido:
        raise ErrorAPI(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "csv_invalido",
            [e.a_dict() for e in resultado.errores],
        )
    creados, actualizados = aplicar_catalogo(db, resultado)
    db.commit()  # todo el catálogo en una sola transacción
    return ImportacionCatalogoResultado(
        filas=len(resultado.filas), creados=creados, actualizados=actualizados
    )


@router.get("", summary="Catálogo, con filtros opcionales")
def listar_productos(
    db: DB,
    activo: bool | None = None,
    categoria: str | None = None,
    q: Annotated[str | None, Query(description="Busca en código y nombre")] = None,
) -> list[ProductoSalida]:
    consulta = select(Producto).order_by(Producto.codigo)
    if activo is not None:
        consulta = consulta.where(Producto.activo.is_(activo))
    if categoria:
        consulta = consulta.where(Producto.categoria == categoria.strip())
    if q:
        patron = f"%{q.strip()}%"
        consulta = consulta.where(or_(Producto.codigo.ilike(patron), Producto.nombre.ilike(patron)))
    return [ProductoSalida.model_validate(p) for p in db.scalars(consulta)]


@router.get("/{producto_id}", summary="Detalle de un producto")
def obtener_producto(producto_id: uuid.UUID, db: DB) -> ProductoSalida:
    return ProductoSalida.model_validate(_obtener(db, producto_id))


@router.patch("/{producto_id}", summary="Editar talles, colores, alias o desactivar")
def editar_producto(producto_id: uuid.UUID, datos: ProductoEditar, db: DB) -> ProductoSalida:
    producto = _obtener(db, producto_id)
    cambios = datos.model_dump(exclude_unset=True)

    for campo in ("codigo", "nombre", "categoria", "talles", "colores", "alias", "activo"):
        if campo in cambios and cambios[campo] is None:
            raise ErrorAPI(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "validacion",
                [{"campo": f"body.{campo}", "mensaje": "No puede ser null.", "tipo": "null"}],
            )

    nuevo_codigo = cambios.get("codigo")
    if (
        nuevo_codigo
        and nuevo_codigo != producto.codigo
        and db.scalar(select(Producto.id).where(Producto.codigo == nuevo_codigo))
    ):
        raise _codigo_duplicado(nuevo_codigo)

    for campo, valor in cambios.items():
        setattr(producto, campo, valor)
    _guardar(db, producto)
    return ProductoSalida.model_validate(producto)
