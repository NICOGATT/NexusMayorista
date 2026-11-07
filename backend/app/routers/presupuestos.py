from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errores import ErrorAPI
from app.models import ListaPrecios
from app.schemas.presupuestos import PresupuestoCalculadoSalida, PresupuestoCalcular
from app.services.calculo import ErrorCalculo, ItemPedido, calcular_presupuesto
from app.services.listas_precios import lista_para_calculo

router = APIRouter(prefix="/presupuestos", tags=["presupuestos"])

DB = Annotated[Session, Depends(get_db)]


@router.post(
    "/calcular",
    summary="Calcula un presupuesto sin guardarlo",
    description=(
        "Recibe ítems ya estructurados (`producto_id` o `codigo`, `talle`, `color`, "
        "`cantidad`) y devuelve precios, subtotales y total con la lista activa (o la "
        "indicada en `lista_id`). La escala se elige por la cantidad total de cada "
        "producto; el precio por talle manda sobre el general. Los ítems sin producto o "
        "sin precio no suman y marcan el presupuesto para revisión."
    ),
)
def calcular(datos: PresupuestoCalcular, db: DB) -> PresupuestoCalculadoSalida:
    if datos.lista_id is not None:
        lista = db.get(ListaPrecios, datos.lista_id)
        if lista is None:
            raise ErrorAPI(status.HTTP_404_NOT_FOUND, "lista_no_encontrada", str(datos.lista_id))
    else:
        lista = db.scalar(select(ListaPrecios).where(ListaPrecios.activa.is_(True)))
        if lista is None:
            raise ErrorAPI(
                status.HTTP_409_CONFLICT,
                "sin_lista_activa",
                "No hay una lista de precios activa. Importá una y activala.",
            )

    foto = lista_para_calculo(
        db,
        lista,
        producto_ids={i.producto_id for i in datos.items if i.producto_id},
        codigos={i.codigo for i in datos.items if i.codigo and not i.producto_id},
    )
    try:
        resultado = calcular_presupuesto(
            [ItemPedido(**i.model_dump()) for i in datos.items],
            foto,
            descuento=datos.descuento,
            descuento_porcentaje=datos.descuento_porcentaje,
        )
    except ErrorCalculo as exc:
        raise ErrorAPI(status.HTTP_422_UNPROCESSABLE_CONTENT, "calculo_invalido", str(exc)) from exc
    return PresupuestoCalculadoSalida.model_validate(asdict(resultado))
