"""Validación del CSV de lista de precios (HU-01).

Formato: `codigo,talle,cantidad_minima,precio_unitario`. También acepta `;` como
separador y coma decimal, que es lo que exporta Excel en español.

Se validan TODAS las filas antes de guardar: si hay un solo error no se importa nada.
Las líneas se numeran como en el archivo (la cabecera es la línea 1).
"""

import csv
import io
import re
import uuid
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

COLUMNAS = ("codigo", "talle", "cantidad_minima", "precio_unitario")
MAX_ERRORES = 100


@dataclass(frozen=True)
class ProductoCatalogo:
    id: uuid.UUID
    codigo: str
    talles: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class FilaPrecio:
    linea: int
    producto_id: uuid.UUID
    codigo: str
    talle: str | None
    cantidad_minima: int
    precio_unitario: Decimal


@dataclass(frozen=True)
class ErrorFila:
    linea: int
    codigo: str | None
    campo: str | None
    mensaje: str

    def a_dict(self) -> dict[str, object]:
        return {
            "linea": self.linea,
            "codigo": self.codigo,
            "campo": self.campo,
            "mensaje": self.mensaje,
        }


@dataclass
class ResultadoValidacion:
    filas: list[FilaPrecio] = field(default_factory=list)
    errores: list[ErrorFila] = field(default_factory=list)

    @property
    def es_valido(self) -> bool:
        return not self.errores and bool(self.filas)


def decodificar(contenido: bytes) -> str:
    """UTF-8 (con o sin BOM); si falla, Windows-1252, que es lo que guarda Excel."""
    try:
        return contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        return contenido.decode("cp1252")


def _separador(primera_linea: str) -> str:
    return ";" if primera_linea.count(";") > primera_linea.count(",") else ","


MILES_CON_PUNTO = re.compile(r"^\d{1,3}(\.\d{3})+$")


def parsear_precio(valor: str) -> Decimal:
    """Acepta 4500, 4500.50, 4500,50, 4.500,50 y 4.500 (punto de miles)."""
    texto = valor.strip().replace(" ", "").replace("$", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif MILES_CON_PUNTO.fullmatch(texto):
        # Con 3 dígitos tras el punto no puede ser decimal (máximo 2): son miles.
        texto = texto.replace(".", "")
    precio = Decimal(texto)
    if not precio.is_finite():
        raise InvalidOperation
    return precio


def validar_csv(texto: str, catalogo: dict[str, ProductoCatalogo]) -> ResultadoValidacion:
    """`catalogo` va indexado por código en mayúsculas."""
    resultado = ResultadoValidacion()
    errores = resultado.errores

    def error(linea: int, codigo: str | None, campo: str | None, mensaje: str) -> None:
        errores.append(ErrorFila(linea, codigo, campo, mensaje))

    lineas = texto.splitlines()
    if not lineas or not lineas[0].strip():
        error(1, None, None, "El archivo está vacío.")
        return resultado

    lector = csv.reader(io.StringIO(texto), delimiter=_separador(lineas[0]))
    cabecera = [c.strip().lower() for c in next(lector)]
    if tuple(cabecera) != COLUMNAS:
        error(
            1,
            None,
            None,
            f"La cabecera debe ser exactamente: {','.join(COLUMNAS)}. "
            f"Se recibió: {','.join(cabecera)}.",
        )
        return resultado

    escalas_vistas: dict[tuple[uuid.UUID, str, int], int] = {}

    for valores in lector:
        linea = lector.line_num
        if len(errores) >= MAX_ERRORES:
            break
        if not any(v.strip() for v in valores):
            continue  # línea en blanco
        if len(valores) != len(COLUMNAS):
            error(linea, None, None, f"Se esperaban 4 columnas y hay {len(valores)}.")
            continue

        codigo_crudo, talle_crudo, cantidad_cruda, precio_crudo = (v.strip() for v in valores)
        codigo = codigo_crudo.upper()
        errores_antes = len(errores)

        producto = catalogo.get(codigo)
        if not codigo:
            error(linea, None, "codigo", "Falta el código del producto.")
        elif producto is None:
            error(linea, codigo, "codigo", f"El código {codigo} no existe en el catálogo.")

        talle = talle_crudo.upper() or None
        if producto and talle and producto.talles and talle not in producto.talles:
            disponibles = ", ".join(sorted(producto.talles))
            error(
                linea,
                codigo,
                "talle",
                f"El talle {talle} no está en el producto (talles: {disponibles}).",
            )

        cantidad = 0
        try:
            cantidad = int(cantidad_cruda)
            if cantidad <= 0:
                raise ValueError
        except ValueError:
            error(
                linea,
                codigo or None,
                "cantidad_minima",
                f"cantidad_minima debe ser un entero mayor a 0 (se recibió '{cantidad_cruda}').",
            )

        precio = Decimal(0)
        try:
            precio = parsear_precio(precio_crudo)
            if precio < 0:
                raise ValueError
            if precio != precio.quantize(Decimal("0.01")):
                raise ValueError
        except (InvalidOperation, ValueError):
            error(
                linea,
                codigo or None,
                "precio_unitario",
                f"precio_unitario debe ser un número >= 0 con hasta 2 decimales "
                f"(se recibió '{precio_crudo}').",
            )

        if len(errores) > errores_antes or producto is None:
            continue

        clave = (producto.id, talle or "", cantidad)
        if clave in escalas_vistas:
            error(
                linea,
                codigo,
                None,
                f"Escala repetida: mismo código, talle y cantidad_minima que la línea "
                f"{escalas_vistas[clave]}.",
            )
            continue
        escalas_vistas[clave] = linea

        resultado.filas.append(
            FilaPrecio(
                linea=linea,
                producto_id=producto.id,
                codigo=codigo,
                talle=talle,
                cantidad_minima=cantidad,
                precio_unitario=precio.quantize(Decimal("0.01")),
            )
        )

    if not errores and not resultado.filas:
        error(1, None, None, "El archivo no tiene filas de precios.")

    return resultado
