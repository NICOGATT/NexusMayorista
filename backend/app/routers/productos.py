import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.errores import ErrorAPI
from app.models import Producto
from app.schemas.catalogo import ProductoCrear, ProductoEditar, ProductoSalida

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
