"""Esquemas de entrada y salida del cálculo de presupuestos (HU-05)."""

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.schemas.catalogo import Dinero


class ItemCalcular(BaseModel):
    producto_id: uuid.UUID | None = Field(default=None, description="Id del producto")
    codigo: str | None = Field(
        default=None, max_length=50, description="Alternativa a producto_id", examples=["BUZ-CANG"]
    )
    talle: str | None = Field(default=None, max_length=20, examples=["XL"])
    color: str | None = Field(default=None, max_length=50, examples=["gris"])
    cantidad: int = Field(gt=0, le=100_000, examples=[10])
    descripcion_original: str | None = Field(
        default=None, max_length=500, examples=["10 buzos canguro gris talle XL"]
    )
    precio_propuesto: Decimal | None = Field(
        default=None,
        ge=0,
        description="Precio que propuso la IA; si difiere, el ítem se marca para revisión.",
    )


class PresupuestoCalcular(BaseModel):
    lista_id: uuid.UUID | None = Field(
        default=None, description="Lista de precios a usar; por defecto, la activa"
    )
    items: list[ItemCalcular] = Field(min_length=1, max_length=200)
    descuento: Decimal | None = Field(default=None, ge=0, description="Monto fijo")
    descuento_porcentaje: Decimal | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def _un_solo_descuento(self) -> "PresupuestoCalcular":
        if self.descuento is not None and self.descuento_porcentaje is not None:
            raise ValueError("Indicá el descuento como monto o como porcentaje, no los dos.")
        return self


class ItemCalculadoSalida(BaseModel):
    producto_id: uuid.UUID | None
    codigo: str | None
    producto: str | None
    descripcion_original: str | None
    talle: str | None
    color: str | None
    cantidad: int
    precio_unitario: Dinero | None
    subtotal: Dinero | None
    cantidad_escala: int | None = Field(description="Unidades usadas para elegir la escala")
    escala_minima: int | None = Field(description="cantidad_minima de la escala aplicada")
    requiere_revision: bool
    motivos: list[str]


class PresupuestoCalculadoSalida(BaseModel):
    lista_id: uuid.UUID | None
    moneda: str
    items: list[ItemCalculadoSalida]
    total_unidades: int
    subtotal: Dinero
    descuento: Dinero
    iva: Dinero = Field(description="IVA sumado al total; 0 si no corresponde sumarlo")
    total: Dinero
    leyenda_iva: str | None = Field(
        description="Cómo leer los importes respecto del IVA, según las reglas comerciales"
    )
    requiere_revision: bool
    advertencias: list[str]
