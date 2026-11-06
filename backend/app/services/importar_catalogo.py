"""Importación del catálogo de productos desde CSV (HU-01).

Cabecera (el orden no importa; solo las tres primeras son obligatorias):

    codigo,nombre,categoria,talles,colores,alias,descripcion,activo

`talles`, `colores` y `alias` llevan varios valores separados por `|`
(ej. `S|M|L|XL`, `remera lisa|remerita básica`). Acepta `,` o `;` como separador
de columnas, igual que el CSV de precios.

Si el código ya existe, el producto se actualiza con las columnas presentes en el
archivo; si no, se crea. Se validan todas las filas antes de tocar la base.
"""

import csv
import io
from dataclasses import dataclass, field

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Producto
from app.schemas.catalogo import ProductoCrear
from app.services.importar_csv import MAX_ERRORES, ErrorFila, detectar_separador

OBLIGATORIAS = ("codigo", "nombre", "categoria")
OPCIONALES = ("talles", "colores", "alias", "descripcion", "activo")
LISTAS = ("talles", "colores", "alias")
SEPARADOR_VALORES = "|"

VERDADEROS = {"si", "sí", "s", "true", "1", "x", "activo"}
FALSOS = {"no", "n", "false", "0", "inactivo"}


@dataclass(frozen=True)
class FilaProducto:
    linea: int
    producto: ProductoCrear


@dataclass
class ResultadoCatalogo:
    columnas: tuple[str, ...] = ()
    filas: list[FilaProducto] = field(default_factory=list)
    errores: list[ErrorFila] = field(default_factory=list)

    @property
    def es_valido(self) -> bool:
        return not self.errores and bool(self.filas)


def _lista(valor: str) -> list[str]:
    return [v for v in (p.strip() for p in valor.split(SEPARADOR_VALORES)) if v]


def _mensaje_pydantic(detalle: dict) -> str:
    mensaje = str(detalle.get("msg", "Valor inválido."))
    return mensaje.removeprefix("Value error, ")


def validar_catalogo_csv(texto: str) -> ResultadoCatalogo:
    resultado = ResultadoCatalogo()
    errores = resultado.errores

    def error(linea: int, codigo: str | None, campo: str | None, mensaje: str) -> None:
        errores.append(ErrorFila(linea, codigo, campo, mensaje))

    lineas = texto.splitlines()
    if not lineas or not lineas[0].strip():
        error(1, None, None, "El archivo está vacío.")
        return resultado

    lector = csv.reader(io.StringIO(texto), delimiter=detectar_separador(lineas[0]))
    cabecera = tuple(c.strip().lower() for c in next(lector))
    faltantes = [c for c in OBLIGATORIAS if c not in cabecera]
    desconocidas = [c for c in cabecera if c not in OBLIGATORIAS + OPCIONALES]
    repetidas = sorted({c for c in cabecera if cabecera.count(c) > 1})
    if faltantes or desconocidas or repetidas:
        partes = []
        if faltantes:
            partes.append(f"faltan {', '.join(faltantes)}")
        if desconocidas:
            partes.append(f"columnas desconocidas: {', '.join(desconocidas)}")
        if repetidas:
            partes.append(f"columnas repetidas: {', '.join(repetidas)}")
        error(
            1,
            None,
            None,
            f"Cabecera inválida ({'; '.join(partes)}). Obligatorias: {','.join(OBLIGATORIAS)}. "
            f"Opcionales: {','.join(OPCIONALES)}.",
        )
        return resultado
    resultado.columnas = cabecera

    codigos_vistos: dict[str, int] = {}

    for valores in lector:
        linea = lector.line_num
        if len(errores) >= MAX_ERRORES:
            break
        if not any(v.strip() for v in valores):
            continue
        if len(valores) != len(cabecera):
            error(linea, None, None, f"Se esperaban {len(cabecera)} columnas y hay {len(valores)}.")
            continue

        crudo = {col: v.strip() for col, v in zip(cabecera, valores, strict=True)}
        codigo = crudo["codigo"].upper() or None
        errores_antes = len(errores)

        datos: dict[str, object] = {c: crudo[c] for c in OBLIGATORIAS}
        for col in LISTAS:
            if col in crudo:
                datos[col] = _lista(crudo[col])
        if "descripcion" in crudo:
            datos["descripcion"] = crudo["descripcion"] or None
        if "activo" in crudo:
            valor = crudo["activo"].lower()
            if valor in VERDADEROS or not valor:
                datos["activo"] = True
            elif valor in FALSOS:
                datos["activo"] = False
            else:
                error(linea, codigo, "activo", f"activo debe ser si/no (se recibió '{valor}').")

        producto: ProductoCrear | None = None
        try:
            producto = ProductoCrear.model_validate(datos)
        except ValidationError as exc:
            for detalle in exc.errors():
                campo = str(detalle["loc"][0]) if detalle.get("loc") else None
                error(linea, codigo, campo, _mensaje_pydantic(detalle))

        if len(errores) > errores_antes or producto is None:
            continue

        if producto.codigo in codigos_vistos:
            error(
                linea,
                producto.codigo,
                "codigo",
                f"Código repetido: ya aparece en la línea {codigos_vistos[producto.codigo]}.",
            )
            continue
        codigos_vistos[producto.codigo] = linea
        resultado.filas.append(FilaProducto(linea, producto))

    if not errores and not resultado.filas:
        error(1, None, None, "El archivo no tiene productos.")

    return resultado


def aplicar_catalogo(db: Session, resultado: ResultadoCatalogo) -> tuple[int, int]:
    """Crea o actualiza los productos validados. No hace commit.

    Devuelve (creados, actualizados).
    """
    codigos = [f.producto.codigo for f in resultado.filas]
    consulta = select(Producto).where(Producto.codigo.in_(codigos))
    existentes = {p.codigo: p for p in db.scalars(consulta)}
    # En una actualización solo se pisan las columnas que vinieron en el archivo.
    campos = [c for c in ProductoCrear.model_fields if c in resultado.columnas]

    creados = actualizados = 0
    for fila in resultado.filas:
        datos = fila.producto.model_dump()
        actual = existentes.get(fila.producto.codigo)
        if actual is None:
            db.add(Producto(**datos))
            creados += 1
        else:
            for campo in campos:
                setattr(actual, campo, datos[campo])
            actualizados += 1
    db.flush()
    return creados, actualizados
