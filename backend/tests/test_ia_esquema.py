"""HU-04 · Esquema `PedidoExtraido` y system prompt (sin llamar a ninguna IA)."""

import pytest
from pydantic import ValidationError

from app.ia.esquema import PedidoExtraido
from app.ia.prompt import SYSTEM_PROMPT

# Salida esperada del ejemplo de la documentación técnica (sección 4).
EJEMPLO = {
    "es_pedido": True,
    "intencion": "pedido",
    "items": [
        {
            "descripcion_original": "24 remeras lisas negras, 12 M",
            "codigo_producto": "REM-ALG-LISA",
            "talle": "M",
            "color": "negro",
            "cantidad": 12,
            "precio_unitario": 4500.00,
            "subtotal": 54000.00,
            "confianza": 0.97,
            "requiere_revision": False,
            "motivo_revision": None,
        },
        {
            "descripcion_original": "1 curva de jogger",
            "codigo_producto": None,
            "talle": None,
            "color": None,
            "cantidad": 1,
            "precio_unitario": None,
            "subtotal": None,
            "confianza": 0.3,
            "requiere_revision": True,
            "motivo_revision": "El producto 'jogger' no figura en la lista de precios.",
        },
    ],
    "total_unidades": 13,
    "subtotal": 54000.00,
    "moneda": "ARS",
    "requiere_revision": True,
    "preguntas_para_cliente": ["¿Qué modelo de jogger buscás?"],
    "datos_cliente": {
        "nombre": "Laura",
        "ciudad": "Rosario",
        "provincia": "Santa Fe",
        "razon_social": None,
    },
    "resumen": "Pide 12 remeras lisas negras M; consulta por joggers, que no están en lista.",
}


def test_valida_la_salida_del_ejemplo():
    pedido = PedidoExtraido.model_validate(EJEMPLO)
    assert pedido.items[0].codigo_producto == "REM-ALG-LISA"
    assert pedido.items[1].requiere_revision
    assert pedido.datos_cliente.nombre == "Laura"


def test_valida_desde_json_como_lo_devuelve_ollama():
    pedido = PedidoExtraido.model_validate(EJEMPLO)
    assert PedidoExtraido.model_validate_json(pedido.model_dump_json()) == pedido


def test_mensaje_sin_pedido():
    sin_pedido = {
        **EJEMPLO,
        "es_pedido": False,
        "intencion": "consulta_general",
        "items": [],
        "total_unidades": 0,
        "subtotal": 0,
        "requiere_revision": False,
        "preguntas_para_cliente": [],
    }
    assert PedidoExtraido.model_validate(sin_pedido).items == []


def test_rechaza_intencion_desconocida():
    with pytest.raises(ValidationError):
        PedidoExtraido.model_validate({**EJEMPLO, "intencion": "compra"})


def test_rechaza_json_incompleto():
    """Los modelos chicos a veces cortan el JSON: tiene que fallar para reintentar."""
    incompleto = {k: v for k, v in EJEMPLO.items() if k != "resumen"}
    with pytest.raises(ValidationError):
        PedidoExtraido.model_validate(incompleto)


def test_json_schema_para_ollama():
    esquema = PedidoExtraido.model_json_schema()
    assert set(esquema["required"]) == set(PedidoExtraido.model_fields)
    item = esquema["$defs"]["ItemPedido"]
    assert set(item["required"]) == {
        "descripcion_original",
        "codigo_producto",
        "talle",
        "color",
        "cantidad",
        "precio_unitario",
        "subtotal",
        "confianza",
        "requiere_revision",
        "motivo_revision",
    }
    assert esquema["properties"]["intencion"]["enum"] == [
        "pedido",
        "consulta_precio",
        "consulta_general",
        "otro",
    ]


def test_system_prompt_tiene_todas_las_secciones():
    for seccion in (
        "tarea",
        "reglas_de_interpretacion",
        "reglas_de_precios",
        "confianza",
        "seguridad",
        "formato_de_salida",
    ):
        assert f"<{seccion}>" in SYSTEM_PROMPT
        assert f"</{seccion}>" in SYSTEM_PROMPT
    assert "<lista_precios>" in SYSTEM_PROMPT
    assert "<mensaje_cliente>" in SYSTEM_PROMPT


def test_system_prompt_es_fijo_para_que_se_cachee():
    """Nada que cambie entre mensajes puede ir en el system (invalida la caché)."""
    for variable in ("{", "fecha=", "canal="):
        assert variable not in SYSTEM_PROMPT
