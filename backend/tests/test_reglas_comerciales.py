"""Reglas comerciales: preguntas a la fábrica, respuestas, ficha y efecto en el cálculo."""

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from app.models import ReglasComerciales
from app.services.calculo import EscalaPor, IvaEnPresupuesto
from app.services.reglas_comerciales import (
    PREGUNTAS,
    a_reglas_calculo,
    generar_ficha,
    pendientes,
    respuesta_legible,
)
from tests.test_presupuestos import calcular, lista_activa  # noqa: F401  (fixture)

RESPUESTAS = {
    "escala_por": "item",
    "precios_incluyen_iva": False,
    "alicuota_iva": 21,
    "iva_en_presupuesto": "sumar",
    "pedido_minimo_unidades": 12,
    "pedido_minimo_monto": 0,
    "descuento_maximo_porcentaje": 10,
    "validez_dias": 7,
    "condiciones_pago": "50 % de seña, saldo contra entrega.",
    "notas": "Lo charlamos con Marta por teléfono.",
    "confirmado_por": "Marta (administración)",
    "confirmado_el": "2026-11-09",
}


# ------------------------------------------------------------------- servicio


def test_sin_respuestas_el_motor_usa_los_valores_por_defecto() -> None:
    reglas = a_reglas_calculo(ReglasComerciales(id=1))

    assert reglas.escala_por == EscalaPor.PRODUCTO
    assert reglas.precios_incluyen_iva is None
    assert reglas.alicuota_iva == Decimal("21")


def test_las_respuestas_pasan_al_motor() -> None:
    fila = ReglasComerciales(
        id=1,
        escala_por="item",
        precios_incluyen_iva=False,
        alicuota_iva=Decimal("10.5"),
        iva_en_presupuesto="aclarar",
        pedido_minimo_unidades=6,
    )
    reglas = a_reglas_calculo(fila)

    assert reglas.escala_por == EscalaPor.ITEM
    assert reglas.alicuota_iva == Decimal("10.5")
    assert reglas.iva_en_presupuesto == IvaEnPresupuesto.ACLARAR
    assert reglas.pedido_minimo_unidades == 6


def test_iva_en_presupuesto_solo_se_pregunta_si_los_precios_son_sin_iva() -> None:
    campos = lambda fila: {p.campo for p in pendientes(fila)}  # noqa: E731

    assert "iva_en_presupuesto" not in campos(ReglasComerciales(id=1))
    assert "iva_en_presupuesto" not in campos(ReglasComerciales(id=1, precios_incluyen_iva=True))
    assert "iva_en_presupuesto" in campos(ReglasComerciales(id=1, precios_incluyen_iva=False))
    assert len(pendientes(ReglasComerciales(id=1))) == len(PREGUNTAS) - 1


def test_respuestas_legibles() -> None:
    assert respuesta_legible("pedido_minimo_unidades", 0) == "No hay mínimo."
    assert respuesta_legible("pedido_minimo_monto", Decimal("150000")) == "$150.000."
    assert respuesta_legible("descuento_maximo_porcentaje", Decimal("100")) == "Sin tope."
    assert respuesta_legible("descuento_maximo_porcentaje", Decimal("7.5")) == "Hasta 7,5 %."
    assert respuesta_legible("alicuota_iva", Decimal("10.50")) == "10,5 %"
    assert respuesta_legible("validez_dias", 1) == "1 día."


def test_ficha_con_respuestas_y_pendientes() -> None:
    fila = ReglasComerciales(id=1, escala_por="producto", precios_incluyen_iva=True)
    ficha = generar_ficha(fila, hoy=date(2026, 11, 8))

    assert ficha.estado == "Pendiente de confirmación por la fábrica."
    assert [r.respuesta for r in ficha.respuestas] == [
        "Por producto: se suman todos los talles y colores del mismo producto.",
        "Sí, los precios incluyen IVA.",
    ]
    assert len(ficha.pendientes) == len(PREGUNTAS) - 3  # 2 respondidas + 1 que no aplica
    texto = ficha.texto_whatsapp
    assert texto.startswith("*Definiciones comerciales*\nGenerada el 08/11/2026.")
    assert "*Precios y escalas*" in texto
    assert "*Nos falta que nos respondan*" in texto
    assert texto.endswith("¿Nos confirman que está todo bien o qué hay que corregir? ¡Gracias!")


def test_ficha_confirmada() -> None:
    fila = ReglasComerciales(
        id=1, confirmado_por="Marta", confirmado_el=date(2026, 11, 9), notas="  "
    )
    ficha = generar_ficha(fila, hoy=date(2026, 11, 10))

    assert ficha.estado == "Confirmada por Marta el 09/11/2026."
    assert ficha.notas is None


# ------------------------------------------------------------------ endpoints


def test_get_sin_fila_devuelve_todo_sin_responder(api: TestClient) -> None:
    cuerpo = api.get("/api/v1/reglas-comerciales").json()

    assert cuerpo["escala_por"] is None
    assert cuerpo["pendientes"] == len(PREGUNTAS) - 1
    assert [p["campo"] for p in cuerpo["preguntas"]][:2] == ["escala_por", "precios_incluyen_iva"]
    assert all(not p["respondida"] for p in cuerpo["preguntas"])


def test_put_guarda_y_registra_quien(api: TestClient) -> None:
    respuesta = api.put("/api/v1/reglas-comerciales", json=RESPUESTAS)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["pendientes"] == 0
    assert cuerpo["escala_por"] == "item"
    assert cuerpo["alicuota_iva"] == 21.0
    assert cuerpo["pedido_minimo_monto"] == 0.0
    assert cuerpo["actualizado_por"] == "vendedor@example.com"
    assert api.get("/api/v1/reglas-comerciales").json()["validez_dias"] == 7


def test_put_reemplaza_todo_y_limpia_iva_si_los_precios_lo_incluyen(api: TestClient) -> None:
    api.put("/api/v1/reglas-comerciales", json=RESPUESTAS)

    cuerpo = api.put(
        "/api/v1/reglas-comerciales",
        json={"precios_incluyen_iva": True, "iva_en_presupuesto": "sumar", "notas": "  "},
    ).json()

    assert cuerpo["iva_en_presupuesto"] is None
    assert cuerpo["escala_por"] is None
    assert cuerpo["notas"] is None


def test_put_valida_las_respuestas(api: TestClient) -> None:
    for invalido in (
        {"escala_por": "talle"},
        {"alicuota_iva": 150},
        {"validez_dias": 0},
        {"pedido_minimo_unidades": -1},
    ):
        assert api.put("/api/v1/reglas-comerciales", json=invalido).status_code == 422


def test_ficha_por_api(api: TestClient) -> None:
    api.put("/api/v1/reglas-comerciales", json=RESPUESTAS)
    cuerpo = api.get("/api/v1/reglas-comerciales/ficha").json()

    assert cuerpo["estado"] == "Confirmada por Marta (administración) el 09/11/2026."
    assert cuerpo["pendientes"] == []
    assert len(cuerpo["respuestas"]) == len(PREGUNTAS)
    assert "→ Por ítem: cada talle y color se cuenta por separado." in cuerpo["texto_whatsapp"]


def test_el_calculo_aplica_las_reglas_guardadas(
    api: TestClient,
    lista_activa: str,  # noqa: F811
) -> None:
    pedido = [
        {"codigo": "REM-ALG-LISA", "talle": "M", "cantidad": 6},
        {"codigo": "REM-ALG-LISA", "talle": "L", "cantidad": 6},
    ]
    antes = calcular(api, items=pedido).json()

    api.put("/api/v1/reglas-comerciales", json=RESPUESTAS)
    despues = calcular(api, items=pedido).json()

    # Por producto: 12 unidades → $4.500. Por ítem: 6 y 6 → $5.000.
    assert antes["subtotal"] == 54000.0
    assert antes["leyenda_iva"] is None
    assert despues["subtotal"] == 60000.0
    assert despues["iva"] == 12600.0
    assert despues["total"] == 72600.0
    assert despues["leyenda_iva"] == "Precios sin IVA. Se suma IVA 21 %."
    assert despues["requiere_revision"] is False


def test_reglas_exigen_token(client: TestClient) -> None:
    assert client.get("/api/v1/reglas-comerciales").status_code == 401
