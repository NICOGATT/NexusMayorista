"""Carga el catálogo y la lista de precios reales directo en la base (HU-01).

Hace lo mismo que `POST /productos/importar` + `POST /listas-precios/importar` +
`POST /listas-precios/{id}/activar`, pero sin levantar la API ni conseguir un JWT.
Todo ocurre en UNA transacción: si algo falla, no queda nada a medias.

Por defecto es una prueba (valida, inserta y hace rollback). Para guardar de verdad
hay que pasar --confirmar.

Uso, desde backend/ (toma DATABASE_URL de backend/.env):

    python -m scripts.cargar_catalogo \\
        --catalogo ../docs/ejemplos/catalogo-ejemplo.csv \\
        --precios ../docs/ejemplos/lista-precios-ejemplo.csv \\
        --nombre "Mayorista Noviembre 2026" --desde 2026-11-01 --activar

    # Si todo sale bien, repetir con --confirmar.

Se puede pasar solo --catalogo (actualiza productos) o solo --precios (usa el
catálogo que ya está en la base).
"""

import argparse
import sys
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from app.db import get_sessionmaker
from app.services import listas_precios as servicio
from app.services.importar_catalogo import aplicar_catalogo, validar_catalogo_csv
from app.services.importar_csv import ErrorFila, decodificar, validar_csv


def _imprimir_errores(archivo: Path, errores: list[ErrorFila]) -> None:
    print(f"\n✗ {archivo.name}: {len(errores)} error(es), no se cargó nada.")
    for e in errores:
        partes = [f"línea {e.linea}"]
        if e.codigo:
            partes.append(e.codigo)
        if e.campo:
            partes.append(e.campo)
        print(f"  - [{' · '.join(partes)}] {e.mensaje}")


def cargar(db: Session, args: argparse.Namespace) -> bool:
    """Aplica los cambios en la sesión sin hacer commit. Devuelve False si hubo errores."""
    if args.catalogo:
        resultado = validar_catalogo_csv(decodificar(args.catalogo.read_bytes()))
        if not resultado.es_valido:
            _imprimir_errores(args.catalogo, resultado.errores)
            return False
        creados, actualizados = aplicar_catalogo(db, resultado)
        print(
            f"✓ Catálogo: {len(resultado.filas)} productos "
            f"({creados} nuevos, {actualizados} actualizados)."
        )

    if args.precios:
        resultado_precios = validar_csv(
            decodificar(args.precios.read_bytes()), servicio.catalogo_por_codigo(db)
        )
        if not resultado_precios.es_valido:
            _imprimir_errores(args.precios, resultado_precios.errores)
            return False
        lista = servicio.crear_lista(
            db,
            resultado_precios,
            nombre=args.nombre,
            vigente_desde=args.desde,
            vigente_hasta=args.hasta,
            moneda=args.moneda,
        )
        print(f"✓ Lista '{lista.nombre}': {len(resultado_precios.filas)} escalas (id {lista.id}).")
        if args.activar:
            servicio.activar(db, lista)
            print("✓ Lista activada; la anterior quedó inactiva.")
    return True


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Carga catálogo y lista de precios desde CSV directo en la base."
    )
    parser.add_argument("--catalogo", type=Path, help="CSV de productos")
    parser.add_argument("--precios", type=Path, help="CSV de la lista de precios")
    parser.add_argument("--nombre", help="Nombre de la lista (obligatorio con --precios)")
    parser.add_argument("--desde", type=date.fromisoformat, help="Vigente desde (AAAA-MM-DD)")
    parser.add_argument("--hasta", type=date.fromisoformat, help="Vigente hasta (opcional)")
    parser.add_argument("--moneda", default="ARS")
    parser.add_argument("--activar", action="store_true", help="Activar la lista cargada")
    parser.add_argument(
        "--confirmar", action="store_true", help="Guardar (sin esto se hace rollback)"
    )
    args = parser.parse_args(argv)

    if not args.catalogo and not args.precios:
        parser.error("Pasá --catalogo, --precios o ambos.")
    if args.precios and (not args.nombre or not args.desde):
        parser.error("Con --precios hacen falta --nombre y --desde.")
    if args.activar and not args.precios:
        parser.error("--activar solo tiene sentido con --precios.")
    if args.hasta and args.desde and args.hasta < args.desde:
        parser.error("--hasta no puede ser anterior a --desde.")
    for archivo in (args.catalogo, args.precios):
        if archivo and not archivo.is_file():
            parser.error(f"No existe el archivo {archivo}.")
    return args


def main(argv: list[str] | None = None, sesiones=None) -> int:
    # La consola de Windows no siempre usa UTF-8 y los ✓/✗ harían fallar el print.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = _argumentos(argv)
    fabrica = sesiones or get_sessionmaker()
    with fabrica() as db:
        try:
            ok = cargar(db, args)
        except Exception:
            db.rollback()
            raise
        if not ok:
            db.rollback()
            return 1
        if args.confirmar:
            db.commit()
            print("\nGuardado.")
        else:
            db.rollback()
            print("\nPrueba OK, no se guardó nada. Repetí con --confirmar para guardar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
