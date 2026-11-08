"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, mensajeDeError } from "@/lib/api";
import type { Ficha } from "@/lib/reglas";

function fecha(iso: string) {
  const [anio, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${anio}`;
}

export default function FichaFabrica() {
  const [ficha, setFicha] = useState<Ficha | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copiado, setCopiado] = useState(false);

  useEffect(() => {
    api<Ficha>("/reglas-comerciales/ficha")
      .then(setFicha)
      .catch((e) => setError(mensajeDeError(e)));
  }, []);

  if (error) return <p className="rounded-md bg-red-50 p-4 text-sm text-red-700">{error}</p>;
  if (!ficha) return <p className="text-sm text-neutral-500">Generando ficha…</p>;

  async function copiar() {
    await navigator.clipboard.writeText(ficha!.texto_whatsapp);
    setCopiado(true);
    setTimeout(() => setCopiado(false), 2500);
  }

  const secciones = [...new Set(ficha.respuestas.map((r) => r.seccion))];

  return (
    <div className="space-y-6">
      <div className="no-imprimir flex flex-wrap items-center gap-3">
        <Link href="/configuracion/reglas" className="text-sm text-neutral-500 hover:text-neutral-900">
          ← Volver a las respuestas
        </Link>
        <div className="ml-auto flex gap-2">
          <button
            onClick={copiar}
            className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
          >
            {copiado ? "¡Copiado!" : "Copiar para WhatsApp"}
          </button>
          <button
            onClick={() => window.print()}
            className="rounded-md border border-neutral-300 bg-white px-4 py-2 text-sm font-medium hover:bg-neutral-50"
          >
            Imprimir o guardar PDF
          </button>
        </div>
      </div>

      <article className="rounded-xl border border-neutral-200 bg-white p-8 print:border-0 print:p-0">
        <header className="border-b border-neutral-200 pb-4">
          <h1 className="text-2xl font-semibold">{ficha.titulo}</h1>
          <p className="mt-1 text-sm text-neutral-600">
            Generada el {fecha(ficha.generada_el)} · {ficha.estado}
          </p>
        </header>

        {ficha.respuestas.length === 0 && (
          <p className="mt-6 text-sm text-neutral-500">Todavía no hay respuestas cargadas.</p>
        )}

        {secciones.map((seccion) => (
          <section key={seccion} className="mt-6">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">
              {seccion}
            </h2>
            <dl className="mt-2 divide-y divide-neutral-100">
              {ficha.respuestas
                .filter((r) => r.seccion === seccion)
                .map((r) => (
                  <div key={r.pregunta} className="grid gap-1 py-3 sm:grid-cols-2 sm:gap-6">
                    <dt className="text-sm text-neutral-600">{r.pregunta}</dt>
                    <dd className="text-sm font-medium">{r.respuesta}</dd>
                  </div>
                ))}
            </dl>
          </section>
        ))}

        {ficha.pendientes.length > 0 && (
          <section className="mt-6 rounded-lg bg-amber-50 p-4 print:bg-white print:p-0">
            <h2 className="text-sm font-semibold text-amber-800 print:text-neutral-900">
              Nos falta que nos respondan
            </h2>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
              {ficha.pendientes.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </section>
        )}

        {ficha.notas && (
          <section className="mt-6">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">Notas</h2>
            <p className="mt-2 text-sm">{ficha.notas}</p>
          </section>
        )}

        <footer className="mt-12 hidden grid-cols-2 gap-12 text-sm text-neutral-600 print:grid">
          <div className="border-t border-neutral-400 pt-2">Firma y aclaración (fábrica)</div>
          <div className="border-t border-neutral-400 pt-2">Fecha</div>
        </footer>
      </article>

      <details className="no-imprimir rounded-xl border border-neutral-200 bg-white p-5">
        <summary className="cursor-pointer text-sm font-medium">Ver el texto para WhatsApp</summary>
        <pre className="mt-3 whitespace-pre-wrap font-sans text-sm text-neutral-700">
          {ficha.texto_whatsapp}
        </pre>
      </details>
    </div>
  );
}
