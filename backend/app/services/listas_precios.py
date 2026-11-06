"""Operaciones sobre listas de precios que comparten la API y los scripts.

Ninguna hace commit: la transacción la cierra quien llama.
"""

from datetime import date

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import ListaPrecios, Precio, Producto
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
