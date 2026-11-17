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

export interface PrecioOdontologoPublico {
  odontologo_id: string;
  monto_turno: string;
  monto_senia: string;
}

export interface TrialPublico {
  disponible: boolean;
  requiere_tarjeta: boolean;
  dias: number | null;
}

export interface PreciosPublicos {
  odontologos: PrecioOdontologoPublico[];
  trial: TrialPublico;
  marca: string;
}

export interface SlotDisponible {
  inicio: string;
  fin: string;
}

export interface DisponibilidadPublica {
  slots: SlotDisponible[];
}

export interface ReservaPublicaRequest {
  odontologo_id: string;
  inicio: string;
  dni: string;
  nombre: string;
  apellido: string;
  email: string | null;
  telefono: string | null;
  consentimiento_datos: boolean;
}

export interface ReservaPublica {
  id: string;
  paciente_id: string;
  odontologo_id: string;
  inicio: string;
  fin: string;
  estado: string;
  canal: string;
  pago_id: string | null;
  checkout_url: string | null;
  checkout_token: string | null;
}

export const ACCIONES_PAGO_SIMULADO = ["aprobar", "rechazar", "expirar"] as const;

export type AccionPagoSimulado = (typeof ACCIONES_PAGO_SIMULADO)[number];

export interface SimulacionPago {
  pago_id: string;
  estado_pago: string;
  turno_id: string | null;
  estado_turno: string | null;
  transicionado: boolean;
  idempotente: boolean;
  proveedor: string;
  marca: string;
}

export interface CotizacionCancelacion {
  porcentaje: number;
}

export interface CancelacionTurnoPublico {
  id: string;
  estado: string;
  devolucion: DevolucionMail | null;
}

export interface ReprogramacionTurnoOrigen {
  id: string;
  estado: string;
}

export interface ReprogramacionTurnoNuevo {
  id: string;
  estado: string;
  pago_id: string | null;
  reprogramado_de_id: string;
}

export interface ReprogramacionTurnoPublico {
  origen: ReprogramacionTurnoOrigen;
  nuevo: ReprogramacionTurnoNuevo;
}

export interface MisTurnoPublico {
  id: string;
  odontologo_id: string;
  inicio: string;
  fin: string;
  estado: string;
}

export interface DevolucionMail {
  id: string;
  porcentaje: number;
  monto: number;
  estado: string;
}

export interface MailAccionResult {
  ok: boolean;
  accion: string;
  estado?: string;
  turno_id?: string;
  inicio?: string;
  mensaje?: string;
  porcentaje?: number;
  devolucion?: DevolucionMail | null;
  marca?: string;
  code?: string;
  detail?: string;
}

export function isPrecioOdontologoPublico(value: unknown): value is PrecioOdontologoPublico {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.odontologo_id === "string" &&
    typeof value.monto_turno === "string" &&
    typeof value.monto_senia === "string"
  );
}

export function isTrialPublico(value: unknown): value is TrialPublico {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.disponible === "boolean" &&
    typeof value.requiere_tarjeta === "boolean" &&
    (value.dias === null || typeof value.dias === "number")
  );
}

export function isPreciosPublicos(value: unknown): value is PreciosPublicos {
  if (!isRecord(value) || !Array.isArray(value.odontologos)) {
    return false;
  }
  return (
    value.odontologos.every(isPrecioOdontologoPublico) &&
    isTrialPublico(value.trial) &&
    typeof value.marca === "string"
  );
}

export function isSlotDisponible(value: unknown): value is SlotDisponible {
  if (!isRecord(value)) {
    return false;
  }
  return typeof value.inicio === "string" && typeof value.fin === "string";
}

export function isDisponibilidadPublica(value: unknown): value is DisponibilidadPublica {
  if (!isRecord(value) || !Array.isArray(value.slots)) {
    return false;
  }
  return value.slots.every(isSlotDisponible);
}

export function isReservaPublica(value: unknown): value is ReservaPublica {
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
    typeof value.canal === "string" &&
    (value.pago_id === null || typeof value.pago_id === "string") &&
    (value.checkout_url === null || typeof value.checkout_url === "string") &&
    (value.checkout_token === null || typeof value.checkout_token === "string")
  );
}

export function isSimulacionPago(value: unknown): value is SimulacionPago {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.pago_id === "string" &&
    typeof value.estado_pago === "string" &&
    (value.turno_id === null || typeof value.turno_id === "string") &&
    (value.estado_turno === null || typeof value.estado_turno === "string") &&
    typeof value.transicionado === "boolean" &&
    typeof value.idempotente === "boolean" &&
    typeof value.proveedor === "string" &&
    typeof value.marca === "string"
  );
}

export function isCotizacionCancelacion(value: unknown): value is CotizacionCancelacion {
  if (!isRecord(value)) {
    return false;
  }
  return typeof value.porcentaje === "number";
}

export function isCancelacionTurnoPublico(value: unknown): value is CancelacionTurnoPublico {
  if (!isRecord(value)) {
    return false;
  }
  if (typeof value.id !== "string" || typeof value.estado !== "string") {
    return false;
  }
  if (value.devolucion !== null && value.devolucion !== undefined) {
    return isDevolucionMail(value.devolucion);
  }
  return value.devolucion === null;
}

export function isReprogramacionTurnoPublico(value: unknown): value is ReprogramacionTurnoPublico {
  if (!isRecord(value) || !isRecord(value.origen) || !isRecord(value.nuevo)) {
    return false;
  }
  const { origen, nuevo } = value;
  return (
    typeof origen.id === "string" &&
    typeof origen.estado === "string" &&
    typeof nuevo.id === "string" &&
    typeof nuevo.estado === "string" &&
    (nuevo.pago_id === null || typeof nuevo.pago_id === "string") &&
    typeof nuevo.reprogramado_de_id === "string"
  );
}

export function isMisTurnoPublico(value: unknown): value is MisTurnoPublico {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.id === "string" &&
    typeof value.odontologo_id === "string" &&
    typeof value.inicio === "string" &&
    typeof value.fin === "string" &&
    typeof value.estado === "string"
  );
}

export function isDevolucionMail(value: unknown): value is DevolucionMail {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.id === "string" &&
    typeof value.porcentaje === "number" &&
    typeof value.monto === "number" &&
    typeof value.estado === "string"
  );
}

export function isMailAccionResult(value: unknown): value is MailAccionResult {
  if (!isRecord(value)) {
    return false;
  }
  if (typeof value.ok !== "boolean" || typeof value.accion !== "string") {
    return false;
  }
  if (value.devolucion !== undefined && value.devolucion !== null) {
    return isDevolucionMail(value.devolucion);
  }
  return true;
}
