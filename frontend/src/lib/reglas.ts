/** Tipos de /api/v1/reglas-comerciales (ver backend/app/schemas/reglas_comerciales.py). */

export type EscalaPor = "producto" | "item";
export type IvaEnPresupuesto = "sumar" | "aclarar";

export interface Respuestas {
  escala_por: EscalaPor | null;
  precios_incluyen_iva: boolean | null;
  alicuota_iva: number | null;
  iva_en_presupuesto: IvaEnPresupuesto | null;
  pedido_minimo_unidades: number | null;
  pedido_minimo_monto: number | null;
  descuento_maximo_porcentaje: number | null;
  validez_dias: number | null;
  condiciones_pago: string | null;
  notas: string | null;
  confirmado_por: string | null;
  confirmado_el: string | null;
}

export type CampoPregunta = Exclude<keyof Respuestas, "notas" | "confirmado_por" | "confirmado_el">;

export interface Pregunta {
  campo: CampoPregunta;
  seccion: string;
  pregunta: string;
  ayuda: string;
  impacto: string;
  aplica: boolean;
  respondida: boolean;
}

export interface Reglas extends Respuestas {
  preguntas: Pregunta[];
  pendientes: number;
  actualizado_por: string | null;
  actualizado_en: string | null;
}

export interface Ficha {
  titulo: string;
  generada_el: string;
  estado: string;
  respuestas: { seccion: string; pregunta: string; respuesta: string }[];
  pendientes: string[];
  notas: string | null;
  texto_whatsapp: string;
}

export const CAMPOS_RESPUESTA: (keyof Respuestas)[] = [
  "escala_por",
  "precios_incluyen_iva",
  "alicuota_iva",
  "iva_en_presupuesto",
  "pedido_minimo_unidades",
  "pedido_minimo_monto",
  "descuento_maximo_porcentaje",
  "validez_dias",
  "condiciones_pago",
  "notas",
  "confirmado_por",
  "confirmado_el",
];

export function soloRespuestas(reglas: Reglas): Respuestas {
  return Object.fromEntries(CAMPOS_RESPUESTA.map((c) => [c, reglas[c]])) as unknown as Respuestas;
}
