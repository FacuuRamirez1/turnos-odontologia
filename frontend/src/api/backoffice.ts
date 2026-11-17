import { apiBlobFetch, apiFetch, type ApiRequestOptions } from "./client";
import { ApiError } from "./errors";
import {
  isAlertaConciliacion,
  isBloqueoStaff,
  isCancelacionTurnoPublico,
  isComprobanteDetalle,
  isCotizacionCancelacion,
  isDevolucionBandeja,
  isDisponibilidadStaff,
  isEjecucionDevolucion,
  isReprogramacionTurnoPublico,
  isReservaPublica,
  isTrazabilidadTurno,
  type AlertaConciliacion,
  type BloqueoCreateInput,
  type BloqueoStaff,
  type CancelacionTurnoPublico,
  type ComprobanteDetalle,
  type CotizacionCancelacion,
  type DevolucionBandeja,
  type DisponibilidadCreateInput,
  type DisponibilidadStaff,
  type DisponibilidadUpdateInput,
  type EjecucionDevolucion,
  type EstadoDevolucion,
  type ReprogramacionTurnoPublico,
  type ReservaPublica,
  type ReservaPublicaRequest,
  type TrazabilidadTurno,
} from "./types";

async function staffFetch<T>(
  path: string,
  guard: (value: unknown) => value is T,
  options: Omit<ApiRequestOptions, "auth"> = {},
): Promise<T> {
  const data = await apiFetch<unknown>(path, { ...options, auth: true });
  if (!guard(data)) {
    throw new ApiError(502, "El servidor devolvió una respuesta con formato inesperado.");
  }
  return data;
}

async function staffListFetch<T>(
  path: string,
  guard: (value: unknown) => value is T,
  signal?: AbortSignal,
): Promise<T[]> {
  const data = await apiFetch<unknown>(path, { auth: true, signal });
  if (!Array.isArray(data) || !data.every(guard)) {
    throw new ApiError(502, "El servidor devolvió la lista con un formato inesperado.");
  }
  return data;
}

export function listarDevoluciones(
  estado?: EstadoDevolucion,
  signal?: AbortSignal,
): Promise<DevolucionBandeja[]> {
  const query = estado !== undefined ? `?${new URLSearchParams({ estado }).toString()}` : "";
  return staffListFetch(`/api/devoluciones${query}`, isDevolucionBandeja, signal);
}

export function listarAlertasConciliacion(signal?: AbortSignal): Promise<AlertaConciliacion[]> {
  return staffListFetch("/api/devoluciones/alertas", isAlertaConciliacion, signal);
}

export function aprobarDevolucion(
  devolucionId: string,
  montoConfirmado: string,
  motivo?: string,
  signal?: AbortSignal,
): Promise<DevolucionBandeja> {
  return staffFetch(
    `/api/devoluciones/${encodeURIComponent(devolucionId)}/aprobar`,
    isDevolucionBandeja,
    {
      method: "POST",
      body:
        motivo !== undefined && motivo.trim() !== ""
          ? { monto_confirmado: montoConfirmado, motivo: motivo.trim() }
          : { monto_confirmado: montoConfirmado },
      signal,
    },
  );
}

export function rechazarDevolucion(
  devolucionId: string,
  motivo: string,
  signal?: AbortSignal,
): Promise<DevolucionBandeja> {
  return staffFetch(
    `/api/devoluciones/${encodeURIComponent(devolucionId)}/rechazar`,
    isDevolucionBandeja,
    {
      method: "POST",
      body: { motivo },
      signal,
    },
  );
}

export function ejecutarDevolucion(
  devolucionId: string,
  signal?: AbortSignal,
): Promise<EjecucionDevolucion> {
  return staffFetch(
    `/api/devoluciones/${encodeURIComponent(devolucionId)}/ejecutar`,
    isEjecucionDevolucion,
    {
      method: "POST",
      signal,
    },
  );
}

export function getComprobante(
  comprobanteId: string,
  signal?: AbortSignal,
): Promise<ComprobanteDetalle> {
  return staffFetch(
    `/api/comprobantes/${encodeURIComponent(comprobanteId)}`,
    isComprobanteDetalle,
    { signal },
  );
}

export function descargarComprobantePdf(
  comprobanteId: string,
  signal?: AbortSignal,
): Promise<Blob> {
  return apiBlobFetch(`/api/comprobantes/${encodeURIComponent(comprobanteId)}/pdf`, signal);
}

export function getTrazabilidadTurno(
  turnoId: string,
  signal?: AbortSignal,
): Promise<TrazabilidadTurno> {
  return staffFetch(`/api/turnos/${encodeURIComponent(turnoId)}/trazabilidad`, isTrazabilidadTurno, {
    signal,
  });
}

export function listarDisponibilidadStaff(
  odontologoId?: string,
  signal?: AbortSignal,
): Promise<DisponibilidadStaff[]> {
  const query =
    odontologoId !== undefined && odontologoId.trim() !== ""
      ? `?${new URLSearchParams({ odontologo_id: odontologoId }).toString()}`
      : "";
  return staffListFetch(`/api/staff/disponibilidad${query}`, isDisponibilidadStaff, signal);
}

export function crearDisponibilidadStaff(
  body: DisponibilidadCreateInput,
  signal?: AbortSignal,
): Promise<DisponibilidadStaff> {
  return staffFetch("/api/staff/disponibilidad", isDisponibilidadStaff, {
    method: "POST",
    body,
    signal,
  });
}

export function editarDisponibilidadStaff(
  filaId: string,
  body: DisponibilidadUpdateInput,
  signal?: AbortSignal,
): Promise<DisponibilidadStaff> {
  return staffFetch(`/api/staff/disponibilidad/${encodeURIComponent(filaId)}`, isDisponibilidadStaff, {
    method: "PUT",
    body,
    signal,
  });
}

export async function borrarDisponibilidadStaff(
  filaId: string,
  signal?: AbortSignal,
): Promise<void> {
  await apiFetch<unknown>(`/api/staff/disponibilidad/${encodeURIComponent(filaId)}`, {
    method: "DELETE",
    auth: true,
    signal,
  });
}

export function listarBloqueosStaff(
  odontologoId?: string,
  signal?: AbortSignal,
): Promise<BloqueoStaff[]> {
  const query =
    odontologoId !== undefined && odontologoId.trim() !== ""
      ? `?${new URLSearchParams({ odontologo_id: odontologoId }).toString()}`
      : "";
  return staffListFetch(`/api/staff/bloqueos${query}`, isBloqueoStaff, signal);
}

export function crearBloqueoStaff(
  body: BloqueoCreateInput,
  signal?: AbortSignal,
): Promise<BloqueoStaff> {
  return staffFetch("/api/staff/bloqueos", isBloqueoStaff, {
    method: "POST",
    body,
    signal,
  });
}

export async function borrarBloqueoStaff(filaId: string, signal?: AbortSignal): Promise<void> {
  await apiFetch<unknown>(`/api/staff/bloqueos/${encodeURIComponent(filaId)}`, {
    method: "DELETE",
    auth: true,
    signal,
  });
}

export function crearReservaTelefonica(
  body: ReservaPublicaRequest,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<ReservaPublica> {
  return staffFetch("/api/reservas/telefonica", isReservaPublica, {
    method: "POST",
    body,
    headers: { "Idempotency-Key": idempotencyKey },
    signal,
  });
}

export function cotizarCancelacionStaff(
  turnoId: string,
  signal?: AbortSignal,
): Promise<CotizacionCancelacion> {
  return staffFetch(
    `/api/reservas/${encodeURIComponent(turnoId)}/cotizar-cancelacion`,
    isCotizacionCancelacion,
    { signal },
  );
}

export function cancelarTurnoStaff(
  turnoId: string,
  motivo?: string,
  signal?: AbortSignal,
): Promise<CancelacionTurnoPublico> {
  return staffFetch(
    `/api/reservas/${encodeURIComponent(turnoId)}/cancelar`,
    isCancelacionTurnoPublico,
    {
      method: "POST",
      body: motivo !== undefined && motivo.trim() !== "" ? { motivo: motivo.trim() } : {},
      signal,
    },
  );
}

export function reprogramarTurnoStaff(
  turnoId: string,
  nuevoInicio: string,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<ReprogramacionTurnoPublico> {
  return staffFetch(
    `/api/reservas/${encodeURIComponent(turnoId)}/reprogramar`,
    isReprogramacionTurnoPublico,
    {
      method: "POST",
      body: { nuevo_inicio: nuevoInicio },
      headers: { "Idempotency-Key": idempotencyKey },
      signal,
    },
  );
}
