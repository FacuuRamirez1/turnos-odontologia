import { apiFetch } from "./client";
import { isAbortError, mapPublicError, MENSAJE_POR_KIND, PublicApiError } from "./errors";
import {
  isCancelacionTurnoPublico,
  isCotizacionCancelacion,
  isDisponibilidadPublica,
  isMailAccionResult,
  isMisTurnoPublico,
  isPreciosPublicos,
  isReprogramacionTurnoPublico,
  isReservaPublica,
  isSimulacionPago,
  type AccionPagoSimulado,
  type CancelacionTurnoPublico,
  type CotizacionCancelacion,
  type DisponibilidadPublica,
  type MailAccionResult,
  type MisTurnoPublico,
  type PreciosPublicos,
  type ReprogramacionTurnoPublico,
  type ReservaPublica,
  type ReservaPublicaRequest,
  type SimulacionPago,
} from "./types";

interface PublicRequest {
  method?: "GET" | "POST";
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

async function publicFetch<T>(
  path: string,
  guard: (value: unknown) => value is T,
  options: PublicRequest = {},
): Promise<T> {
  try {
    const data = await apiFetch<unknown>(path, { ...options, auth: false });
    if (!guard(data)) {
      throw new PublicApiError("formato", MENSAJE_POR_KIND.formato);
    }
    return data;
  } catch (cause: unknown) {
    if (isAbortError(cause)) {
      throw cause;
    }
    throw mapPublicError(cause);
  }
}

export function getPrecios(signal?: AbortSignal): Promise<PreciosPublicos> {
  return publicFetch("/api/precios", isPreciosPublicos, { signal });
}

export function getDisponibilidad(
  odontologoId: string,
  fecha: string,
  signal?: AbortSignal,
): Promise<DisponibilidadPublica> {
  const params = new URLSearchParams({ odontologo_id: odontologoId, fecha });
  return publicFetch(`/api/disponibilidad?${params.toString()}`, isDisponibilidadPublica, {
    signal,
  });
}

export function crearReserva(
  cuerpo: ReservaPublicaRequest,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<ReservaPublica> {
  return publicFetch("/api/reservas", isReservaPublica, {
    method: "POST",
    body: cuerpo,
    headers: { "Idempotency-Key": idempotencyKey },
    signal,
  });
}

export function simularPago(
  pagoId: string,
  accion: AccionPagoSimulado,
  checkoutToken: string,
  signal?: AbortSignal,
): Promise<SimulacionPago> {
  return publicFetch(`/api/pagos/${encodeURIComponent(pagoId)}/simular`, isSimulacionPago, {
    method: "POST",
    body: { accion },
    headers: { checkout_token: checkoutToken },
    signal,
  });
}

export function cotizarCancelacionPublica(
  turnoId: string,
  dni: string,
  token: string,
  signal?: AbortSignal,
): Promise<CotizacionCancelacion> {
  const params = new URLSearchParams({ dni, token });
  return publicFetch(
    `/api/reservas/${encodeURIComponent(turnoId)}/cotizar-cancelacion?${params.toString()}`,
    isCotizacionCancelacion,
    { signal },
  );
}

export function cancelarTurnoPublico(
  turnoId: string,
  dni: string,
  token: string,
  motivo?: string,
  signal?: AbortSignal,
): Promise<CancelacionTurnoPublico> {
  const params = new URLSearchParams({ dni, token });
  return publicFetch(
    `/api/reservas/${encodeURIComponent(turnoId)}/cancelar?${params.toString()}`,
    isCancelacionTurnoPublico,
    {
      method: "POST",
      body: motivo !== undefined ? { motivo } : {},
      signal,
    },
  );
}

export function reprogramarTurnoPublico(
  turnoId: string,
  dni: string,
  token: string,
  nuevoInicio: string,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<ReprogramacionTurnoPublico> {
  const params = new URLSearchParams({ dni, token });
  return publicFetch(
    `/api/reservas/${encodeURIComponent(turnoId)}/reprogramar?${params.toString()}`,
    isReprogramacionTurnoPublico,
    {
      method: "POST",
      body: { nuevo_inicio: nuevoInicio },
      headers: { "Idempotency-Key": idempotencyKey },
      signal,
    },
  );
}

function isMisTurnosPublicos(value: unknown): value is MisTurnoPublico[] {
  return Array.isArray(value) && value.every(isMisTurnoPublico);
}

export function getMisTurnos(
  dni: string,
  token: string,
  signal?: AbortSignal,
): Promise<MisTurnoPublico[]> {
  const params = new URLSearchParams({ dni, token });
  return publicFetch(`/api/mis-turnos?${params.toString()}`, isMisTurnosPublicos, { signal });
}

export function confirmarDesdeMail(
  token: string,
  signal?: AbortSignal,
): Promise<MailAccionResult> {
  const params = new URLSearchParams({ token });
  return publicFetch(`/api/mail/confirmar?${params.toString()}`, isMailAccionResult, { signal });
}

export function cancelarDesdeMail(
  token: string,
  signal?: AbortSignal,
): Promise<MailAccionResult> {
  const params = new URLSearchParams({ token });
  return publicFetch(`/api/mail/cancelar?${params.toString()}`, isMailAccionResult, { signal });
}
