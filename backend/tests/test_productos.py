"""HU-01 · Criterio 1: un producto nuevo con talles, colores y alias queda disponible."""

import uuid

from fastapi.testclient import TestClient

REMERA = {
    "codigo": " rem-alg-lisa ",
    "nombre": "Remera algodón lisa",
    "categoria": "remeras",
    "talles": ["s", "M", "L", "XL", "m"],
    "colores": ["Negro", "blanco"],
    "alias": ["Remera Lisa", "remerita básica", "remera lisa"],
}


def test_alta_de_producto_normaliza_y_queda_en_el_catalogo(api: TestClient) -> None:
    creado = api.post("/api/v1/productos", json=REMERA)

    assert creado.status_code == 201
    producto = creado.json()
    assert producto["codigo"] == "REM-ALG-LISA"
    assert producto["talles"] == ["S", "M", "L", "XL"]
    assert producto["colores"] == ["negro", "blanco"]
    assert producto["alias"] == ["remera lisa", "remerita básica"]
    assert producto["activo"] is True

    catalogo = api.get("/api/v1/productos", params={"activo": True}).json()
    assert [p["codigo"] for p in catalogo] == ["REM-ALG-LISA"]
    assert api.get(f"/api/v1/productos/{producto['id']}").json()["nombre"] == REMERA["nombre"]


def test_codigo_duplicado_responde_409(api: TestClient) -> None:
    api.post("/api/v1/productos", json=REMERA)

    respuesta = api.post("/api/v1/productos", json={**REMERA, "codigo": "REM-ALG-LISA"})

    assert respuesta.status_code == 409
    assert respuesta.json()["error"] == "codigo_duplicado"


def test_codigo_con_espacios_internos_es_invalido(api: TestClient) -> None:
    respuesta = api.post("/api/v1/productos", json={**REMERA, "codigo": "REM ALG"})

    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "validacion"


def test_editar_alias_y_desactivar(api: TestClient) -> None:
    producto_id = api.post("/api/v1/productos", json=REMERA).json()["id"]

    editado = api.patch(
        f"/api/v1/productos/{producto_id}",
        json={"alias": ["remera básica"], "activo": False},
    )

    assert editado.status_code == 200
    assert editado.json()["alias"] == ["remera básica"]
    assert editado.json()["activo"] is False
    assert editado.json()["talles"] == ["S", "M", "L", "XL"]  # lo no enviado no cambia
    assert api.get("/api/v1/productos", params={"activo": True}).json() == []


def test_editar_con_null_en_campo_obligatorio_responde_422(api: TestClient) -> None:
    producto_id = api.post("/api/v1/productos", json=REMERA).json()["id"]

    respuesta = api.patch(f"/api/v1/productos/{producto_id}", json={"nombre": None})

    assert respuesta.status_code == 422


def test_buscar_por_nombre(api: TestClient) -> None:
    api.post("/api/v1/productos", json=REMERA)
    api.post(
        "/api/v1/productos",
        json={"codigo": "BUZ-CANG", "nombre": "Buzo canguro", "categoria": "buzos"},
    )

    encontrados = api.get("/api/v1/productos", params={"q": "canguro"}).json()

    assert [p["codigo"] for p in encontrados] == ["BUZ-CANG"]


def test_producto_inexistente_responde_404(api: TestClient) -> None:
    respuesta = api.get(f"/api/v1/productos/{uuid.uuid4()}")

    assert respuesta.status_code == 404
    assert respuesta.json()["error"] == "producto_no_encontrado"


def test_catalogo_exige_token(client: TestClient) -> None:
    assert client.get("/api/v1/productos").status_code == 401
