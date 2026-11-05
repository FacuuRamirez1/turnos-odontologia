export type UserRole = "odontologo" | "recepcionista" | "admin" | "paciente";

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface LogoutResponse {
  ok: boolean;
}

export interface MeResponse {
  sub: string;
  rol: string;
  email: string;
  odontologo_id: string | null;
}

export const ESTADOS_TURNO = [
  "creado",
  "confirmado",
  "atendido",
  "cancelado",
  "reprogramado",
  "no_show",
  "devuelto",
] as const;

export type EstadoTurno = (typeof ESTADOS_TURNO)[number];

export function isEstadoTurno(value: string): value is EstadoTurno {
  return (ESTADOS_TURNO as readonly string[]).includes(value);
}

export function toEstadoTurno(value: string): EstadoTurno | "desconocido" {
  return isEstadoTurno(value) ? value : "desconocido";
}

export interface TurnoAgenda {
  id: string;
  paciente_id: string;
  odontologo_id: string;
  inicio: string;
  fin: string;
  estado: string;
  canal: string;
}

export interface Paciente {
  id: string;
  dni: string;
  nombre: string;
  apellido: string;
  email: string | null;
  telefono: string | null;
  consentimiento_datos: boolean;
  consentimiento_fecha: string | null;
}

export interface TurnoAcotado {
  turno_id: string;
  odontologo_id: string;
  inicio: string;
  fin: string;
  estado: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isLoginResponse(value: unknown): value is LoginResponse {
  if (!isRecord(value)) {
    return false;
  }
  return typeof value.access_token === "string" && typeof value.token_type === "string";
}

export function isLogoutResponse(value: unknown): value is LogoutResponse {
  if (!isRecord(value)) {
    return false;
  }
  return typeof value.ok === "boolean";
}

export function isMeResponse(value: unknown): value is MeResponse {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.sub === "string" &&
    typeof value.rol === "string" &&
    typeof value.email === "string" &&
    (value.odontologo_id === null || typeof value.odontologo_id === "string")
  );
}

export function isTurnoAgenda(value: unknown): value is TurnoAgenda {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.id === "string" &&
    typeof value.paciente_id === "string" &&
    typeof value.odontologo_id === "string" &&
    typeof value.inicio === "string" &&
    typeof value.fin === "string" &&
    typeof value.estado === "string" &&
    typeof value.canal === "string"
  );
}

export function isPaciente(value: unknown): value is Paciente {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.id === "string" &&
    typeof value.dni === "string" &&
    typeof value.nombre === "string" &&
    typeof value.apellido === "string" &&
    (value.email === null || typeof value.email === "string") &&
    (value.telefono === null || typeof value.telefono === "string") &&
    typeof value.consentimiento_datos === "boolean" &&
    (value.consentimiento_fecha === null || typeof value.consentimiento_fecha === "string")
  );
}

export function isTurnoAcotado(value: unknown): value is TurnoAcotado {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.turno_id === "string" &&
    typeof value.odontologo_id === "string" &&
    typeof value.inicio === "string" &&
    typeof value.fin === "string" &&
    typeof value.estado === "string"
  );
}
