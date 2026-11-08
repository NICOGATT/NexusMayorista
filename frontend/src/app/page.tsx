import { redirect } from "next/navigation";

// Hasta que exista el tablero (Día 9), la entrada es la configuración de reglas.
export default function Inicio() {
  redirect("/configuracion/reglas");
}
