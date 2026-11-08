"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { supabase } from "@/lib/supabase";

function FormularioLogin() {
  const router = useRouter();
  const volver = useSearchParams().get("volver") || "/";
  const [email, setEmail] = useState("");
  const [clave, setClave] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function entrar(evento: React.FormEvent) {
    evento.preventDefault();
    setEnviando(true);
    setError(null);
    const { error } = await supabase.auth.signInWithPassword({ email, password: clave });
    setEnviando(false);
    if (error) {
      setError("Email o contraseña incorrectos.");
      return;
    }
    router.replace(volver.startsWith("/") ? volver : "/");
  }

  return (
    <form
      onSubmit={entrar}
      className="w-full max-w-sm space-y-4 rounded-xl border border-neutral-200 bg-white p-6 shadow-sm"
    >
      <h1 className="text-lg font-semibold">Entrar a NexusMayorista</h1>
      <label className="block text-sm">
        Email
        <input
          type="email"
          required
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2"
        />
      </label>
      <label className="block text-sm">
        Contraseña
        <input
          type="password"
          required
          autoComplete="current-password"
          value={clave}
          onChange={(e) => setClave(e.target.value)}
          className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2"
        />
      </label>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button
        type="submit"
        disabled={enviando}
        className="w-full rounded-md bg-neutral-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {enviando ? "Entrando…" : "Entrar"}
      </button>
    </form>
  );
}

export default function Login() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <Suspense>
        <FormularioLogin />
      </Suspense>
    </main>
  );
}
