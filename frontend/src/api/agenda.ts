import { apiFetch } from "./client";
import { ApiError } from "./errors";
import { isTurnoAgenda, type TurnoAgenda } from "./types";

function agendaPath(fecha: string, odontologoId: string): string {
  const params = new URLSearchParams({ fecha, odontologo_id: odontologoId });
  return `/api/agenda?${params.toString()}`;
}

async function mutateTurno(path: string, signal?: AbortSignal): Promise<TurnoAgenda> {
  const data = await apiFetch<unknown>(path, { method: "POST", signal });
  if (!isTurnoAgenda(data)) {
    throw new ApiError(502, "El servidor devolvió el turno con un formato inesperado.");
  }
  return data;
}

export async function getAgenda(
  fecha: string,
  odontologoId: string,
  signal?: AbortSignal,
): Promise<TurnoAgenda[]> {
  const data = await apiFetch<unknown>(agendaPath(fecha, odontologoId), { signal });
  if (!Array.isArray(data)) {
    throw new ApiError(502, "El servidor devolvió la agenda con un formato inesperado.");
  }
  return data.filter(isTurnoAgenda);
}

export function markAtendido(turnoId: string, signal?: AbortSignal): Promise<TurnoAgenda> {
  return mutateTurno(`/api/agenda/${encodeURIComponent(turnoId)}/atendido`, signal);
}

export function markNoShow(turnoId: string, signal?: AbortSignal): Promise<TurnoAgenda> {
  return mutateTurno(`/api/agenda/${encodeURIComponent(turnoId)}/no-show`, signal);
}
