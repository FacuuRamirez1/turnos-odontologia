import { apiBlobFetch, apiFetch } from "./client";
import { ApiError } from "./errors";

export const ESTADOS_ASISTENCIA = [
  "creado",
  "confirmado",
  "cancelado",
  "reprogramado",
  "atendido",
  "no_show",
  "devuelto",
] as const;

export const ESTADOS_MAIL = [
  "encolado",
  "enviado",
  "reintentando",
  "fallido",
  "confirmado_desde_mail",
  "cancelado_desde_mail",
] as const;

export interface FiltrosReporte {
  desde: string;
  hasta: string;
  odontologoId?: string;
}

export interface AsistenciaReporte {
  desde: string;
  hasta: string;
  odontologo_id: string | null;
  conteos: Record<string, number>;
}

export interface MailReporte {
  desde: string;
  hasta: string;
  conteos: Record<string, number>;
}

export interface FilaCajaReporte {
  concepto: string;
  fecha: string;
  monto: string;
  turno_id: string;
  pago_id: string;
  devolucion_id: string | null;
  odontologo_id: string;
}

export interface CajaReporte {
  desde: string;
  hasta: string;
  odontologo_id: string | null;
  marca: string;
  total_aprobado: string;
  total_devuelto: string;
  neto: string;
  filas: FilaCajaReporte[];
}

export type ExportacionReporte =
  | "turnos.csv"
  | "turnos.pdf"
  | "caja.csv"
  | "caja.pdf"
  | "auditoria.csv";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isConteos(value: unknown, claves: readonly string[]): value is Record<string, number> {
  return (
    isRecord(value) &&
    claves.every((clave) => typeof value[clave] === "number") &&
    Object.keys(value).length === claves.length
  );
}

function isStringOrNull(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

export function isAsistenciaReporte(value: unknown): value is AsistenciaReporte {
  return (
    isRecord(value) &&
    typeof value.desde === "string" &&
    typeof value.hasta === "string" &&
    isStringOrNull(value.odontologo_id) &&
    isConteos(value.conteos, ESTADOS_ASISTENCIA)
  );
}

export function isMailReporte(value: unknown): value is MailReporte {
  return (
    isRecord(value) &&
    typeof value.desde === "string" &&
    typeof value.hasta === "string" &&
    isConteos(value.conteos, ESTADOS_MAIL)
  );
}

function isFilaCaja(value: unknown): value is FilaCajaReporte {
  return (
    isRecord(value) &&
    typeof value.concepto === "string" &&
    typeof value.fecha === "string" &&
    typeof value.monto === "string" &&
    typeof value.turno_id === "string" &&
    typeof value.pago_id === "string" &&
    isStringOrNull(value.devolucion_id) &&
    typeof value.odontologo_id === "string"
  );
}

export function isCajaReporte(value: unknown): value is CajaReporte {
  return (
    isRecord(value) &&
    typeof value.desde === "string" &&
    typeof value.hasta === "string" &&
    isStringOrNull(value.odontologo_id) &&
    typeof value.marca === "string" &&
    typeof value.total_aprobado === "string" &&
    typeof value.total_devuelto === "string" &&
    typeof value.neto === "string" &&
    Array.isArray(value.filas) &&
    value.filas.every(isFilaCaja)
  );
}

export function buildReporteQuery(filtros: FiltrosReporte): string {
  const params = new URLSearchParams({ desde: filtros.desde, hasta: filtros.hasta });
  if (filtros.odontologoId !== undefined && filtros.odontologoId !== "") {
    params.set("odontologo_id", filtros.odontologoId);
  }
  return params.toString();
}

async function reporteFetch<T>(
  ruta: string,
  filtros: FiltrosReporte,
  guard: (value: unknown) => value is T,
  signal?: AbortSignal,
): Promise<T> {
  const data = await apiFetch<unknown>(`/api/reportes/${ruta}?${buildReporteQuery(filtros)}`, {
    auth: true,
    signal,
  });
  if (!guard(data)) {
    throw new ApiError(502, "El servidor devolvió una respuesta con formato inesperado.");
  }
  return data;
}

export function getAsistencia(
  filtros: FiltrosReporte,
  signal?: AbortSignal,
): Promise<AsistenciaReporte> {
  return reporteFetch("asistencia", filtros, isAsistenciaReporte, signal);
}

export function getCaja(filtros: FiltrosReporte, signal?: AbortSignal): Promise<CajaReporte> {
  return reporteFetch("caja", filtros, isCajaReporte, signal);
}

export function getMailReporte(filtros: FiltrosReporte, signal?: AbortSignal): Promise<MailReporte> {
  return reporteFetch("mail", filtros, isMailReporte, signal);
}

export function descargarExportacion(
  exportacion: ExportacionReporte,
  filtros: FiltrosReporte,
  signal?: AbortSignal,
): Promise<Blob> {
  return apiBlobFetch(`/api/reportes/${exportacion}?${buildReporteQuery(filtros)}`, signal);
}
