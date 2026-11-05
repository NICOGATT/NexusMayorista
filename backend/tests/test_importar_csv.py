"""Validación pura del CSV (sin base de datos)."""

import uuid
from decimal import Decimal

import pytest

from app.services.importar_csv import (
    ProductoCatalogo,
    decodificar,
    parsear_precio,
    validar_csv,
)

REMERA = ProductoCatalogo(uuid.uuid4(), "REM-ALG-LISA", frozenset({"S", "M", "L", "XL"}))
BUZO = ProductoCatalogo(uuid.uuid4(), "BUZ-CANG", frozenset())
CATALOGO = {p.codigo: p for p in (REMERA, BUZO)}

CABECERA = "codigo,talle,cantidad_minima,precio_unitario\n"


def test_csv_valido_con_escalas_y_talle_vacio() -> None:
    texto = CABECERA + (
        "REM-ALG-LISA,,1,5000\n"
        "REM-ALG-LISA,,12,4500.00\n"
        "rem-alg-lisa,xl,12,4800\n"
        "\n"
        "BUZ-CANG,,1,15800.5\n"
    )

    resultado = validar_csv(texto, CATALOGO)

    assert resultado.es_valido
    assert [(f.codigo, f.talle, f.cantidad_minima, f.precio_unitario) for f in resultado.filas] == [
        ("REM-ALG-LISA", None, 1, Decimal("5000.00")),
        ("REM-ALG-LISA", None, 12, Decimal("4500.00")),
        ("REM-ALG-LISA", "XL", 12, Decimal("4800.00")),
        ("BUZ-CANG", None, 1, Decimal("15800.50")),
    ]
    assert resultado.filas[-1].linea == 6  # la línea en blanco cuenta, como en el archivo


def test_codigo_inexistente_indica_linea_y_codigo() -> None:
    texto = CABECERA + "REM-ALG-LISA,,1,5000\nJEAN-MOM,,1,20000\n"

    resultado = validar_csv(texto, CATALOGO)

    assert not resultado.es_valido
    assert [(e.linea, e.codigo, e.campo) for e in resultado.errores] == [(3, "JEAN-MOM", "codigo")]
    assert "JEAN-MOM" in resultado.errores[0].mensaje


def test_informa_todos_los_errores_no_solo_el_primero() -> None:
    texto = CABECERA + (
        "NO-EXISTE,,1,100\n"
        "REM-ALG-LISA,XXL,1,100\n"
        "REM-ALG-LISA,,0,100\n"
        "REM-ALG-LISA,,1,-5\n"
        '"REM-ALG-LISA","",1,"10,555"\n'
        "BUZ-CANG,,1\n"
    )

    resultado = validar_csv(texto, CATALOGO)

    assert [(e.linea, e.campo) for e in resultado.errores] == [
        (2, "codigo"),
        (3, "talle"),
        (4, "cantidad_minima"),
        (5, "precio_unitario"),
        (6, "precio_unitario"),
        (7, None),
    ]


def test_escala_repetida() -> None:
    texto = CABECERA + "REM-ALG-LISA,M,12,4500\nrem-alg-lisa,m,12,4400\n"

    resultado = validar_csv(texto, CATALOGO)

    assert [(e.linea, e.mensaje) for e in resultado.errores] == [
        (3, "Escala repetida: mismo código, talle y cantidad_minima que la línea 2.")
    ]


def test_formato_excel_en_espanol_con_punto_y_coma() -> None:
    texto = "CODIGO;TALLE;CANTIDAD_MINIMA;PRECIO_UNITARIO\nREM-ALG-LISA;;12;4.500,50\n"

    resultado = validar_csv(texto, CATALOGO)

    assert resultado.es_valido
    assert resultado.filas[0].precio_unitario == Decimal("4500.50")


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("4500", "4500"),
        ("4500.5", "4500.5"),
        ("4500,50", "4500.50"),
        ("4.500,50", "4500.50"),
        ("4.500", "4500"),
        ("1.250.000", "1250000"),
        ("$ 4500", "4500"),
    ],
)
def test_parsear_precio(texto: str, esperado: str) -> None:
    assert parsear_precio(texto) == Decimal(esperado)


def test_cabecera_incorrecta() -> None:
    resultado = validar_csv("codigo,precio\nREM-ALG-LISA,5000\n", CATALOGO)

    assert resultado.errores[0].linea == 1
    assert "cabecera" in resultado.errores[0].mensaje


@pytest.mark.parametrize("texto", ["", CABECERA, CABECERA + "\n\n"])
def test_archivo_vacio_o_sin_filas(texto: str) -> None:
    resultado = validar_csv(texto, CATALOGO)

    assert not resultado.es_valido
    assert len(resultado.errores) == 1


def test_decodifica_utf8_con_bom_y_windows_1252() -> None:
    assert decodificar("﻿código".encode()) == "código"
    assert decodificar("código".encode("cp1252")) == "código"
