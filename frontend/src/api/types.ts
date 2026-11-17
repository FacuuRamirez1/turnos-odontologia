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

export const ESTADOS_DEVOLUCION = ["pendiente", "aprobada", "rechazada", "ejecutada"] as const;

export type EstadoDevolucion = (typeof ESTADOS_DEVOLUCION)[number];

export function isEstadoDevolucion(value: unknown): value is EstadoDevolucion {
  return typeof value === "string" && (ESTADOS_DEVOLUCION as readonly string[]).includes(value);
}

export interface DevolucionBandeja {
  id: string;
  pago_id: string;
  turno_id: string;
  monto: number;
  porcentaje: number;
  motivo: string | null;
  motivo_rechazo: string | null;
  estado: string;
  aprobada_at: string | null;
  rechazada_at: string | null;
  marca: string;
}

export interface AlertaConciliacion {
  id: string;
  pago_id: string;
  turno_id: string;
  tipo: string;
  detalle: string | null;
  estado_pago: string | null;
  estado_esperado: string | null;
  estado_turno: string | null;
  discrepancia: boolean;
  actor: string;
  fecha: string;
  marca: string;
}

export interface EjecucionDevolucion {
  id: string;
  estado: string;
  monto: number;
  porcentaje: number;
  mp_refund_id: string;
  pago_estado: string;
  marca: string;
}

export interface ComprobanteDetalle {
  id: string;
  pago_id: string;
  devolucion_id: string | null;
  turno_id: string;
  tipo: string;
  concepto: string;
  numero: string;
  monto: number;
  moneda: string;
  cae: string | null;
  emitida_at: string | null;
  simulado: boolean;
  marca: string;
}

export interface TurnoTrazabilidad {
  id: string;
  paciente_id: string;
  odontologo_id: string;
  inicio: string;
  fin: string;
  estado: string;
  canal: string;
  pago_id: string | null;
  reprogramado_de_id: string | null;
}

export interface PagoTrazabilidad {
  id: string;
  estado: string;
  monto: number;
  moneda: string;
  proveedor: string;
}

export interface DevolucionTrazabilidad {
  id: string;
  estado: string;
  monto: number;
  porcentaje: number;
  motivo: string | null;
  mp_refund_id: string | null;
  aprobada_at: string | null;
  rechazada_at: string | null;
  ejecutada_at: string | null;
}

export interface ComprobanteTrazabilidad {
  id: string;
  concepto: string;
  numero: string;
  monto: number;
  moneda: string;
  emitida_at: string | null;
  simulado: boolean;
}

export interface EventoPagoTrazabilidad {
  id: string;
  tipo_evento: string;
  actor: string;
  fecha: string;
  payload_json: Record<string, unknown>;
}

export interface HistorialTrazabilidad {
  id: string;
  estado_anterior: string;
  estado_nuevo: string;
  actor_tipo: string;
  actor_id: string;
  fecha: string;
  motivo: string | null;
}

export interface TrazabilidadTurno {
  turno: TurnoTrazabilidad;
  pago: PagoTrazabilidad | null;
  devolucion: DevolucionTrazabilidad | null;
  comprobantes: ComprobanteTrazabilidad[];
  eventos_pago: EventoPagoTrazabilidad[];
  historial: HistorialTrazabilidad[];
  marca: string;
}

export interface DisponibilidadStaff {
  id: string;
  odontologo_id: string;
  dia_semana: number;
  hora_inicio: string;
  hora_fin: string;
  duracion_min: number;
  tope_dia: number;
  vigente_desde: string | null;
  vigente_hasta: string | null;
}

export interface DisponibilidadCreateInput {
  odontologo_id?: string | null;
  dia_semana: number;
  hora_inicio: string;
  hora_fin: string;
  duracion_min: number;
  tope_dia: number;
  vigente_desde?: string | null;
  vigente_hasta?: string | null;
}

export interface DisponibilidadUpdateInput {
  dia_semana?: number | null;
  hora_inicio?: string | null;
  hora_fin?: string | null;
  duracion_min?: number | null;
  tope_dia?: number | null;
  vigente_desde?: string | null;
  vigente_hasta?: string | null;
}

export const MOTIVOS_BLOQUEO = ["pausa", "feriado", "bloqueo", "vacaciones"] as const;

export type MotivoBloqueo = (typeof MOTIVOS_BLOQUEO)[number];

export interface BloqueoStaff {
  id: string;
  odontologo_id: string;
  desde: string;
  hasta: string;
  motivo: string;
}

export interface BloqueoCreateInput {
  odontologo_id?: string | null;
  desde: string;
  hasta: string;
  motivo: MotivoBloqueo;
}

function isStringOrNull(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

export function isDevolucionBandeja(value: unknown): value is DevolucionBandeja {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.id === "string" &&
    typeof value.pago_id === "string" &&
    typeof value.turno_id === "string" &&
    typeof value.monto === "number" &&
    typeof value.porcentaje === "number" &&
    isStringOrNull(value.motivo) &&
    isStringOrNull(value.motivo_rechazo) &&
    typeof value.estado === "string" &&
    isStringOrNull(value.aprobada_at) &&
    isStringOrNull(value.rechazada_at) &&
    typeof value.marca === "string"
  );
}

export function isAlertaConciliacion(value: unknown): value is AlertaConciliacion {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.id === "string" &&
    typeof value.pago_id === "string" &&
    typeof value.turno_id === "string" &&
    typeof value.tipo === "string" &&
    isStringOrNull(value.detalle) &&
    isStringOrNull(value.estado_pago) &&
    isStringOrNull(value.estado_esperado) &&
    isStringOrNull(value.estado_turno) &&
    typeof value.discrepancia === "boolean" &&
    typeof value.actor === "string" &&
    typeof value.fecha === "string" &&
    typeof value.marca === "string"
  );
}

export function isEjecucionDevolucion(value: unknown): value is EjecucionDevolucion {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.id === "string" &&
    typeof value.estado === "string" &&
    typeof value.monto === "number" &&
    typeof value.porcentaje === "number" &&
    typeof value.mp_refund_id === "string" &&
    typeof value.pago_estado === "string" &&
    typeof value.marca === "string"
  );
}

export function isComprobanteDetalle(value: unknown): value is ComprobanteDetalle {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.id === "string" &&
    typeof value.pago_id === "string" &&
    isStringOrNull(value.devolucion_id) &&
    typeof value.turno_id === "string" &&
    typeof value.tipo === "string" &&
    typeof value.concepto === "string" &&
    typeof value.numero === "string" &&
    typeof value.monto === "number" &&
    typeof value.moneda === "string" &&
    isStringOrNull(value.cae) &&
    isStringOrNull(value.emitida_at) &&
    typeof value.simulado === "boolean" &&
    typeof value.marca === "string"
  );
}

function isTurnoTrazabilidad(value: unknown): value is TurnoTrazabilidad {
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
    isStringOrNull(value.pago_id) &&
    isStringOrNull(value.reprogramado_de_id)
  );
}

function isPagoTrazabilidad(value: unknown): value is PagoTrazabilidad {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.id === "string" &&
    typeof value.estado === "string" &&
    typeof value.monto === "number" &&
    typeof value.moneda === "string" &&
    typeof value.proveedor === "string"
  );
}

function isDevolucionTrazabilidad(value: unknown): value is DevolucionTrazabilidad {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.id === "string" &&
    typeof value.estado === "string" &&
    typeof value.monto === "number" &&
    typeof value.porcentaje === "number" &&
    isStringOrNull(value.motivo) &&
    isStringOrNull(value.mp_refund_id) &&
    isStringOrNull(value.aprobada_at) &&
    isStringOrNull(value.rechazada_at) &&
    isStringOrNull(value.ejecutada_at)
  );
}

function isComprobanteTrazabilidad(value: unknown): value is ComprobanteTrazabilidad {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.id === "string" &&
    typeof value.concepto === "string" &&
    typeof value.numero === "string" &&
    typeof value.monto === "number" &&
    typeof value.moneda === "string" &&
    isStringOrNull(value.emitida_at) &&
    typeof value.simulado === "boolean"
  );
}

function isEventoPagoTrazabilidad(value: unknown): value is EventoPagoTrazabilidad {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.id === "string" &&
    typeof value.tipo_evento === "string" &&
    typeof value.actor === "string" &&
    typeof value.fecha === "string" &&
    isRecord(value.payload_json)
  );
}

function isHistorialTrazabilidad(value: unknown): value is HistorialTrazabilidad {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.id === "string" &&
    typeof value.estado_anterior === "string" &&
    typeof value.estado_nuevo === "string" &&
    typeof value.actor_tipo === "string" &&
    typeof value.actor_id === "string" &&
    typeof value.fecha === "string" &&
    isStringOrNull(value.motivo)
  );
}

export function isTrazabilidadTurno(value: unknown): value is TrazabilidadTurno {
  if (!isRecord(value)) {
    return false;
  }
  return (
    isTurnoTrazabilidad(value.turno) &&
    (value.pago === null || isPagoTrazabilidad(value.pago)) &&
    (value.devolucion === null || isDevolucionTrazabilidad(value.devolucion)) &&
    Array.isArray(value.comprobantes) &&
    value.comprobantes.every(isComprobanteTrazabilidad) &&
    Array.isArray(value.eventos_pago) &&
    value.eventos_pago.every(isEventoPagoTrazabilidad) &&
    Array.isArray(value.historial) &&
    value.historial.every(isHistorialTrazabilidad) &&
    typeof value.marca === "string"
  );
}

export function isDisponibilidadStaff(value: unknown): value is DisponibilidadStaff {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.id === "string" &&
    typeof value.odontologo_id === "string" &&
    typeof value.dia_semana === "number" &&
    typeof value.hora_inicio === "string" &&
    typeof value.hora_fin === "string" &&
    typeof value.duracion_min === "number" &&
    typeof value.tope_dia === "number" &&
    isStringOrNull(value.vigente_desde) &&
    isStringOrNull(value.vigente_hasta)
  );
}

export function isBloqueoStaff(value: unknown): value is BloqueoStaff {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.id === "string" &&
    typeof value.odontologo_id === "string" &&
    typeof value.desde === "string" &&
    typeof value.hasta === "string" &&
    typeof value.motivo === "string"
  );
}
