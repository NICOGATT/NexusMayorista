"""HU-01 · Criterios 2, 3 y 4: importar CSV, rechazar códigos inexistentes y activar."""

import uuid

import pytest
from fastapi.testclient import TestClient

CSV_VALIDO = (
    "codigo,talle,cantidad_minima,precio_unitario\n"
    "REM-ALG-LISA,,1,5000\n"
    "REM-ALG-LISA,,12,4500\n"
    "REM-ALG-LISA,,50,4200\n"
    "BUZ-CANG,XL,1,15800\n"
)


@pytest.fixture
def catalogo(api: TestClient) -> None:
    api.post(
        "/api/v1/productos",
        json={
            "codigo": "REM-ALG-LISA",
            "nombre": "Remera algodón lisa",
            "categoria": "remeras",
            "talles": ["S", "M", "L", "XL"],
        },
    )
    api.post(
        "/api/v1/productos",
        json={
            "codigo": "BUZ-CANG",
            "nombre": "Buzo canguro",
            "categoria": "buzos",
            "talles": ["M", "L", "XL"],
        },
    )


def importar(api: TestClient, csv: str, nombre: str = "Mayorista Noviembre 2026"):
    return api.post(
        "/api/v1/listas-precios/importar",
        data={"nombre": nombre, "vigente_desde": "2026-11-01"},
        files={"archivo": ("lista.csv", csv.encode(), "text/csv")},
    )


@pytest.mark.usefixtures("catalogo")
def test_csv_valido_crea_lista_inactiva_con_todas_las_escalas(api: TestClient) -> None:
    respuesta = importar(api, CSV_VALIDO)

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["filas_cargadas"] == 4
    assert cuerpo["lista"]["activa"] is False
    assert cuerpo["lista"]["nombre"] == "Mayorista Noviembre 2026"

    detalle = api.get(f"/api/v1/listas-precios/{cuerpo['lista']['id']}").json()
    assert [
        (p["codigo"], p["talle"], p["cantidad_minima"], p["precio_unitario"])
        for p in detalle["precios"]
    ] == [
        ("BUZ-CANG", "XL", 1, 15800.0),
        ("REM-ALG-LISA", None, 1, 5000.0),
        ("REM-ALG-LISA", None, 12, 4500.0),
        ("REM-ALG-LISA", None, 50, 4200.0),
    ]


@pytest.mark.usefixtures("catalogo")
def test_codigo_inexistente_rechaza_toda_la_importacion(api: TestClient) -> None:
    csv = CSV_VALIDO + "JEAN-MOM,,1,20000\n"

    respuesta = importar(api, csv)

    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    assert cuerpo["error"] == "csv_invalido"
    assert cuerpo["detalle"] == [
        {
            "linea": 6,
            "codigo": "JEAN-MOM",
            "campo": "codigo",
            "mensaje": "El código JEAN-MOM no existe en el catálogo.",
        }
    ]
    assert api.get("/api/v1/listas-precios").json() == []  # no se guardó nada


@pytest.mark.usefixtures("catalogo")
def test_activar_otra_lista_desactiva_la_anterior(api: TestClient) -> None:
    primera = importar(api, CSV_VALIDO, "Octubre").json()["lista"]["id"]
    segunda = importar(api, CSV_VALIDO, "Noviembre").json()["lista"]["id"]

    assert api.post(f"/api/v1/listas-precios/{primera}/activar").json()["activa"] is True
    assert api.get("/api/v1/listas-precios/activa").json()["id"] == primera

    activada = api.post(f"/api/v1/listas-precios/{segunda}/activar")

    assert activada.status_code == 200
    listas = {lista["id"]: lista["activa"] for lista in api.get("/api/v1/listas-precios").json()}
    assert listas == {primera: False, segunda: True}
    activa = api.get("/api/v1/listas-precios/activa").json()
    assert activa["id"] == segunda
    assert len(activa["precios"]) == 4


@pytest.mark.usefixtures("catalogo")
def test_activar_dos_veces_la_misma_lista_es_idempotente(api: TestClient) -> None:
    lista = importar(api, CSV_VALIDO).json()["lista"]["id"]

    api.post(f"/api/v1/listas-precios/{lista}/activar")
    segunda_vez = api.post(f"/api/v1/listas-precios/{lista}/activar")

    assert segunda_vez.status_code == 200
    assert segunda_vez.json()["activa"] is True


def test_sin_lista_activa_responde_404(api: TestClient) -> None:
    respuesta = api.get("/api/v1/listas-precios/activa")

    assert respuesta.status_code == 404
    assert respuesta.json()["error"] == "sin_lista_activa"


def test_activar_lista_inexistente_responde_404(api: TestClient) -> None:
    respuesta = api.post(f"/api/v1/listas-precios/{uuid.uuid4()}/activar")

    assert respuesta.status_code == 404


@pytest.mark.usefixtures("catalogo")
def test_vigencia_invertida_responde_422(api: TestClient) -> None:
    respuesta = api.post(
        "/api/v1/listas-precios/importar",
        data={"nombre": "X", "vigente_desde": "2026-11-30", "vigente_hasta": "2026-11-01"},
        files={"archivo": ("lista.csv", CSV_VALIDO.encode(), "text/csv")},
    )

    assert respuesta.status_code == 422


def test_la_base_impide_dos_listas_activas(fabrica_sesiones) -> None:
    """Aunque el código fallara, el índice único parcial lo frena."""
    from datetime import date

    from sqlalchemy.exc import IntegrityError

    from app.models import ListaPrecios

    with fabrica_sesiones() as db:
        db.add(ListaPrecios(nombre="A", vigente_desde=date(2026, 11, 1), activa=True))
        db.commit()
        db.add(ListaPrecios(nombre="B", vigente_desde=date(2026, 11, 1), activa=True))
        with pytest.raises(IntegrityError):
            db.commit()
