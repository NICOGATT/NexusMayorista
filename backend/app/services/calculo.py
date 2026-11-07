"""Motor de cálculo de presupuestos (HU-05).

Función pura: recibe los ítems y una foto de la lista de precios, y devuelve
importes exactos. No toca la base, así se prueba con tests unitarios y es la
única fuente de verdad de los importes (la IA nunca fija un precio).

Reglas (sección 4 de la documentación técnica):

1. La escala se elige por la cantidad TOTAL del producto en el pedido, sumando
   talles y colores (`EscalaPor.PRODUCTO`). Es una pregunta abierta con la
   fábrica; si responde "por ítem", se cambia con `escala_por=EscalaPor.ITEM`.
2. Dentro de esa cantidad se usa la fila con la mayor `cantidad_minima` que no
   la supere.
3. Si el talle del ítem tiene filas propias aplicables, mandan sobre las
   generales (talle vacío). Si no, se usan las generales.
4. Un ítem sin producto, con un talle que el producto no tiene o sin precio en
   la lista no suma al total y marca el presupuesto para revisión.
5. Si la IA propuso un precio distinto del calculado, queda el del sistema y el
   ítem se marca con "diferencia de precio IA vs. lista".
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

CENTAVO = Decimal("0.01")


class EscalaPor(StrEnum):
    PRODUCTO = "producto"
    ITEM = "item"


# ----------------------------------------------------------------- entradas


@dataclass(frozen=True)
class ProductoInfo:
    id: uuid.UUID
    codigo: str
    nombre: str
    talles: frozenset[str] = frozenset()
    colores: frozenset[str] = frozenset()
    activo: bool = True


@dataclass(frozen=True)
class EscalaPrecio:
    producto_id: uuid.UUID
    talle: str | None
    cantidad_minima: int
    precio_unitario: Decimal


@dataclass(frozen=True)
class ListaCalculo:
    """Foto de la lista de precios con los productos que hacen falta."""

    id: uuid.UUID | None
    moneda: str
    productos: dict[uuid.UUID, ProductoInfo]
    precios: list[EscalaPrecio]

    def producto_por_codigo(self, codigo: str) -> ProductoInfo | None:
        codigo = codigo.strip().upper()
        return next((p for p in self.productos.values() if p.codigo == codigo), None)


@dataclass(frozen=True)
class ItemPedido:
    cantidad: int
    producto_id: uuid.UUID | None = None
    codigo: str | None = None
    talle: str | None = None
    color: str | None = None
    descripcion_original: str | None = None
    precio_propuesto: Decimal | None = None  # lo que dijo la IA, solo para comparar


# ------------------------------------------------------------------- salidas


@dataclass
class ItemCalculado:
    cantidad: int
    producto_id: uuid.UUID | None
    codigo: str | None
    producto: str | None
    talle: str | None
    color: str | None
    descripcion_original: str | None
    precio_unitario: Decimal | None = None
    subtotal: Decimal | None = None
    cantidad_escala: int | None = None  # cantidad usada para elegir la escala
    escala_minima: int | None = None  # cantidad_minima de la fila aplicada
    requiere_revision: bool = False
    motivos: list[str] = field(default_factory=list)

    def marcar(self, motivo: str) -> None:
        self.requiere_revision = True
        self.motivos.append(motivo)


@dataclass
class PresupuestoCalculado:
    lista_id: uuid.UUID | None
    moneda: str
    items: list[ItemCalculado]
    total_unidades: int
    subtotal: Decimal
    descuento: Decimal
    total: Decimal
    requiere_revision: bool
    advertencias: list[str] = field(default_factory=list)


class ErrorCalculo(ValueError):
    """Datos de entrada imposibles de calcular (no es un ítem a revisar)."""


# -------------------------------------------------------------------- motor


def _normalizar_talle(talle: str | None) -> str | None:
    return (talle.strip().upper() or None) if talle else None


def _normalizar_color(color: str | None) -> str | None:
    return (color.strip().lower() or None) if color else None


def elegir_precio(
    filas: list[EscalaPrecio], talle: str | None, cantidad: int
) -> EscalaPrecio | None:
    """Fila de precio que corresponde a un talle y una cantidad (reglas 2 y 3)."""

    def mejor(candidatas: list[EscalaPrecio]) -> EscalaPrecio | None:
        aplicables = [f for f in candidatas if f.cantidad_minima <= cantidad]
        return max(aplicables, key=lambda f: f.cantidad_minima, default=None)

    if talle:
        propia = mejor([f for f in filas if f.talle == talle])
        if propia:
            return propia
    return mejor([f for f in filas if f.talle is None])


def _monto_descuento(
    subtotal: Decimal, descuento: Decimal | None, descuento_porcentaje: Decimal | None
) -> Decimal:
    if descuento is not None and descuento_porcentaje is not None:
        raise ErrorCalculo("Indicá el descuento como monto o como porcentaje, no los dos.")
    if descuento_porcentaje is not None:
        if not Decimal(0) <= descuento_porcentaje <= Decimal(100):
            raise ErrorCalculo("El porcentaje de descuento debe estar entre 0 y 100.")
        return (subtotal * descuento_porcentaje / 100).quantize(CENTAVO, ROUND_HALF_UP)
    monto = (descuento or Decimal(0)).quantize(CENTAVO, ROUND_HALF_UP)
    if monto < 0:
        raise ErrorCalculo("El descuento no puede ser negativo.")
    if monto > subtotal:
        raise ErrorCalculo(f"El descuento ({monto}) supera el subtotal ({subtotal}).")
    return monto


def calcular_presupuesto(
    items: list[ItemPedido],
    lista: ListaCalculo,
    *,
    descuento: Decimal | None = None,
    descuento_porcentaje: Decimal | None = None,
    escala_por: EscalaPor = EscalaPor.PRODUCTO,
) -> PresupuestoCalculado:
    precios_por_producto: dict[uuid.UUID, list[EscalaPrecio]] = defaultdict(list)
    for fila in lista.precios:
        precios_por_producto[fila.producto_id].append(fila)

    # 1) Resolver producto, talle y color de cada ítem.
    calculados: list[ItemCalculado] = []
    resueltos: list[tuple[ItemCalculado, ProductoInfo]] = []
    for item in items:
        if item.cantidad <= 0:
            raise ErrorCalculo("La cantidad de cada ítem debe ser mayor a 0.")

        producto = None
        if item.producto_id is not None:
            producto = lista.productos.get(item.producto_id)
        elif item.codigo:
            producto = lista.producto_por_codigo(item.codigo)

        calc = ItemCalculado(
            cantidad=item.cantidad,
            producto_id=producto.id if producto else item.producto_id,
            codigo=producto.codigo if producto else (item.codigo or None),
            producto=producto.nombre if producto else None,
            talle=_normalizar_talle(item.talle),
            color=_normalizar_color(item.color),
            descripcion_original=item.descripcion_original,
        )
        calculados.append(calc)

        if producto is None:
            if item.producto_id is None and not item.codigo:
                calc.marcar("Producto no reconocido.")
            else:
                calc.marcar("El producto no existe en el catálogo.")
            continue
        if not producto.activo:
            calc.marcar("El producto está inactivo en el catálogo.")
        if calc.color and producto.colores and calc.color not in producto.colores:
            calc.marcar(f"El color {calc.color} no está en el producto.")
        if calc.talle and producto.talles and calc.talle not in producto.talles:
            calc.marcar(f"El talle {calc.talle} no está en el producto.")
            continue
        if not precios_por_producto.get(producto.id):
            calc.marcar("El producto no tiene precio en esta lista.")
            continue
        resueltos.append((calc, producto))

    # 2) Cantidad que define la escala (regla 1).
    total_por_producto: dict[uuid.UUID, int] = defaultdict(int)
    for calc, producto in resueltos:
        total_por_producto[producto.id] += calc.cantidad

    # 3) Precio de cada ítem resuelto.
    for calc, producto in resueltos:
        cantidad_escala = (
            total_por_producto[producto.id] if escala_por == EscalaPor.PRODUCTO else calc.cantidad
        )
        fila = elegir_precio(precios_por_producto[producto.id], calc.talle, cantidad_escala)
        if fila is None:
            minimo = min(f.cantidad_minima for f in precios_por_producto[producto.id])
            calc.marcar(f"La cantidad no alcanza el mínimo de la lista ({minimo} unidades).")
            continue
        calc.cantidad_escala = cantidad_escala
        calc.escala_minima = fila.cantidad_minima
        calc.precio_unitario = fila.precio_unitario.quantize(CENTAVO)
        calc.subtotal = calc.precio_unitario * calc.cantidad

    # 4) Comparar con el precio que propuso la IA (regla 5).
    for calc, item in zip(calculados, items, strict=True):
        if (
            item.precio_propuesto is not None
            and calc.precio_unitario is not None
            and item.precio_propuesto.quantize(CENTAVO) != calc.precio_unitario
        ):
            calc.marcar(
                f"Diferencia de precio IA vs. lista: la IA propuso {item.precio_propuesto}, "
                f"la lista dice {calc.precio_unitario}."
            )

    subtotal = sum((c.subtotal for c in calculados if c.subtotal is not None), Decimal("0.00"))
    monto_descuento = _monto_descuento(subtotal, descuento, descuento_porcentaje)
    requiere_revision = any(c.requiere_revision for c in calculados)

    advertencias = []
    sin_precio = sum(1 for c in calculados if c.subtotal is None)
    if sin_precio:
        advertencias.append(f"{sin_precio} ítem(s) sin precio: no suman al total.")
    if not calculados:
        advertencias.append("El pedido no tiene ítems.")

    return PresupuestoCalculado(
        lista_id=lista.id,
        moneda=lista.moneda,
        items=calculados,
        total_unidades=sum(c.cantidad for c in calculados),
        subtotal=subtotal.quantize(CENTAVO),
        descuento=monto_descuento,
        total=(subtotal - monto_descuento).quantize(CENTAVO),
        requiere_revision=requiere_revision or not calculados,
        advertencias=advertencias,
    )
