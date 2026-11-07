"""HU-05 · Motor de cálculo (función pura, sin base).

Lista de ejemplo (docs/ejemplos/lista-precios-ejemplo.csv):
    REM-ALG-LISA  general   1 → 5000 · 12 → 4500 · 50 → 4200
    BUZ-CANG      general   1 → 16500 · 10 → 15800
    BUZ-CANG      XXL       1 → 17500
"""

import uuid
from decimal import Decimal

import pytest

from app.services.calculo import (
    ErrorCalculo,
    EscalaPor,
    EscalaPrecio,
    ItemPedido,
    ListaCalculo,
    ProductoInfo,
    calcular_presupuesto,
    elegir_precio,
)

REMERA = ProductoInfo(
    uuid.uuid4(),
    "REM-ALG-LISA",
    "Remera algodón lisa",
    talles=frozenset({"S", "M", "L", "XL"}),
    colores=frozenset({"negro", "blanco"}),
)
BUZO = ProductoInfo(
    uuid.uuid4(), "BUZ-CANG", "Buzo canguro", talles=frozenset({"M", "L", "XL", "XXL"})
)
SIN_PRECIO = ProductoInfo(uuid.uuid4(), "PAN-JOG", "Pantalón jogger")


def escala(producto: ProductoInfo, talle: str | None, minimo: int, precio: str) -> EscalaPrecio:
    return EscalaPrecio(producto.id, talle, minimo, Decimal(precio))


LISTA = ListaCalculo(
    id=uuid.uuid4(),
    moneda="ARS",
    productos={p.id: p for p in (REMERA, BUZO, SIN_PRECIO)},
    precios=[
        escala(REMERA, None, 1, "5000"),
        escala(REMERA, None, 12, "4500"),
        escala(REMERA, None, 50, "4200"),
        escala(BUZO, None, 1, "16500"),
        escala(BUZO, None, 10, "15800"),
        escala(BUZO, "XXL", 1, "17500"),
    ],
)


def remeras(cantidad: int, talle: str | None = "M", **kw) -> ItemPedido:
    return ItemPedido(cantidad=cantidad, producto_id=REMERA.id, talle=talle, **kw)


# ------------------------------------------------- escalas (bordes del plan)


@pytest.mark.parametrize(
    ("cantidad", "precio", "minimo"),
    [
        (1, "5000.00", 1),
        (11, "5000.00", 1),
        (12, "4500.00", 12),
        (49, "4500.00", 12),
        (50, "4200.00", 50),
        (500, "4200.00", 50),
    ],
)
def test_bordes_de_escala(cantidad: int, precio: str, minimo: int) -> None:
    resultado = calcular_presupuesto([remeras(cantidad)], LISTA)

    item = resultado.items[0]
    assert item.precio_unitario == Decimal(precio)
    assert item.escala_minima == minimo
    assert item.subtotal == Decimal(precio) * cantidad
    assert resultado.total == item.subtotal
    assert not resultado.requiere_revision


def test_criterio_1_la_escala_se_elige_por_el_total_del_producto() -> None:
    """24 remeras (12 M + 12 L) → escala de 12 a $4.500, subtotal $108.000."""
    resultado = calcular_presupuesto([remeras(12, "M"), remeras(12, "L")], LISTA)

    assert [i.precio_unitario for i in resultado.items] == [Decimal("4500.00")] * 2
    assert [i.cantidad_escala for i in resultado.items] == [24, 24]
    assert resultado.subtotal == Decimal("108000.00")
    assert resultado.total_unidades == 24


def test_talles_y_colores_suman_para_la_escala_pero_otro_producto_no() -> None:
    resultado = calcular_presupuesto(
        [
            remeras(6, "S", color="negro"),
            remeras(6, "S", color="blanco"),
            ItemPedido(cantidad=40, producto_id=BUZO.id, talle="L"),
        ],
        LISTA,
    )

    assert [i.precio_unitario for i in resultado.items[:2]] == [Decimal("4500.00")] * 2
    assert resultado.items[2].precio_unitario == Decimal("15800.00")


def test_escala_por_item_si_la_fabrica_lo_decide() -> None:
    resultado = calcular_presupuesto(
        [remeras(12, "M"), remeras(12, "L")], LISTA, escala_por=EscalaPor.ITEM
    )
    assert [i.precio_unitario for i in resultado.items] == [Decimal("4500.00")] * 2

    resultado = calcular_presupuesto(
        [remeras(6, "M"), remeras(6, "L")], LISTA, escala_por=EscalaPor.ITEM
    )
    assert [i.precio_unitario for i in resultado.items] == [Decimal("5000.00")] * 2


# ----------------------------------------------------------- precio por talle


def test_criterio_2_precio_por_talle_manda_sobre_el_general() -> None:
    resultado = calcular_presupuesto(
        [
            ItemPedido(cantidad=10, producto_id=BUZO.id, talle="XL"),
            ItemPedido(cantidad=5, producto_id=BUZO.id, talle="XXL"),
        ],
        LISTA,
    )

    xl, xxl = resultado.items
    assert xl.precio_unitario == Decimal("15800.00")  # escala general de 10 (15 en total)
    assert xxl.precio_unitario == Decimal("17500.00")  # fila propia del XXL
    assert resultado.subtotal == Decimal("158000.00") + Decimal("87500.00")


def test_item_sin_talle_usa_el_precio_general() -> None:
    resultado = calcular_presupuesto([ItemPedido(cantidad=2, producto_id=BUZO.id)], LISTA)
    assert resultado.items[0].precio_unitario == Decimal("16500.00")


def test_elegir_precio_cae_al_general_si_la_fila_del_talle_no_aplica() -> None:
    filas = [escala(BUZO, None, 1, "100"), escala(BUZO, "XXL", 20, "90")]

    assert elegir_precio(filas, "XXL", 5).precio_unitario == Decimal("100")
    assert elegir_precio(filas, "XXL", 20).precio_unitario == Decimal("90")


# ------------------------------------------------------------ ítems a revisar


def test_criterio_3_item_sin_producto_no_suma_y_marca_revision() -> None:
    resultado = calcular_presupuesto(
        [remeras(12), ItemPedido(cantidad=1, descripcion_original="1 curva de jogger")],
        LISTA,
    )

    sin_producto = resultado.items[1]
    assert sin_producto.precio_unitario is None
    assert sin_producto.subtotal is None
    assert sin_producto.requiere_revision
    assert sin_producto.motivos == ["Producto no reconocido."]
    assert resultado.subtotal == Decimal("54000.00")
    assert resultado.total_unidades == 13
    assert resultado.requiere_revision
    assert resultado.advertencias == ["1 ítem(s) sin precio: no suman al total."]


def test_item_sin_producto_no_cuenta_para_la_escala() -> None:
    resultado = calcular_presupuesto(
        [remeras(6), ItemPedido(cantidad=6, codigo="NO-EXISTE")], LISTA
    )
    assert resultado.items[0].precio_unitario == Decimal("5000.00")
    assert resultado.items[1].motivos == ["El producto no existe en el catálogo."]


def test_talle_inexistente_no_tiene_precio() -> None:
    resultado = calcular_presupuesto([remeras(12, "XXXL")], LISTA)

    item = resultado.items[0]
    assert item.subtotal is None
    assert item.motivos == ["El talle XXXL no está en el producto."]
    assert resultado.total == 0


def test_color_inexistente_tiene_precio_pero_marca_revision() -> None:
    resultado = calcular_presupuesto([remeras(1, color="Fucsia")], LISTA)

    item = resultado.items[0]
    assert item.color == "fucsia"
    assert item.precio_unitario == Decimal("5000.00")
    assert item.motivos == ["El color fucsia no está en el producto."]


def test_producto_sin_precio_en_la_lista() -> None:
    resultado = calcular_presupuesto([ItemPedido(cantidad=3, codigo="pan-jog")], LISTA)

    assert resultado.items[0].codigo == "PAN-JOG"
    assert resultado.items[0].motivos == ["El producto no tiene precio en esta lista."]


def test_cantidad_por_debajo_de_la_escala_minima() -> None:
    lista = ListaCalculo(LISTA.id, "ARS", {REMERA.id: REMERA}, [escala(REMERA, None, 6, "5000")])
    resultado = calcular_presupuesto([remeras(3)], lista)

    assert resultado.items[0].motivos == [
        "La cantidad no alcanza el mínimo de la lista (6 unidades)."
    ]


def test_producto_inactivo_se_calcula_pero_marca_revision() -> None:
    inactivo = ProductoInfo(REMERA.id, REMERA.codigo, REMERA.nombre, activo=False)
    lista = ListaCalculo(LISTA.id, "ARS", {REMERA.id: inactivo}, LISTA.precios)

    resultado = calcular_presupuesto([remeras(1, talle=None)], lista)

    assert resultado.items[0].precio_unitario == Decimal("5000.00")
    assert resultado.requiere_revision


def test_criterio_4_diferencia_de_precio_ia_vs_lista() -> None:
    resultado = calcular_presupuesto(
        [
            remeras(12, "M", precio_propuesto=Decimal("4500")),  # coincide
            remeras(12, "L", precio_propuesto=Decimal("5000")),  # la IA usó otra escala
        ],
        LISTA,
    )

    bien, mal = resultado.items
    assert not bien.requiere_revision
    assert mal.precio_unitario == Decimal("4500.00")  # queda el del sistema
    assert mal.motivos[0].startswith("Diferencia de precio IA vs. lista")
    assert resultado.subtotal == Decimal("108000.00")


# ----------------------------------------------------------------- descuentos


def test_total_con_descuento_en_monto() -> None:
    resultado = calcular_presupuesto([remeras(12)], LISTA, descuento=Decimal("4000"))

    assert resultado.subtotal == Decimal("54000.00")
    assert resultado.descuento == Decimal("4000.00")
    assert resultado.total == Decimal("50000.00")


def test_total_con_descuento_porcentual_redondea_al_centavo() -> None:
    # 3 × 4.999,99 = 14.999,97 → 7 % = 1.049,9979 → 1.050,00
    lista = ListaCalculo(LISTA.id, "ARS", {REMERA.id: REMERA}, [escala(REMERA, None, 1, "4999.99")])
    resultado = calcular_presupuesto([remeras(3)], lista, descuento_porcentaje=Decimal("7"))

    assert resultado.subtotal == Decimal("14999.97")
    assert resultado.descuento == Decimal("1050.00")
    assert resultado.total == Decimal("13949.97")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"descuento": Decimal("60000")},  # supera el subtotal
        {"descuento": Decimal("-1")},
        {"descuento_porcentaje": Decimal("101")},
        {"descuento": Decimal("1"), "descuento_porcentaje": Decimal("1")},
    ],
)
def test_descuentos_invalidos(kwargs) -> None:
    with pytest.raises(ErrorCalculo):
        calcular_presupuesto([remeras(12)], LISTA, **kwargs)


def test_cantidad_cero_es_error() -> None:
    with pytest.raises(ErrorCalculo):
        calcular_presupuesto([remeras(0)], LISTA)


def test_los_importes_son_exactos_al_centavo() -> None:
    lista = ListaCalculo(LISTA.id, "ARS", {REMERA.id: REMERA}, [escala(REMERA, None, 1, "0.10")])
    resultado = calcular_presupuesto([remeras(3, "S"), remeras(3, "M")], lista)

    assert resultado.total == Decimal("0.60")  # con float daría 0.6000000000000001
