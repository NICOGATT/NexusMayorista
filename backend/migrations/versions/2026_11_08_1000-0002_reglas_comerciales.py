"""Reglas comerciales: las respuestas de la fábrica que usa el motor de cálculo.

Una sola fila (id = 1). Los campos en null son preguntas sin responder.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-08 10:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE: tuple[str, ...] = (
    """
    create table reglas_comerciales (
      id                           integer primary key default 1,
      escala_por                   text,
      precios_incluyen_iva         boolean,
      alicuota_iva                 numeric(5,2),
      iva_en_presupuesto           text,
      pedido_minimo_unidades       integer check (pedido_minimo_unidades >= 0),
      pedido_minimo_monto          numeric(12,2) check (pedido_minimo_monto >= 0),
      descuento_maximo_porcentaje  numeric(5,2),
      validez_dias                 integer check (validez_dias > 0),
      condiciones_pago             text,
      notas                        text,
      confirmado_por               text,
      confirmado_el                date,
      actualizado_por              text,
      actualizado_en               timestamptz not null default now(),
      constraint reglas_comerciales_fila_unica check (id = 1),
      constraint reglas_comerciales_escala_por_check
        check (escala_por in ('producto', 'item')),
      constraint reglas_comerciales_iva_en_presupuesto_check
        check (iva_en_presupuesto in ('sumar', 'aclarar')),
      constraint reglas_comerciales_alicuota_iva_check
        check (alicuota_iva >= 0 and alicuota_iva <= 100),
      constraint reglas_comerciales_descuento_maximo_check
        check (descuento_maximo_porcentaje >= 0 and descuento_maximo_porcentaje <= 100)
    )
    """,
    "comment on table reglas_comerciales is "
    "'Respuestas de la fábrica que cambian el cálculo. Una sola fila; null = sin responder.'",
    """
    create trigger trg_reglas_comerciales_actualizado before update on reglas_comerciales
      for each row execute function set_actualizado_en()
    """,
    "insert into reglas_comerciales (id) values (1)",
    "alter table reglas_comerciales enable row level security",
    "create policy equipo_accede_reglas_comerciales on reglas_comerciales for all "
    "to authenticated using (true) with check (true)",
)

DOWNGRADE: tuple[str, ...] = ("drop table if exists reglas_comerciales",)


def upgrade() -> None:
    for sentencia in UPGRADE:
        op.execute(sentencia)


def downgrade() -> None:
    for sentencia in DOWNGRADE:
        op.execute(sentencia)
