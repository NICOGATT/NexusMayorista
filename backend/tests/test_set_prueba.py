"""Set de prueba de HU-04 (`tests/fixtures/set_prueba.json`).

No llama a ninguna IA: controla que el set esté bien armado y que el resultado
esperado de cada caso coincida con lo que calcula el motor (HU-05). Así, cuando
el script de evaluación (día 7) compare la salida de la IA contra el set, una
diferencia es de la IA y no un error del set.
"""

import json
import uuid
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pytest

from app.ia.esquema import Intencion
from app.services.calculo import (
    EscalaPrecio,
    ItemPedido,
    ListaCalculo,
    ProductoInfo,
    calcular_presupuesto,
)

RUTA = Path(__file__).parent / "fixtures" / "set_prueba.json"
SET = json.loads(RUTA.read_text(encoding="utf-8"))
CASOS = SET["casos"]
CATALOGO = {p["codigo"]: p for p in SET["catalogo"]}


def lista_del_set() -> ListaCalculo:
    productos = {
        p["codigo"]: ProductoInfo(
            id=uuid.uuid5(uuid.NAMESPACE_URL, p["codigo"]),
            codigo=p["codigo"],
            nombre=p["nombre"],
            talles=frozenset(p["talles"]),
            colores=frozenset(p["colores"]),
        )
        for p in SET["catalogo"]
    }
    precios = [
        EscalaPrecio(
            producto_id=productos[f["codigo"]].id,
            talle=f["talle"],
            cantidad_minima=f["cantidad_minima"],
            precio_unitario=Decimal(f["precio_unitario"]),
        )
        for f in SET["precios"]
    ]
    return ListaCalculo(
        id=None,
        moneda="ARS",
        productos={p.id: p for p in productos.values()},
        precios=precios,
    )


LISTA = lista_del_set()


def test_tiene_30_casos_con_la_mezcla_del_plan():
    assert len(CASOS) == 30
    assert Counter(c["tipo"] for c in CASOS) == {
        "simple": 15,
        "complejo": 8,
        "fuera_de_lista": 4,
        "sin_pedido": 3,
    }


def test_ids_unicos_y_canales_validos():
    ids = [c["id"] for c in CASOS]
    assert len(ids) == len(set(ids))
    assert {c["canal"] for c in CASOS} <= {"whatsapp", "instagram"}
    assert all(c["texto"].strip() for c in CASOS)


def test_los_precios_del_set_son_los_del_ejemplo_cargado():
    """El set tiene que cotizar con la misma lista que está activa en staging."""
    raiz = Path(__file__).resolve().parents[2]
    csv = (raiz / "docs" / "ejemplos" / "lista-precios-ejemplo.csv").read_text(encoding="utf-8")
    filas = [linea.split(",") for linea in csv.strip().splitlines()[1:]]
    esperado = {(c, t or None, int(m), Decimal(p)) for c, t, m, p in filas}
    del_set = {
        (f["codigo"], f["talle"], f["cantidad_minima"], Decimal(f["precio_unitario"]))
        for f in SET["precios"]
    }
    assert del_set == esperado


@pytest.mark.parametrize("caso", CASOS, ids=lambda c: c["id"])
def test_esperado_coincide_con_el_motor(caso):
    esperado = caso["esperado"]
    items = esperado["items"]

    if not esperado["es_pedido"]:
        assert caso["tipo"] == "sin_pedido"
        assert items == []
        assert esperado["intencion"] in Intencion.__args__
        assert Decimal(esperado["subtotal"]) == 0
        return

    assert items, "un pedido tiene que tener al menos un ítem"
    for item in items:
        assert item["cantidad"] > 0
        if item["codigo"] is not None:
            assert item["codigo"] in CATALOGO
        if item["color"] is not None:
            assert item["color"] == item["color"].lower()

    resultado = calcular_presupuesto(
        [
            ItemPedido(
                cantidad=i["cantidad"], codigo=i["codigo"], talle=i["talle"], color=i["color"]
            )
            for i in items
        ],
        LISTA,
    )
    assert resultado.subtotal == Decimal(esperado["subtotal"])

    for item, calculado in zip(items, resultado.items, strict=True):
        if calculado.requiere_revision:
            # Lo que el motor marca, el esperado también lo tiene que marcar.
            assert item["requiere_revision"], calculado.motivos
        elif item["requiere_revision"]:
            # Única revisión que el motor no ve: un total sin repartir por talle.
            assert item["talle"] is None


def test_hay_casos_para_cada_regla_del_prompt():
    textos = " ".join(c["texto"].lower() for c in CASOS)
    for regla in ("docena", "media docena", "curva", "de cada talle", "small", "extra large"):
        assert regla in textos, regla
    assert any(i["talle"] == "XXL" for c in CASOS for i in c["esperado"]["items"])
    assert any(i["talle"] is None for c in CASOS for i in c["esperado"]["items"])
    assert any("ignorá" in c["texto"].lower() for c in CASOS)
