import { supabase } from "./supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Error con el formato único de la API: `{ "error": ..., "detalle": ... }`. */
export class ErrorApi extends Error {
  constructor(
    public status: number,
    public codigo: string,
    public detalle: unknown,
  ) {
    super(typeof detalle === "string" ? detalle : codigo);
  }
}

/** Llama a /api/v1 con el JWT de la sesión de Supabase. */
export async function api<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;

  const respuesta = await fetch(`${API_URL}/api/v1${ruta}`, {
    ...opciones,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...opciones.headers,
    },
  });

  if (!respuesta.ok) {
    const cuerpo = await respuesta.json().catch(() => ({}));
    if (respuesta.status === 401) {
      await supabase.auth.signOut();
    }
    throw new ErrorApi(respuesta.status, cuerpo.error ?? "error", cuerpo.detalle);
  }
  return respuesta.json() as Promise<T>;
}

/** Texto legible para mostrar un error de la API. */
export function mensajeDeError(error: unknown): string {
  if (error instanceof ErrorApi) {
    if (Array.isArray(error.detalle)) {
      return error.detalle
        .map((d: { campo?: string; mensaje?: string; msg?: string }) =>
          [d.campo, d.mensaje ?? d.msg].filter(Boolean).join(": "),
        )
        .join(" · ");
    }
    return error.message;
  }
  if (error instanceof TypeError) {
    return "No se pudo conectar con la API. ¿Está corriendo el backend?";
  }
  return "Error inesperado.";
}
