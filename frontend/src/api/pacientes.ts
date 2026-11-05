import { apiFetch } from "./client";
import { ApiError } from "./errors";
import { isPaciente, isTurnoAcotado, type Paciente, type TurnoAcotado } from "./types";

export async function getPaciente(pacienteId: string, signal?: AbortSignal): Promise<Paciente> {
  const data = await apiFetch<unknown>(`/api/pacientes/${encodeURIComponent(pacienteId)}`, {
    signal,
  });
  if (!isPaciente(data)) {
    throw new ApiError(502, "El servidor devolvió la ficha con un formato inesperado.");
  }
  return data;
}

export async function getPacienteTurnos(
  pacienteId: string,
  signal?: AbortSignal,
): Promise<TurnoAcotado[]> {
  const data = await apiFetch<unknown>(
    `/api/pacientes/${encodeURIComponent(pacienteId)}/turnos`,
    { signal },
  );
  if (!Array.isArray(data)) {
    throw new ApiError(502, "El servidor devolvió el historial con un formato inesperado.");
  }
  return data.filter(isTurnoAcotado);
}
