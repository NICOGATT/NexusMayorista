"use client";

import type { Session } from "@supabase/supabase-js";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { supabase } from "@/lib/supabase";

const SECCIONES = [{ href: "/configuracion/reglas", nombre: "Reglas comerciales" }];

/** Muestra el contenido solo con sesión iniciada; si no, manda al login. */
export function ConSesion({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const ruta = usePathname();
  const [sesion, setSesion] = useState<Session | null | undefined>(undefined);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSesion(data.session));
    const { data } = supabase.auth.onAuthStateChange((_evento, nueva) => setSesion(nueva));
    return () => data.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (sesion === null) router.replace(`/login?volver=${encodeURIComponent(ruta)}`);
  }, [sesion, router, ruta]);

  if (!sesion) {
    return <p className="p-8 text-sm text-neutral-500">Cargando…</p>;
  }

  return (
    <div className="min-h-screen">
      <header className="no-imprimir border-b border-neutral-200 bg-white">
        <div className="mx-auto flex max-w-4xl items-center gap-6 px-4 py-3">
          <span className="font-semibold">NexusMayorista</span>
          <nav className="flex gap-4 text-sm">
            {SECCIONES.map((s) => (
              <Link
                key={s.href}
                href={s.href}
                className={
                  ruta.startsWith(s.href)
                    ? "font-medium text-neutral-900"
                    : "text-neutral-500 hover:text-neutral-900"
                }
              >
                {s.nombre}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm text-neutral-500">
            <span className="hidden sm:inline">{sesion.user.email}</span>
            <button
              onClick={() => supabase.auth.signOut()}
              className="rounded-md px-2 py-1 hover:bg-neutral-100 hover:text-neutral-900"
            >
              Salir
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-4xl px-4 py-8">{children}</main>
    </div>
  );
}
