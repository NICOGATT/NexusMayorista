"""Esquemas de entrada y salida de catálogo y listas de precios."""

import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator

# Los importes viajan como número en el JSON (4500.0), como en el ejemplo de la API.
Dinero = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]

PATRON_CODIGO = re.compile(r"^[A-Z0-9][A-Z0-9._-]*$")


def normalizar_codigo(valor: str) -> str:
    codigo = valor.strip().upper()
    if not PATRON_CODIGO.fullmatch(codigo):
        raise ValueError("Solo letras, números, '.', '_' o '-', sin espacios (ej. REM-ALG-LISA).")
    return codigo


def _sin_repetidos(valores: list[str], transformar) -> list[str]:
    vistos: list[str] = []
    for v in valores:
        limpio = transformar(v.strip())
        if limpio and limpio not in vistos:
            vistos.append(limpio)
    return vistos


def normalizar_talles(valores: list[str]) -> list[str]:
    return _sin_repetidos(valores, str.upper)


def normalizar_minusculas(valores: list[str]) -> list[str]:
    return _sin_repetidos(valores, str.lower)


# ------------------------------------------------------------------ productos


class _ProductoCampos(BaseModel):
    @field_validator("codigo", check_fields=False)
    @classmethod
    def _codigo(cls, v: str | None) -> str | None:
        return None if v is None else normalizar_codigo(v)

    @field_validator("nombre", "categoria", check_fields=False)
    @classmethod
    def _texto_obligatorio(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not v.strip():
            raise ValueError("No puede estar vacío.")
        return v.strip()

    @field_validator("talles", check_fields=False)
    @classmethod
    def _talles(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else normalizar_talles(v)

    @field_validator("colores", "alias", check_fields=False)
    @classmethod
    def _minusculas(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else normalizar_minusculas(v)


class ProductoCrear(_ProductoCampos):
    codigo: str = Field(max_length=50, examples=["REM-ALG-LISA"])
    nombre: str = Field(max_length=200, examples=["Remera algodón lisa"])
    categoria: str = Field(max_length=100, examples=["remeras"])
    descripcion: str | None = None
    talles: list[str] = Field(default_factory=list, examples=[["S", "M", "L", "XL"]])
    colores: list[str] = Field(default_factory=list, examples=[["negro", "blanco"]])
    alias: list[str] = Field(default_factory=list, examples=[["remera lisa", "remerita básica"]])
    activo: bool = True


class ProductoEditar(_ProductoCampos):
    """Todos los campos son opcionales: solo se cambia lo que se envía."""

    codigo: str | None = Field(default=None, max_length=50)
    nombre: str | None = Field(default=None, max_length=200)
    categoria: str | None = Field(default=None, max_length=100)
    descripcion: str | None = None
    talles: list[str] | None = None
    colores: list[str] | None = None
    alias: list[str] | None = None
    activo: bool | None = None


class ProductoSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    codigo: str
    nombre: str
    categoria: str
    descripcion: str | None
    talles: list[str]
    colores: list[str]
    alias: list[str]
    activo: bool
    creado_en: datetime | None = None
    actualizado_en: datetime | None = None


# ----------------------------------------------------------- listas de precios


class ListaPreciosSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str
    moneda: str
    vigente_desde: date
    vigente_hasta: date | None
    activa: bool
    creado_en: datetime | None = None


class PrecioSalida(BaseModel):
    id: uuid.UUID
    producto_id: uuid.UUID
    codigo: str
    producto: str
    talle: str | None
    cantidad_minima: int
    precio_unitario: Dinero


class ListaPreciosDetalle(ListaPreciosSalida):
    precios: list[PrecioSalida]


class ImportacionResultado(BaseModel):
    lista: ListaPreciosSalida
    filas_cargadas: int
