export { apiFetch, AUTH_UNAUTHORIZED_EVENT } from "./client";
export type { ApiRequestOptions } from "./client";
export {
  ApiError,
  isAbortError,
  mapPublicError,
  PublicApiError,
  toErrorMessage,
  toPublicErrorMessage,
} from "./errors";
export type { PublicErrorKind } from "./errors";
export { getMe, loginRequest, logoutRequest, refreshSession } from "./auth";
export { getAgenda, markAtendido, markNoShow } from "./agenda";
export { getPaciente, getPacienteTurnos } from "./pacientes";
export {
  cancelarDesdeMail,
  cancelarTurnoPublico,
  confirmarDesdeMail,
  cotizarCancelacionPublica,
  crearReserva,
  getDisponibilidad,
  getMisTurnos,
  getPrecios,
  reprogramarTurnoPublico,
  simularPago,
} from "./public";
export { ACCIONES_PAGO_SIMULADO, ESTADOS_TURNO, isEstadoTurno, toEstadoTurno } from "./types";
export type {
  AccionPagoSimulado,
  CancelacionTurnoPublico,
  CotizacionCancelacion,
  DevolucionMail,
  DisponibilidadPublica,
  EstadoTurno,
  LoginRequest,
  LoginResponse,
  LogoutResponse,
  MailAccionResult,
  MeResponse,
  MisTurnoPublico,
  Paciente,
  PrecioOdontologoPublico,
  PreciosPublicos,
  ReprogramacionTurnoNuevo,
  ReprogramacionTurnoOrigen,
  ReprogramacionTurnoPublico,
  ReservaPublica,
  ReservaPublicaRequest,
  SimulacionPago,
  SlotDisponible,
  TrialPublico,
  TurnoAcotado,
  TurnoAgenda,
  UserRole,
} from "./types";
