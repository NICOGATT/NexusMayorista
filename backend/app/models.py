"""Modelos ORM. Reflejan la migración 0001; la base real es la de Supabase.

Los tipos tienen variante para SQLite (ARRAY -> JSON) y los valores por defecto se
generan en Python, así los tests corren sin Postgres. En Postgres la migración
además define sus propios defaults, triggers y RLS.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

ListaTexto = ARRAY(Text).with_variant(JSON(), "sqlite")


class Producto(Base):
    __tablename__ = "productos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    codigo: Mapped[str] = mapped_column(Text, unique=True, comment="SKU base, ej. REM-ALG-LISA")
    nombre: Mapped[str] = mapped_column(Text)
    categoria: Mapped[str] = mapped_column(Text)
    descripcion: Mapped[str | None] = mapped_column(Text)
    talles: Mapped[list[str]] = mapped_column(ListaTexto, default=list)
    colores: Mapped[list[str]] = mapped_column(ListaTexto, default=list)
    alias: Mapped[list[str]] = mapped_column(
        ListaTexto, default=list, comment="Sinónimos que usan los clientes"
    )
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ListaPrecios(Base):
    __tablename__ = "listas_precios"
    __table_args__ = (
        # Solo una lista activa a la vez (índice único parcial).
        Index(
            "ux_listas_precios_unica_activa",
            "activa",
            unique=True,
            postgresql_where=text("activa"),
            sqlite_where=text("activa"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(Text)
    moneda: Mapped[str] = mapped_column(CHAR(3), default="ARS")
    vigente_desde: Mapped[date] = mapped_column(Date)
    vigente_hasta: Mapped[date | None] = mapped_column(Date)
    activa: Mapped[bool] = mapped_column(Boolean, default=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    precios: Mapped[list["Precio"]] = relationship(
        back_populates="lista",
        cascade="all, delete-orphan",
        order_by="Precio.cantidad_minima",
    )


class Precio(Base):
    __tablename__ = "precios"
    __table_args__ = (
        CheckConstraint("cantidad_minima > 0", name="precios_cantidad_minima_check"),
        CheckConstraint("precio_unitario >= 0", name="precios_precio_unitario_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    lista_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("listas_precios.id", ondelete="CASCADE"))
    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("productos.id"))
    talle: Mapped[str | None] = mapped_column(Text, comment="null = aplica a todos los talles")
    cantidad_minima: Mapped[int] = mapped_column(Integer, default=1)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    lista: Mapped[ListaPrecios] = relationship(back_populates="precios")
    producto: Mapped[Producto] = relationship()


# Escalas: mismo producto/talle con distintos mínimos (1, 12, 50 unidades...).
Index(
    "ux_precios_escala",
    Precio.lista_id,
    Precio.producto_id,
    func.coalesce(Precio.talle, ""),
    Precio.cantidad_minima,
    unique=True,
)


class ReglasComerciales(Base):
    """Definiciones de la fábrica que cambian cómo se calcula un presupuesto.

    Una sola fila (id = 1). Cada campo en null significa "la fábrica todavía no
    respondió": el motor usa entonces el comportamiento por defecto.
    """

    __tablename__ = "reglas_comerciales"
    __table_args__ = (
        CheckConstraint("id = 1", name="reglas_comerciales_fila_unica"),
        CheckConstraint(
            "escala_por in ('producto', 'item')", name="reglas_comerciales_escala_por_check"
        ),
        CheckConstraint(
            "iva_en_presupuesto in ('sumar', 'aclarar')",
            name="reglas_comerciales_iva_en_presupuesto_check",
        ),
        CheckConstraint(
            "alicuota_iva >= 0 and alicuota_iva <= 100",
            name="reglas_comerciales_alicuota_iva_check",
        ),
        CheckConstraint(
            "descuento_maximo_porcentaje >= 0 and descuento_maximo_porcentaje <= 100",
            name="reglas_comerciales_descuento_maximo_check",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    escala_por: Mapped[str | None] = mapped_column(Text, comment="producto | item")
    precios_incluyen_iva: Mapped[bool | None] = mapped_column(Boolean)
    alicuota_iva: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    iva_en_presupuesto: Mapped[str | None] = mapped_column(
        Text, comment="Si los precios no incluyen IVA: sumar | aclarar"
    )
    pedido_minimo_unidades: Mapped[int | None] = mapped_column(Integer)
    pedido_minimo_monto: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    descuento_maximo_porcentaje: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    validez_dias: Mapped[int | None] = mapped_column(Integer)
    condiciones_pago: Mapped[str | None] = mapped_column(Text)
    notas: Mapped[str | None] = mapped_column(Text)
    confirmado_por: Mapped[str | None] = mapped_column(
        Text, comment="Quién de la fábrica confirmó las respuestas"
    )
    confirmado_el: Mapped[date | None] = mapped_column(Date)
    actualizado_por: Mapped[str | None] = mapped_column(Text)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
