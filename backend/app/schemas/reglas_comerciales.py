"""Esquemas de las reglas comerciales (respuestas de la fábrica)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.catalogo import Dinero


class ReglasEntrada(BaseModel):
    """Todas las respuestas. Un campo en null es una pregunta sin responder."""

    escala_por: Literal["producto", "item"] | None = None
    precios_incluyen_iva: bool | None = None
    alicuota_iva: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=2)
    iva_en_presupuesto: Literal["sumar", "aclarar"] | None = None
    pedido_minimo_unidades: int | None = Field(
        default=None, ge=0, le=1_000_000, description="0 = no hay mínimo"
    )
    pedido_minimo_monto: Decimal | None = Field(
        default=None,
        ge=0,
        le=Decimal("9999999999.99"),
        decimal_places=2,
        description="0 = no hay monto mínimo",
    )
    descuento_maximo_porcentaje: Decimal | None = Field(
        default=None, ge=0, le=100, decimal_places=2, description="100 = sin tope"
    )
    validez_dias: int | None = Field(default=None, gt=0, le=365)
    condiciones_pago: str | None = Field(default=None, max_length=2000)
    notas: str | None = Field(default=None, max_length=2000)
    confirmado_por: str | None = Field(default=None, max_length=200)
    confirmado_el: date | None = None

    @field_validator("condiciones_pago", "notas", "confirmado_por")
    @classmethod
    def _texto_vacio_es_null(cls, valor: str | None) -> str | None:
        return (valor or "").strip() or None


class PreguntaSalida(BaseModel):
    campo: str
    seccion: str
    pregunta: str
    ayuda: str
    impacto: str
    aplica: bool = Field(description="false si no hace falta responderla (depende de otra)")
    respondida: bool


class ReglasSalida(ReglasEntrada):
    alicuota_iva: Dinero | None = None
    pedido_minimo_monto: Dinero | None = None
    descuento_maximo_porcentaje: Dinero | None = None
    preguntas: list[PreguntaSalida]
    pendientes: int = Field(description="Preguntas que aplican y siguen sin respuesta")
    actualizado_por: str | None
    actualizado_en: datetime | None


class RespuestaFicha(BaseModel):
    seccion: str
    pregunta: str
    respuesta: str


class FichaSalida(BaseModel):
    titulo: str
    generada_el: date
    estado: str
    respuestas: list[RespuestaFicha]
    pendientes: list[str]
    notas: str | None
    texto_whatsapp: str = Field(description="Listo para pegar en WhatsApp")
