"""Reglas comerciales: las preguntas a la fábrica, sus respuestas y la ficha.

Las respuestas se cargan desde el frontend y tienen dos usos:

1. El motor de cálculo las aplica en cada presupuesto (`a_reglas_calculo`).
2. Se genera una ficha para que la fábrica las confirme por escrito
   (`generar_ficha`): una versión para imprimir y un texto para WhatsApp.

Convenciones: un campo en null es una pregunta sin responder. En los mínimos,
0 significa "no hay mínimo"; en el descuento máximo, 100 significa "sin tope".
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import ReglasComerciales
from app.services.calculo import (
    EscalaPor,
    IvaEnPresupuesto,
    ReglasCalculo,
    formato_numero,
    formato_porcentaje,
)

ID_FILA = 1
ALICUOTA_POR_DEFECTO = Decimal("21")


@dataclass(frozen=True)
class Pregunta:
    campo: str
    seccion: str
    pregunta: str
    ayuda: str
    impacto: str


PREGUNTAS: tuple[Pregunta, ...] = (
    Pregunta(
        "escala_por",
        "Precios y escalas",
        "¿La escala de precio se elige por el total del producto (sumando talles y colores) "
        "o por cada ítem por separado?",
        "Ejemplo: 6 remeras M + 6 L. Por producto cuentan 12 y entran en la escala de 12; "
        "por ítem cuentan 6 y 6.",
        "Cambia qué precio unitario toma cada ítem.",
    ),
    Pregunta(
        "precios_incluyen_iva",
        "IVA",
        "¿Los precios de la lista incluyen IVA?",
        "Mirá cómo factura la fábrica: si factura A, los precios suelen ser sin IVA.",
        "Define la leyenda de IVA del presupuesto y si se suma IVA al total.",
    ),
    Pregunta(
        "alicuota_iva",
        "IVA",
        "¿Qué alícuota de IVA corresponde?",
        "En indumentaria suele ser 21 %.",
        "Se usa para sumar o aclarar el IVA.",
    ),
    Pregunta(
        "iva_en_presupuesto",
        "IVA",
        "Si los precios no incluyen IVA, ¿el presupuesto suma el IVA al total "
        'o solo aclara "+ IVA"?',
        "Solo hace falta si los precios son sin IVA.",
        "Cambia el total del presupuesto.",
    ),
    Pregunta(
        "pedido_minimo_unidades",
        "Pedido mínimo y descuentos",
        "¿Hay una cantidad mínima de unidades por pedido?",
        "0 = no hay mínimo.",
        "Si el pedido no llega, el presupuesto queda marcado para revisión.",
    ),
    Pregunta(
        "pedido_minimo_monto",
        "Pedido mínimo y descuentos",
        "¿Hay un monto mínimo por pedido?",
        "0 = no hay monto mínimo. Se compara con el total sin IVA y con el descuento aplicado.",
        "Si el pedido no llega, el presupuesto queda marcado para revisión.",
    ),
    Pregunta(
        "descuento_maximo_porcentaje",
        "Pedido mínimo y descuentos",
        "¿Cuál es el descuento máximo que puede dar un vendedor sin pedir autorización?",
        "0 = ningún descuento sin autorización; 100 = sin tope.",
        "Si un vendedor se pasa, el presupuesto queda marcado para revisión.",
    ),
    Pregunta(
        "validez_dias",
        "Condiciones",
        "¿Cuántos días vale un presupuesto?",
        "Por ejemplo, 7 días por la inflación.",
        "Se muestra en el presupuesto y en el texto para WhatsApp (HU-07).",
    ),
    Pregunta(
        "condiciones_pago",
        "Condiciones",
        "¿Cuáles son las condiciones de pago y de entrega?",
        "Ejemplo: 50 % de seña y saldo contra entrega; envío por transporte a cargo del cliente.",
        "Va al pie del presupuesto y del texto para WhatsApp (HU-07).",
    ),
)

CAMPOS = tuple(p.campo for p in PREGUNTAS)
CAMPOS_CONFIRMACION = ("notas", "confirmado_por", "confirmado_el")


# ------------------------------------------------------------- lectura y guardado


def obtener(db: Session) -> ReglasComerciales:
    """La fila de reglas; si todavía no existe, una vacía sin guardar."""
    return db.get(ReglasComerciales, ID_FILA) or ReglasComerciales(id=ID_FILA)


def guardar(db: Session, valores: dict, *, usuario: str | None) -> ReglasComerciales:
    """Reemplaza todas las respuestas (lo que no viene queda sin responder). No hace commit."""
    fila = db.get(ReglasComerciales, ID_FILA)
    if fila is None:
        fila = ReglasComerciales(id=ID_FILA)
        db.add(fila)
    for campo in (*CAMPOS, *CAMPOS_CONFIRMACION):
        setattr(fila, campo, valores.get(campo))
    if fila.precios_incluyen_iva is not False:
        fila.iva_en_presupuesto = None  # solo aplica a precios sin IVA
    fila.actualizado_por = usuario
    db.flush()
    return fila


def aplica(campo: str, fila: ReglasComerciales) -> bool:
    """`iva_en_presupuesto` solo se pregunta si los precios son sin IVA."""
    return campo != "iva_en_presupuesto" or fila.precios_incluyen_iva is False


def respondida(campo: str, fila: ReglasComerciales) -> bool:
    valor = getattr(fila, campo)
    return valor is not None and valor != ""


def pendientes(fila: ReglasComerciales) -> list[Pregunta]:
    return [p for p in PREGUNTAS if aplica(p.campo, fila) and not respondida(p.campo, fila)]


def a_reglas_calculo(fila: ReglasComerciales) -> ReglasCalculo:
    """Lo que el motor necesita. Lo no respondido queda con el valor por defecto."""
    return ReglasCalculo(
        escala_por=EscalaPor(fila.escala_por) if fila.escala_por else EscalaPor.PRODUCTO,
        precios_incluyen_iva=fila.precios_incluyen_iva,
        alicuota_iva=(fila.alicuota_iva if fila.alicuota_iva is not None else ALICUOTA_POR_DEFECTO),
        iva_en_presupuesto=(
            IvaEnPresupuesto(fila.iva_en_presupuesto) if fila.iva_en_presupuesto else None
        ),
        pedido_minimo_unidades=fila.pedido_minimo_unidades,
        pedido_minimo_monto=fila.pedido_minimo_monto,
        descuento_maximo_porcentaje=fila.descuento_maximo_porcentaje,
    )


# ------------------------------------------------------------------------ ficha


def respuesta_legible(campo: str, valor) -> str:
    """Cómo se lee cada respuesta en la ficha que se le manda a la fábrica."""
    if campo == "escala_por":
        return {
            "producto": "Por producto: se suman todos los talles y colores del mismo producto.",
            "item": "Por ítem: cada talle y color se cuenta por separado.",
        }[valor]
    if campo == "precios_incluyen_iva":
        return "Sí, los precios incluyen IVA." if valor else "No, los precios son sin IVA."
    if campo == "alicuota_iva":
        return f"{formato_porcentaje(valor)} %"
    if campo == "iva_en_presupuesto":
        return {
            "sumar": "Se suma el IVA al total del presupuesto.",
            "aclarar": 'El total queda sin IVA y se aclara "+ IVA".',
        }[valor]
    if campo == "pedido_minimo_unidades":
        return "No hay mínimo." if valor == 0 else f"{formato_numero(valor)} unidades."
    if campo == "pedido_minimo_monto":
        return "No hay monto mínimo." if valor == 0 else f"${formato_numero(valor)}."
    if campo == "descuento_maximo_porcentaje":
        if valor == 0:
            return "Ningún descuento sin autorización."
        if valor == 100:
            return "Sin tope."
        return f"Hasta {formato_porcentaje(valor)} %."
    if campo == "validez_dias":
        return "1 día." if valor == 1 else f"{valor} días."
    return str(valor).strip()


@dataclass(frozen=True)
class Respuesta:
    seccion: str
    pregunta: str
    respuesta: str


@dataclass(frozen=True)
class Ficha:
    titulo: str
    generada_el: date
    estado: str
    respuestas: list[Respuesta]
    pendientes: list[str]
    notas: str | None
    texto_whatsapp: str


def _fecha(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def generar_ficha(fila: ReglasComerciales, *, hoy: date) -> Ficha:
    respuestas = [
        Respuesta(p.seccion, p.pregunta, respuesta_legible(p.campo, getattr(fila, p.campo)))
        for p in PREGUNTAS
        if aplica(p.campo, fila) and respondida(p.campo, fila)
    ]
    faltan = [p.pregunta for p in pendientes(fila)]
    if fila.confirmado_por:
        cuando = f" el {_fecha(fila.confirmado_el)}" if fila.confirmado_el else ""
        estado = f"Confirmada por {fila.confirmado_por}{cuando}."
    else:
        estado = "Pendiente de confirmación por la fábrica."
    notas = (fila.notas or "").strip() or None
    titulo = "Definiciones comerciales"

    lineas = [f"*{titulo}*", f"Generada el {_fecha(hoy)}. {estado}"]
    seccion_actual = None
    for r in respuestas:
        if r.seccion != seccion_actual:
            seccion_actual = r.seccion
            lineas += ["", f"*{r.seccion}*"]
        lineas += [f"• {r.pregunta}", f"  → {r.respuesta}"]
    if faltan:
        lineas += ["", "*Nos falta que nos respondan*"]
        lineas += [f"• {p}" for p in faltan]
    if notas:
        lineas += ["", f"*Notas:* {notas}"]
    lineas += [
        "",
        "¿Nos confirman que está todo bien o qué hay que corregir? ¡Gracias!",
    ]

    return Ficha(
        titulo=titulo,
        generada_el=hoy,
        estado=estado,
        respuestas=respuestas,
        pendientes=faltan,
        notas=notas,
        texto_whatsapp="\n".join(lineas),
    )
