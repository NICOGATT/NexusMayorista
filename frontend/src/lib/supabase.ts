import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

/** false si falta completar frontend/.env.local (y reiniciar `npm run dev`). */
export const supabaseConfigurado = Boolean(url && anonKey);

if (!supabaseConfigurado) {
  console.warn("Faltan NEXT_PUBLIC_SUPABASE_URL o NEXT_PUBLIC_SUPABASE_ANON_KEY en .env.local");
}

export const supabase = createClient(url || "http://localhost", anonKey || "sin-clave");
