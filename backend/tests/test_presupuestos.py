"""HU-05 · POST /api/v1/presupuestos/calcular contra la base (SQLite en tests)."""

import pytest
from fastapi.testclient import TestClient

CATALOGO = (
    "codigo,nombre,categoria,talles,colores\n"
    "REM-ALG-LISA,Remera algodón lisa,remeras,S|M|L|XL,negro|blanco\n"
    "BUZ-CANG,Buzo canguro,buzos,M|L|XL|XXL,gris|negro\n"
)
PRECIOS = (
    "codigo,talle,cantidad_minima,precio_unitario\n"
    "REM-ALG-LISA,,1,5000\nREM-ALG-LISA,,12,4500\nREM-ALG-LISA,,50,4200\n"
    "BUZ-CANG,,1,16500\nBUZ-CANG,,10,15800\nBUZ-CANG,XXL,1,17500\n"
)


def importar_lista(api: TestClient, csv: str, nombre: str) -> str:
    respuesta = api.post(
        "/api/v1/listas-precios/importar",
        data={"nombre": nombre, "vigente_desde": "2026-11-01"},
        files={"archivo": ("lista.csv", csv.encode(), "text/csv")},
    )
    return respuesta.json()["lista"]["id"]


@pytest.fixture
def lista_activa(api: TestClient) -> str:
    api.post(
        "/api/v1/productos/importar",
        files={"archivo": ("catalogo.csv", CATALOGO.encode(), "text/csv")},
    )
    lista_id = importar_lista(api, PRECIOS, "Noviembre")
    api.post(f"/api/v1/listas-precios/{lista_id}/activar")
    return lista_id


def calcular(api: TestClient, **cuerpo):
    return api.post("/api/v1/presupuestos/calcular", json=cuerpo)


def test_ejemplo_de_la_documentacion(api: TestClient, lista_activa: str) -> None:
    """24 remeras negras (12 M + 12 L) y 10 buzos canguro gris XL → $266.000."""
    respuesta = calcular(
        api,
        items=[
            {"codigo": "REM-ALG-LISA", "talle": "M", "color": "negro", "cantidad": 12},
            {"codigo": "REM-ALG-LISA", "talle": "L", "color": "negro", "cantidad": 12},
            {"codigo": "BUZ-CANG", "talle": "XL", "color": "gris", "cantidad": 10},
        ],
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["lista_id"] == lista_activa
    assert cuerpo["moneda"] == "ARS"
    assert [(i["precio_unitario"], i["subtotal"]) for i in cuerpo["items"]] == [
        (4500.0, 54000.0),
        (4500.0, 54000.0),
        (15800.0, 158000.0),
    ]
    assert cuerpo["subtotal"] == 266000.0
    assert cuerpo["total"] == 266000.0
    assert cuerpo["requiere_revision"] is False


def test_por_producto_id_con_descuento(api: TestClient, lista_activa: str) -> None:
    buzo = api.get("/api/v1/productos", params={"q": "BUZ-CANG"}).json()[0]

    cuerpo = calcular(
        api,
        items=[{"producto_id": buzo["id"], "talle": "xxl", "cantidad": 2}],
        descuento_porcentaje=10,
    ).json()

    assert cuerpo["items"][0]["precio_unitario"] == 17500.0
    assert cuerpo["items"][0]["producto"] == "Buzo canguro"
    assert cuerpo["descuento"] == 3500.0
    assert cuerpo["total"] == 31500.0


def test_item_sin_producto_marca_revision(api: TestClient, lista_activa: str) -> None:
    cuerpo = calcular(
        api,
        items=[
            {"codigo": "REM-ALG-LISA", "cantidad": 1},
            {"descripcion_original": "una curva de jogger", "cantidad": 1},
        ],
    ).json()

    assert cuerpo["total"] == 5000.0
    assert cuerpo["requiere_revision"] is True
    assert cuerpo["items"][1]["subtotal"] is None


def test_lista_indicada_en_vez_de_la_activa(api: TestClient, lista_activa: str) -> None:
    otra = importar_lista(
        api, "codigo,talle,cantidad_minima,precio_unitario\nREM-ALG-LISA,,1,9999\n", "Vieja"
    )

    con_otra = calcular(api, lista_id=otra, items=[{"codigo": "REM-ALG-LISA", "cantidad": 1}])
    con_activa = calcular(api, items=[{"codigo": "REM-ALG-LISA", "cantidad": 1}])

    assert con_otra.json()["total"] == 9999.0
    assert con_activa.json()["total"] == 5000.0


def test_sin_lista_activa_responde_409(api: TestClient) -> None:
    respuesta = calcular(api, items=[{"codigo": "X", "cantidad": 1}])

    assert respuesta.status_code == 409
    assert respuesta.json()["error"] == "sin_lista_activa"


def test_lista_inexistente_responde_404(api: TestClient) -> None:
    respuesta = calcular(
        api,
        lista_id="00000000-0000-0000-0000-000000000000",
        items=[{"codigo": "X", "cantidad": 1}],
    )
    assert respuesta.status_code == 404


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"items": []},
        {"items": [{"codigo": "REM-ALG-LISA", "cantidad": 0}]},
        {
            "items": [{"codigo": "REM-ALG-LISA", "cantidad": 1}],
            "descuento": 1,
            "descuento_porcentaje": 1,
        },
    ],
)
def test_entradas_invalidas_responden_422(api: TestClient, lista_activa: str, cuerpo) -> None:
    assert calcular(api, **cuerpo).status_code == 422


def test_descuento_mayor_al_subtotal_responde_422(api: TestClient, lista_activa: str) -> None:
    respuesta = calcular(api, items=[{"codigo": "REM-ALG-LISA", "cantidad": 1}], descuento=6000)

    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "calculo_invalido"


def test_calcular_exige_token(client: TestClient) -> None:
    assert calcular(client, items=[{"codigo": "X", "cantidad": 1}]).status_code == 401
