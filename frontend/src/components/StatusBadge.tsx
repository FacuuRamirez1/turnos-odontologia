import { toEstadoTurno, type EstadoTurno } from "../api/types";

const ESTADO_LABELS: Record<EstadoTurno | "desconocido", string> = {
  creado: "Creado",
  confirmado: "Confirmado",
  atendido: "Atendido",
  cancelado: "Cancelado",
  reprogramado: "Reprogramado",
  no_show: "No show",
  devuelto: "Devuelto",
  desconocido: "Desconocido",
};

export function StatusBadge({ estado }: { estado: string }): JSX.Element {
  const normalized = toEstadoTurno(estado);
  return (
    <span className={`status-badge status-badge--${normalized}`}>{ESTADO_LABELS[normalized]}</span>
  );
}
