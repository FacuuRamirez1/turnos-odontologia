import { formatDate, formatTime, todayLocal } from "../../utils/format";

export const ANTICIPACION_MIN_HORAS = 24;

const HORA_MS = 60 * 60 * 1000;

export function normalizarDni(valor: string): string {
  return valor.replace(/[\s.-]/g, "").trim();
}

export function dniValido(valor: string): boolean {
  return /^[0-9]{7,8}$/.test(normalizarDni(valor));
}

export function formatearMonto(valor: string): string {
  const numero = Number(valor);
  if (!Number.isFinite(numero)) {
    return valor;
  }
  return `$ ${numero.toLocaleString("es-AR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
}

export function fechaHoraSlot(inicio: string): string {
  return `${formatDate(inicio)} · ${formatTime(inicio)}`;
}

export function esFechaPasada(fecha: string): boolean {
  return fecha !== "" && fecha < todayLocal();
}

export function fueraDeAnticipacion(inicio: string, ahora: number = Date.now()): boolean {
  const horario = new Date(inicio).getTime();
  if (Number.isNaN(horario)) {
    return false;
  }
  return horario < ahora + ANTICIPACION_MIN_HORAS * HORA_MS;
}

export function nuevaIdempotencyKey(): string {
  if (typeof globalThis.crypto.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  return `res-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}
