"""Esquema inicial del Sprint 1 (sección 2 de la documentación técnica).

Crea los 4 tipos enumerados, las 8 tablas, los triggers de `actualizado_en` y de
historial de etapas, y activa Row Level Security con acceso para usuarios autenticados.

Revision ID: 0001
Revises:
Create Date: 2026-11-05 11:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLAS = (
    "clientes",
    "productos",
    "listas_precios",
    "precios",
    "presupuestos",
    "presupuesto_items",
    "interacciones",
    "historial_etapas",
)

# Cada string es una sentencia: se ejecutan de a una (los cuerpos $$...$$ llevan ";").
UPGRADE: tuple[str, ...] = (
    # ---------------------------------------------------------------- tipos
    "create type canal_tipo as enum ('whatsapp', 'instagram', 'manual')",
    "create type direccion_mensaje as enum ('entrante', 'saliente')",
    "create type estado_ia as enum ('pendiente', 'procesando', 'procesado', 'error', 'no_aplica')",
    "create type etapa_presupuesto as enum "
    "('nuevo', 'borrador', 'enviado', 'negociacion', 'ganado', 'perdido')",
    # ------------------------------------------- función genérica actualizado_en
    """
    create or replace function set_actualizado_en() returns trigger as $$
    begin
      new.actualizado_en := now();
      return new;
    end;
    $$ language plpgsql
    """,
    # ------------------------------------------------------------- clientes
    """
    create table clientes (
      id                 uuid primary key default gen_random_uuid(),
      nombre             text,
      razon_social       text,
      cuit               text,
      telefono_whatsapp  text unique,
      instagram_id       text unique,
      instagram_usuario  text,
      email              text,
      ciudad             text,
      provincia          text,
      tipo               text not null default 'prospecto'
                         check (tipo in ('prospecto', 'cliente')),
      canal_origen       canal_tipo not null,
      notas              text,
      creado_en          timestamptz not null default now(),
      actualizado_en     timestamptz not null default now(),
      constraint clientes_identificador_chk
        check (telefono_whatsapp is not null or instagram_id is not null or email is not null)
    )
    """,
    "comment on column clientes.telefono_whatsapp is 'Formato E.164: +5491122334455'",
    "comment on column clientes.instagram_id is 'IGSID que envía Meta'",
    """
    create trigger trg_clientes_actualizado before update on clientes
      for each row execute function set_actualizado_en()
    """,
    # ------------------------------------------------------------ productos
    """
    create table productos (
      id             uuid primary key default gen_random_uuid(),
      codigo         text not null unique,
      nombre         text not null,
      categoria      text not null,
      descripcion    text,
      talles         text[] not null default '{}',
      colores        text[] not null default '{}',
      alias          text[] not null default '{}',
      activo         boolean not null default true,
      creado_en      timestamptz not null default now(),
      actualizado_en timestamptz not null default now()
    )
    """,
    "comment on column productos.codigo is 'SKU base, ej. REM-ALG-LISA'",
    "comment on column productos.alias is 'Sinónimos que usan los clientes'",
    """
    create trigger trg_productos_actualizado before update on productos
      for each row execute function set_actualizado_en()
    """,
    # ------------------------------------------------------- listas de precios
    """
    create table listas_precios (
      id             uuid primary key default gen_random_uuid(),
      nombre         text not null,
      moneda         char(3) not null default 'ARS',
      vigente_desde  date not null,
      vigente_hasta  date,
      activa         boolean not null default false,
      creado_en      timestamptz not null default now()
    )
    """,
    # Solo una lista activa a la vez
    """
    create unique index ux_listas_precios_unica_activa
      on listas_precios (activa) where activa
    """,
    # -------------------------------------------------------------- precios
    """
    create table precios (
      id               uuid primary key default gen_random_uuid(),
      lista_id         uuid not null references listas_precios(id) on delete cascade,
      producto_id      uuid not null references productos(id),
      talle            text,
      cantidad_minima  integer not null default 1 check (cantidad_minima > 0),
      precio_unitario  numeric(12,2) not null check (precio_unitario >= 0)
    )
    """,
    "comment on column precios.talle is 'null = aplica a todos los talles'",
    # Escalas: mismo producto/talle con distintos mínimos (1, 12, 50 unidades...)
    """
    create unique index ux_precios_escala
      on precios (lista_id, producto_id, coalesce(talle, ''), cantidad_minima)
    """,
    # ----------------------------------------- presupuestos (= tarjetas del tablero)
    """
    create table presupuestos (
      id                 uuid primary key default gen_random_uuid(),
      numero             bigint generated always as identity unique,
      cliente_id         uuid not null references clientes(id),
      lista_id           uuid not null references listas_precios(id),
      etapa              etapa_presupuesto not null default 'nuevo',
      posicion_tablero   integer not null default 0,
      moneda             char(3) not null default 'ARS',
      subtotal           numeric(14,2) not null default 0,
      descuento          numeric(14,2) not null default 0,
      total              numeric(14,2) not null default 0,
      requiere_revision  boolean not null default false,
      observaciones      text,
      valido_hasta       date,
      asignado_a         uuid references auth.users(id),
      motivo_perdida     text,
      creado_en          timestamptz not null default now(),
      actualizado_en     timestamptz not null default now()
    )
    """,
    "comment on column presupuestos.numero is 'Número visible: P-000123'",
    "create index ix_presupuestos_tablero on presupuestos (etapa, posicion_tablero)",
    "create index ix_presupuestos_cliente on presupuestos (cliente_id)",
    """
    create trigger trg_presupuestos_actualizado before update on presupuestos
      for each row execute function set_actualizado_en()
    """,
    # ---------------------------------------------------- ítems del presupuesto
    """
    create table presupuesto_items (
      id                    uuid primary key default gen_random_uuid(),
      presupuesto_id        uuid not null references presupuestos(id) on delete cascade,
      producto_id           uuid references productos(id),
      descripcion_original  text not null,
      talle                 text,
      color                 text,
      cantidad              integer not null check (cantidad > 0),
      precio_unitario       numeric(12,2),
      subtotal              numeric(14,2) generated always as (cantidad * precio_unitario) stored,
      confianza             numeric(3,2) check (confianza between 0 and 1),
      requiere_revision     boolean not null default false,
      nota                  text
    )
    """,
    "create index ix_items_presupuesto on presupuesto_items (presupuesto_id)",
    # ------------------------------------------------- interacciones (mensajes)
    """
    create table interacciones (
      id               uuid primary key default gen_random_uuid(),
      cliente_id       uuid not null references clientes(id),
      presupuesto_id   uuid references presupuestos(id),
      canal            canal_tipo not null,
      direccion        direccion_mensaje not null,
      id_externo       text unique,
      contenido        text,
      payload_crudo    jsonb,
      estado_ia        estado_ia not null default 'pendiente',
      resultado_ia     jsonb,
      modelo_ia        text,
      tokens_entrada   integer,
      tokens_salida    integer,
      error_ia         text,
      recibido_en      timestamptz not null default now(),
      procesado_en     timestamptz
    )
    """,
    "comment on column interacciones.id_externo is 'wamid / mid de Meta: evita duplicados'",
    "create index ix_interacciones_cliente on interacciones (cliente_id, recibido_en desc)",
    """
    create index ix_interacciones_pendientes on interacciones (estado_ia)
      where estado_ia in ('pendiente', 'error')
    """,
    # ------------------------------------------- historial de movimientos
    """
    create table historial_etapas (
      id               bigint generated always as identity primary key,
      presupuesto_id   uuid not null references presupuestos(id) on delete cascade,
      etapa_anterior   etapa_presupuesto,
      etapa_nueva      etapa_presupuesto not null,
      cambiado_por     uuid references auth.users(id),
      cambiado_en      timestamptz not null default now()
    )
    """,
    """
    create or replace function registrar_cambio_etapa() returns trigger as $$
    begin
      if new.etapa is distinct from old.etapa then
        insert into historial_etapas (presupuesto_id, etapa_anterior, etapa_nueva, cambiado_por)
        values (new.id, old.etapa, new.etapa, auth.uid());
      end if;
      return new;
    end;
    $$ language plpgsql security definer set search_path = public
    """,
    """
    create trigger trg_presupuestos_etapa after update of etapa on presupuestos
      for each row execute function registrar_cambio_etapa()
    """,
    # ------------------------------------------------------ Row Level Security
    *(f"alter table {t} enable row level security" for t in TABLAS),
    # Sprint 1: todo el equipo autenticado accede a todo; en el Sprint 2 se
    # restringe por vendedor asignado.
    *(
        f"create policy equipo_accede_{t} on {t} for all to authenticated "
        "using (true) with check (true)"
        for t in TABLAS
    ),
    # Supabase expone `public` por su API REST: sin RLS, cualquiera con la anon
    # key podría leer o borrar la tabla de versiones de Alembic.
    "alter table alembic_version enable row level security",
)

DOWNGRADE: tuple[str, ...] = (
    "drop table if exists historial_etapas",
    "drop table if exists interacciones",
    "drop table if exists presupuesto_items",
    "drop table if exists presupuestos",
    "drop table if exists precios",
    "drop table if exists listas_precios",
    "drop table if exists productos",
    "drop table if exists clientes",
    "drop function if exists registrar_cambio_etapa()",
    "drop function if exists set_actualizado_en()",
    "drop type if exists etapa_presupuesto",
    "drop type if exists estado_ia",
    "drop type if exists direccion_mensaje",
    "drop type if exists canal_tipo",
)


def upgrade() -> None:
    for sentencia in UPGRADE:
        op.execute(sentencia)


def downgrade() -> None:
    for sentencia in DOWNGRADE:
        op.execute(sentencia)
