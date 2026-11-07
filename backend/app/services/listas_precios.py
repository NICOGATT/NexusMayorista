"""Operaciones sobre listas de precios que comparten la API y los scripts.

Ninguna hace commit: la transacción la cierra quien llama.
"""

import uuid
from datetime import date

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.models import ListaPrecios, Precio, Producto
from app.services.calculo import EscalaPrecio, ListaCalculo, ProductoInfo
from app.services.importar_csv import ProductoCatalogo, ResultadoValidacion


def catalogo_por_codigo(db: Session) -> dict[str, ProductoCatalogo]:
    """Índice del catálogo por código en mayúsculas, como lo espera `validar_csv`."""
    return {
        p.codigo.upper(): ProductoCatalogo(id=p.id, codigo=p.codigo, talles=frozenset(p.talles))
        for p in db.scalars(select(Producto))
    }


def crear_lista(
    db: Session,
    resultado: ResultadoValidacion,
    *,
    nombre: str,
    vigente_desde: date,
    vigente_hasta: date | None = None,
    moneda: str = "ARS",
) -> ListaPrecios:
    """Agrega una lista nueva, inactiva, con todas las escalas validadas."""
    lista = ListaPrecios(
        nombre=nombre,
        moneda=moneda.upper(),
        vigente_desde=vigente_desde,
        vigente_hasta=vigente_hasta,
        activa=False,
        precios=[
            Precio(
                producto_id=f.producto_id,
                talle=f.talle,
                cantidad_minima=f.cantidad_minima,
                precio_unitario=f.precio_unitario,
            )
            for f in resultado.filas
        ],
    )
    db.add(lista)
    db.flush()
    return lista


def activar(db: Session, lista: ListaPrecios) -> None:
    """Desactiva cualquier otra lista activa y activa esta (en la misma transacción)."""
    if lista.activa:
        return
    db.execute(
        update(ListaPrecios)
        .where(ListaPrecios.activa.is_(True), ListaPrecios.id != lista.id)
        .values(activa=False)
    )
    lista.activa = True
    db.flush()


def lista_para_calculo(
    db: Session,
    lista: ListaPrecios,
    producto_ids: set[uuid.UUID],
    codigos: set[str],
) -> ListaCalculo:
    """Foto de la lista con solo los productos que pide el presupuesto."""
    condiciones = []
    if producto_ids:
        condiciones.append(Producto.id.in_(producto_ids))
    if codigos:
        condiciones.append(Producto.codigo.in_({c.strip().upper() for c in codigos}))
    productos = list(db.scalars(select(Producto).where(or_(*condiciones)))) if condiciones else []

    filas = (
        db.scalars(
            select(Precio).where(
                Precio.lista_id == lista.id,
                Precio.producto_id.in_([p.id for p in productos]),
            )
        )
        if productos
        else []
    )
    return ListaCalculo(
        id=lista.id,
        moneda=lista.moneda,
        productos={
            p.id: ProductoInfo(
                id=p.id,
                codigo=p.codigo,
                nombre=p.nombre,
                talles=frozenset(p.talles),
                colores=frozenset(p.colores),
                activo=p.activo,
            )
            for p in productos
        },
        precios=[
            EscalaPrecio(
                producto_id=f.producto_id,
                talle=f.talle,
                cantidad_minima=f.cantidad_minima,
                precio_unitario=f.precio_unitario,
            )
            for f in filas
        ],
    )
