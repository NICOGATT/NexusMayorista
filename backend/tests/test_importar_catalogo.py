"""HU-01 · Criterio 1 en lote: cargar el catálogo de productos desde CSV."""

import pytest
from fastapi.testclient import TestClient

from app.services.importar_catalogo import validar_catalogo_csv

CATALOGO = (
    "codigo,nombre,categoria,talles,colores,alias\n"
    "rem-alg-lisa,Remera algodón lisa,remeras,S|M|L|XL,Negro|Blanco,remera lisa|remerita básica\n"
    'BUZ-CANG,"Buzo canguro, frisa",buzos,M|L|XL|XXL,gris,buzo con capucha\n'
)


def importar(api: TestClient, csv: str):
    return api.post(
        "/api/v1/productos/importar",
        files={"archivo": ("catalogo.csv", csv.encode(), "text/csv")},
    )


# ------------------------------------------------------------ validación pura


def test_valida_y_normaliza_listas_separadas_por_barra() -> None:
    resultado = validar_catalogo_csv(CATALOGO)

    assert resultado.es_valido
    remera, buzo = (f.producto for f in resultado.filas)
    assert remera.codigo == "REM-ALG-LISA"
    assert remera.talles == ["S", "M", "L", "XL"]
    assert remera.colores == ["negro", "blanco"]
    assert remera.alias == ["remera lisa", "remerita básica"]
    assert buzo.nombre == "Buzo canguro, frisa"  # la coma entre comillas no corta la columna


def test_solo_columnas_obligatorias_y_punto_y_coma() -> None:
    texto = "codigo;nombre;categoria\nPAN-JOG;Pantalón jogger;pantalones\n"
    resultado = validar_catalogo_csv(texto)

    assert resultado.es_valido
    assert resultado.filas[0].producto.talles == []


def test_cabecera_sin_obligatorias_o_con_columnas_desconocidas() -> None:
    resultado = validar_catalogo_csv("codigo,nombre,precio\nX,Y,1\n")

    assert not resultado.es_valido
    assert "faltan categoria" in resultado.errores[0].mensaje
    assert "desconocidas: precio" in resultado.errores[0].mensaje


def test_informa_cada_fila_con_error_y_no_carga_ninguna() -> None:
    texto = (
        "codigo,nombre,categoria,activo\n"
        "REM ALG,Remera,remeras,si\n"  # línea 2: código con espacio
        "BUZ-CANG,,buzos,si\n"  # línea 3: falta nombre
        "PAN-JOG,Jogger,pantalones,quizas\n"  # línea 4: activo inválido
        "BUZ-CANG,Buzo,buzos,no\n"  # línea 5: válida
        "buz-cang,Buzo otra vez,buzos,no\n"  # línea 6: código repetido
    )

    resultado = validar_catalogo_csv(texto)

    assert not resultado.es_valido
    assert [(e.linea, e.campo) for e in resultado.errores] == [
        (2, "codigo"),
        (3, "nombre"),
        (4, "activo"),
        (6, "codigo"),
    ]
    assert "línea 5" in resultado.errores[-1].mensaje


SIN_PRODUCTOS = ["", "codigo,nombre,categoria\n", "codigo,nombre,categoria\n,,\n"]


@pytest.mark.parametrize("texto", SIN_PRODUCTOS)
def test_archivo_vacio_o_sin_productos(texto: str) -> None:
    assert not validar_catalogo_csv(texto).es_valido


# ------------------------------------------------------------------- endpoint


def test_importa_el_catalogo_y_queda_disponible(api: TestClient) -> None:
    respuesta = importar(api, CATALOGO)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"filas": 2, "creados": 2, "actualizados": 0}
    productos = api.get("/api/v1/productos").json()
    assert [p["codigo"] for p in productos] == ["BUZ-CANG", "REM-ALG-LISA"]
    assert productos[1]["alias"] == ["remera lisa", "remerita básica"]


def test_reimportar_actualiza_solo_las_columnas_del_archivo(api: TestClient) -> None:
    importar(api, CATALOGO)

    respuesta = importar(
        api,
        "codigo,nombre,categoria,alias\n"
        "REM-ALG-LISA,Remera lisa 24/1,remeras,remera lisa|lisita\n"
        "CAM-JEAN,Campera de jean,camperas,\n",
    )

    assert respuesta.json() == {"filas": 2, "creados": 1, "actualizados": 1}
    remera = api.get("/api/v1/productos", params={"q": "REM-ALG-LISA"}).json()[0]
    assert remera["nombre"] == "Remera lisa 24/1"
    assert remera["alias"] == ["remera lisa", "lisita"]
    assert remera["talles"] == ["S", "M", "L", "XL"]  # no venía en el archivo: se conserva
    assert remera["colores"] == ["negro", "blanco"]


def test_csv_invalido_no_guarda_nada(api: TestClient) -> None:
    respuesta = importar(api, "codigo,nombre,categoria\nREM-ALG-LISA,Remera,remeras\nMAL COD,X,y\n")

    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    assert cuerpo["error"] == "csv_invalido"
    assert cuerpo["detalle"][0]["linea"] == 3
    assert api.get("/api/v1/productos").json() == []


def test_catalogo_importado_permite_importar_la_lista_de_precios(api: TestClient) -> None:
    importar(api, CATALOGO)

    respuesta = api.post(
        "/api/v1/listas-precios/importar",
        data={"nombre": "Noviembre", "vigente_desde": "2026-11-01"},
        files={
            "archivo": (
                "lista.csv",
                b"codigo,talle,cantidad_minima,precio_unitario\n"
                b"REM-ALG-LISA,,1,5000\nBUZ-CANG,XXL,1,17500\n",
                "text/csv",
            )
        },
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["filas_cargadas"] == 2


def test_importar_catalogo_exige_token(client: TestClient) -> None:
    assert importar(client, CATALOGO).status_code == 401
