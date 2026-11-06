"""Script de carga directa: catálogo + lista + activación en una transacción."""

from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models import ListaPrecios, Precio, Producto
from scripts.cargar_catalogo import main

EJEMPLOS = Path(__file__).resolve().parents[2] / "docs" / "ejemplos"
CATALOGO = EJEMPLOS / "catalogo-ejemplo.csv"
PRECIOS = EJEMPLOS / "lista-precios-ejemplo.csv"
ARGS = [
    "--catalogo",
    str(CATALOGO),
    "--precios",
    str(PRECIOS),
    "--nombre",
    "Mayorista Noviembre 2026",
    "--desde",
    "2026-11-01",
    "--activar",
]


def contar(fabrica, modelo) -> int:
    with fabrica() as db:
        return db.scalar(select(func.count()).select_from(modelo))


def test_sin_confirmar_no_guarda_nada(fabrica_sesiones, capsys) -> None:
    assert main(ARGS, fabrica_sesiones) == 0

    assert "no se guardó nada" in capsys.readouterr().out
    assert contar(fabrica_sesiones, Producto) == 0
    assert contar(fabrica_sesiones, ListaPrecios) == 0


def test_con_confirmar_carga_todo_y_deja_la_lista_activa(fabrica_sesiones) -> None:
    assert main([*ARGS, "--confirmar"], fabrica_sesiones) == 0

    with fabrica_sesiones() as db:
        assert db.scalars(select(Producto.codigo).order_by(Producto.codigo)).all() == [
            "BUZ-CANG",
            "REM-ALG-LISA",
        ]
        activa = db.scalar(select(ListaPrecios).where(ListaPrecios.activa.is_(True)))
        assert activa.nombre == "Mayorista Noviembre 2026"
    assert contar(fabrica_sesiones, Precio) == 6


def test_segunda_carga_desactiva_la_lista_anterior(fabrica_sesiones) -> None:
    main([*ARGS, "--confirmar"], fabrica_sesiones)
    otra = [*ARGS, "--confirmar"]
    otra[otra.index("Mayorista Noviembre 2026")] = "Mayorista Diciembre 2026"

    assert main(otra, fabrica_sesiones) == 0

    with fabrica_sesiones() as db:
        activas = db.scalars(select(ListaPrecios.nombre).where(ListaPrecios.activa.is_(True)))
        assert activas.all() == ["Mayorista Diciembre 2026"]
    assert contar(fabrica_sesiones, Producto) == 2  # el catálogo se actualizó, no se duplicó


def test_error_en_precios_revierte_tambien_el_catalogo(fabrica_sesiones, tmp_path, capsys) -> None:
    precios = tmp_path / "precios.csv"
    precios.write_text("codigo,talle,cantidad_minima,precio_unitario\nNO-EXISTE,,1,100\n")

    codigo = main(
        [
            "--catalogo",
            str(CATALOGO),
            "--precios",
            str(precios),
            "--nombre",
            "X",
            "--desde",
            "2026-11-01",
            "--confirmar",
        ],
        fabrica_sesiones,
    )

    assert codigo == 1
    assert "línea 2 · NO-EXISTE" in capsys.readouterr().out
    assert contar(fabrica_sesiones, Producto) == 0


def test_precios_sin_nombre_es_error_de_uso(fabrica_sesiones) -> None:
    with pytest.raises(SystemExit):
        main(["--precios", str(PRECIOS)], fabrica_sesiones)
