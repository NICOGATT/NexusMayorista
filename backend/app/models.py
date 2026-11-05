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
