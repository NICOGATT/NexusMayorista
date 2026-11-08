"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { api, mensajeDeError } from "@/lib/api";
import {
  type CampoPregunta,
  type Pregunta,
  type Reglas,
  type Respuestas,
  soloRespuestas,
} from "@/lib/reglas";

type Opcion = { valor: string | boolean; etiqueta: string };
type Atajo = { valor: number; etiqueta: string };

/** Cómo se responde cada pregunta. El texto de la pregunta viene de la API. */
const CONTROLES: Record<
  CampoPregunta,
  | { tipo: "opciones"; opciones: Opcion[] }
  | { tipo: "numero"; sufijo?: string; prefijo?: string; paso?: number; atajos?: Atajo[] }
  | { tipo: "texto" }
> = {
  escala_por: {
    tipo: "opciones",
    opciones: [
      { valor: "producto", etiqueta: "Por producto (sumando talles y colores)" },
      { valor: "item", etiqueta: "Por ítem (cada talle y color por separado)" },
    ],
  },
  precios_incluyen_iva: {
    tipo: "opciones",
    opciones: [
      { valor: true, etiqueta: "Sí, incluyen IVA" },
      { valor: false, etiqueta: "No, son sin IVA" },
    ],
  },
  alicuota_iva: {
    tipo: "numero",
    sufijo: "%",
    paso: 0.5,
    atajos: [
      { valor: 21, etiqueta: "21 % (lo habitual en ropa)" },
      { valor: 10.5, etiqueta: "10,5 %" },
    ],
  },
  iva_en_presupuesto: {
    tipo: "opciones",
    opciones: [
      { valor: "sumar", etiqueta: "Sumar el IVA al total" },
      { valor: "aclarar", etiqueta: 'Dejar el total sin IVA y aclarar "+ IVA"' },
    ],
  },
  pedido_minimo_unidades: {
    tipo: "numero",
    sufijo: "unidades",
    atajos: [{ valor: 0, etiqueta: "No hay mínimo" }],
  },
  pedido_minimo_monto: {
    tipo: "numero",
    prefijo: "$",
    atajos: [{ valor: 0, etiqueta: "No hay monto mínimo" }],
  },
  descuento_maximo_porcentaje: {
    tipo: "numero",
    sufijo: "%",
    paso: 0.5,
    atajos: [
      { valor: 0, etiqueta: "Ninguno sin autorización" },
      { valor: 100, etiqueta: "Sin tope" },
    ],
  },
  validez_dias: { tipo: "numero", sufijo: "días", atajos: [{ valor: 7, etiqueta: "7 días" }] },
  condiciones_pago: { tipo: "texto" },
};

function respondida(valor: unknown) {
  return valor !== null && valor !== undefined && valor !== "";
}

/** El porcentaje de IVA y si se suma o se aclara solo importan con precios sin IVA. */
const SOLO_SI_PRECIOS_SIN_IVA: CampoPregunta[] = ["alicuota_iva", "iva_en_presupuesto"];

function aplica(campo: CampoPregunta, r: Respuestas) {
  return !SOLO_SI_PRECIOS_SIN_IVA.includes(campo) || r.precios_incluyen_iva === false;
}

export default function ReglasComerciales() {
  const [reglas, setReglas] = useState<Reglas | null>(null);
  const [respuestas, setRespuestas] = useState<Respuestas | null>(null);
  const [guardadas, setGuardadas] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    api<Reglas>("/reglas-comerciales")
      .then((r) => {
        setReglas(r);
        setRespuestas(soloRespuestas(r));
        setGuardadas(JSON.stringify(soloRespuestas(r)));
      })
      .catch((e) => setError(mensajeDeError(e)));
  }, []);

  const secciones = useMemo(() => {
    const grupos = new Map<string, Pregunta[]>();
    for (const p of reglas?.preguntas ?? []) {
      grupos.set(p.seccion, [...(grupos.get(p.seccion) ?? []), p]);
    }
    return [...grupos.entries()];
  }, [reglas]);

  if (error && !respuestas) {
    return <p className="rounded-md bg-red-50 p-4 text-sm text-red-700">{error}</p>;
  }
  if (!reglas || !respuestas) {
    return <p className="text-sm text-neutral-500">Cargando preguntas…</p>;
  }

  const r = respuestas;
  const aplicables = reglas.preguntas.filter((p) => aplica(p.campo, r));
  const hechas = aplicables.filter((p) => respondida(r[p.campo])).length;
  const hayCambios = JSON.stringify(r) !== guardadas;

  function cambiar<K extends keyof Respuestas>(campo: K, valor: Respuestas[K]) {
    setRespuestas((actual) => (actual ? { ...actual, [campo]: valor } : actual));
    setAviso(null);
  }

  async function guardar() {
    setGuardando(true);
    setError(null);
    try {
      const nuevas = await api<Reglas>("/reglas-comerciales", {
        method: "PUT",
        body: JSON.stringify(r),
      });
      setReglas(nuevas);
      setRespuestas(soloRespuestas(nuevas));
      setGuardadas(JSON.stringify(soloRespuestas(nuevas)));
      setAviso("Guardado. Desde ahora el cálculo de presupuestos usa estas reglas.");
    } catch (e) {
      setError(mensajeDeError(e));
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className="space-y-8 pb-24">
      <div>
        <h1 className="text-2xl font-semibold">Reglas comerciales</h1>
        <p className="mt-2 max-w-2xl text-sm text-neutral-600">
          Las preguntas que hay que hacerle a la fábrica. Lo que respondas se aplica al cálculo de
          cada presupuesto y arma una ficha para que la fábrica lo confirme por escrito. Lo que
          quede sin responder usa el comportamiento por defecto.
        </p>
        <div className="mt-4 flex items-center gap-3">
          <div className="h-2 w-48 overflow-hidden rounded-full bg-neutral-200">
            <div
              className="h-full bg-emerald-500 transition-all"
              style={{ width: `${(hechas / Math.max(aplicables.length, 1)) * 100}%` }}
            />
          </div>
          <span className="text-sm text-neutral-600">
            {hechas} de {aplicables.length} respondidas
          </span>
        </div>
      </div>

      {secciones.map(([seccion, preguntas]) => (
        <section key={seccion} className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">
            {seccion}
          </h2>
          {preguntas.map((p) => (
            <TarjetaPregunta
              key={p.campo}
              pregunta={p}
              valor={r[p.campo]}
              aplica={aplica(p.campo, r)}
              onCambio={(valor) => cambiar(p.campo, valor as never)}
            />
          ))}
        </section>
      ))}

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">
          Confirmación de la fábrica
        </h2>
        <div className="grid gap-4 rounded-xl border border-neutral-200 bg-white p-5 sm:grid-cols-2">
          <label className="block text-sm">
            ¿Quién de la fábrica lo confirmó?
            <input
              value={r.confirmado_por ?? ""}
              onChange={(e) => cambiar("confirmado_por", e.target.value || null)}
              placeholder="Ej.: Marta, administración"
              className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2"
            />
          </label>
          <label className="block text-sm">
            ¿Cuándo?
            <input
              type="date"
              value={r.confirmado_el ?? ""}
              onChange={(e) => cambiar("confirmado_el", e.target.value || null)}
              className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2"
            />
          </label>
          <label className="block text-sm sm:col-span-2">
            Notas
            <textarea
              rows={2}
              value={r.notas ?? ""}
              onChange={(e) => cambiar("notas", e.target.value || null)}
              placeholder="Cualquier aclaración que haya dado la fábrica"
              className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2"
            />
          </label>
        </div>
      </section>

      {reglas.actualizado_por && (
        <p className="text-xs text-neutral-500">
          Última modificación: {reglas.actualizado_por}
          {reglas.actualizado_en &&
            ` · ${new Date(reglas.actualizado_en).toLocaleString("es-AR")}`}
        </p>
      )}

      <div className="fixed inset-x-0 bottom-0 border-t border-neutral-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-4xl flex-wrap items-center gap-3 px-4 py-3">
          <button
            onClick={guardar}
            disabled={guardando || !hayCambios}
            className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
          >
            {guardando ? "Guardando…" : "Guardar respuestas"}
          </button>
          <Link
            href="/configuracion/reglas/ficha"
            aria-disabled={hayCambios}
            className={`rounded-md border border-neutral-300 px-4 py-2 text-sm font-medium ${
              hayCambios ? "pointer-events-none opacity-40" : "hover:bg-neutral-50"
            }`}
          >
            Generar ficha para la fábrica
          </Link>
          <span className="text-sm">
            {error && <span className="text-red-600">{error}</span>}
            {!error && aviso && <span className="text-emerald-700">{aviso}</span>}
            {!error && !aviso && hayCambios && (
              <span className="text-amber-700">Hay cambios sin guardar.</span>
            )}
          </span>
        </div>
      </div>
    </div>
  );
}

function TarjetaPregunta({
  pregunta,
  valor,
  aplica,
  onCambio,
}: {
  pregunta: Pregunta;
  valor: Respuestas[CampoPregunta];
  aplica: boolean;
  onCambio: (valor: string | number | boolean | null) => void;
}) {
  const control = CONTROLES[pregunta.campo];
  const lista = respondida(valor);
  const nombre = `pregunta-${pregunta.campo}`;

  return (
    <div
      className={`rounded-xl border bg-white p-5 ${
        aplica ? "border-neutral-200" : "border-dashed border-neutral-200 opacity-50"
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <p className="font-medium">{pregunta.pregunta}</p>
        <span
          className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
            !aplica
              ? "bg-neutral-100 text-neutral-500"
              : lista
                ? "bg-emerald-50 text-emerald-700"
                : "bg-amber-50 text-amber-700"
          }`}
        >
          {!aplica ? "No hace falta" : lista ? "Respondida" : "Sin responder"}
        </span>
      </div>
      <p className="mt-1 text-sm text-neutral-500">{pregunta.ayuda}</p>

      <fieldset disabled={!aplica} className="mt-4">
        {control.tipo === "opciones" && (
          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
            {[...control.opciones, { valor: null, etiqueta: "Todavía no sé" }].map((o) => (
              <label
                key={String(o.valor)}
                className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm ${
                  valor === o.valor
                    ? "border-neutral-900 bg-neutral-50"
                    : "border-neutral-200 hover:border-neutral-400"
                }`}
              >
                <input
                  type="radio"
                  name={nombre}
                  checked={valor === o.valor}
                  onChange={() => onCambio(o.valor)}
                />
                {o.etiqueta}
              </label>
            ))}
          </div>
        )}

        {control.tipo === "numero" && (
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center rounded-md border border-neutral-300 focus-within:border-neutral-900">
              {control.prefijo && <span className="pl-3 text-sm text-neutral-500">{control.prefijo}</span>}
              <input
                type="number"
                min={0}
                step={control.paso ?? 1}
                value={valor === null || valor === undefined ? "" : String(valor)}
                onChange={(e) => onCambio(e.target.value === "" ? null : Number(e.target.value))}
                placeholder="Sin responder"
                className="w-36 rounded-md px-3 py-2 text-sm outline-none"
              />
              {control.sufijo && <span className="pr-3 text-sm text-neutral-500">{control.sufijo}</span>}
            </div>
            {control.atajos?.map((a) => (
              <button
                key={a.valor}
                type="button"
                onClick={() => onCambio(a.valor)}
                className={`rounded-md border px-3 py-2 text-sm ${
                  valor === a.valor
                    ? "border-neutral-900 bg-neutral-50"
                    : "border-neutral-200 hover:border-neutral-400"
                }`}
              >
                {a.etiqueta}
              </button>
            ))}
            {lista && (
              <button
                type="button"
                onClick={() => onCambio(null)}
                className="px-2 text-sm text-neutral-500 underline-offset-2 hover:underline"
              >
                Borrar respuesta
              </button>
            )}
          </div>
        )}

        {control.tipo === "texto" && (
          <textarea
            rows={3}
            value={(valor as string | null) ?? ""}
            onChange={(e) => onCambio(e.target.value || null)}
            placeholder="Sin responder"
            className="w-full rounded-md border border-neutral-300 px-3 py-2 text-sm"
          />
        )}
      </fieldset>

      <p className="mt-3 text-xs text-neutral-500">
        <span className="font-medium text-neutral-600">Qué cambia en el sistema:</span>{" "}
        {pregunta.impacto}
      </p>
    </div>
  );
}
