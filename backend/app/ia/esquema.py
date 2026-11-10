"""Salida estructurada de la IA (sección 4 de la documentación técnica).

El mismo esquema sirve para Claude (`messages.parse`) y para Ollama (`format` con
`PedidoExtraido.model_json_schema()`). Los importes que trae son solo una
referencia: el motor de cálculo (`app/services/calculo.py`) los vuelve a calcular
y marca cualquier diferencia.
"""

from typing import Literal

from pydantic import BaseModel, Field

Intencion = Literal["pedido", "consulta_precio", "consulta_general", "otro"]


class DatosCliente(BaseModel):
    nombre: str | None = Field(description="Nombre de pila o como firma el cliente")
    ciudad: str | None
    provincia: str | None
    razon_social: str | None


class ItemPedido(BaseModel):
    descripcion_original: str = Field(description="Fragmento literal del mensaje")
    codigo_producto: str | None = Field(
        description="Código de la lista de precios, o null si no se reconoció"
    )
    talle: str | None = Field(description="Talle en el formato de la lista, o null")
    color: str | None = Field(description="Color en minúscula y singular, o null")
    cantidad: int = Field(description="Unidades de esta combinación de producto, talle y color")
    precio_unitario: float | None
    subtotal: float | None
    confianza: float = Field(description="Entre 0 y 1")
    requiere_revision: bool
    motivo_revision: str | None


class PedidoExtraido(BaseModel):
    es_pedido: bool
    intencion: Intencion
    items: list[ItemPedido]
    total_unidades: int
    subtotal: float
    moneda: str
    requiere_revision: bool
    preguntas_para_cliente: list[str]
    datos_cliente: DatosCliente
    resumen: str = Field(description="Una o dos líneas para la tarjeta del tablero")
