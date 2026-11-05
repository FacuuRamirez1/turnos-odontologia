import { useEffect, useRef, useState } from "react";
import { ApiError, isAbortError, toErrorMessage } from "../api/errors";
import { getPaciente, getPacienteTurnos } from "../api/pacientes";
import type { Paciente, TurnoAcotado } from "../api/types";
import { formatDate, formatTurnoRange } from "../utils/format";
import { StatusBadge } from "./StatusBadge";

const HISTORIAL_LIMITE = 20;

interface FichaPacientePanelProps {
  pacienteId: string;
  refreshKey: number;
  onClose: () => void;
}

function panelErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401 || error.status === 403) {
      return "No tenés permisos para ver esta ficha.";
    }
    if (error.status === 404) {
      return "No se encontró la ficha del paciente.";
    }
  }
  return toErrorMessage(error);
}

export function FichaPacientePanel({
  pacienteId,
  refreshKey,
  onClose,
}: FichaPacientePanelProps): JSX.Element {
  const [paciente, setPaciente] = useState<Paciente | null>(null);
  const [historial, setHistorial] = useState<TurnoAcotado[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const panelRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    panelRef.current?.focus();
  }, [pacienteId]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setPaciente(null);
    setHistorial([]);

    Promise.all([
      getPaciente(pacienteId, controller.signal),
      getPacienteTurnos(pacienteId, controller.signal),
    ])
      .then(([pacienteData, historialData]) => {
        if (controller.signal.aborted) {
          return;
        }
        setPaciente(pacienteData);
        setHistorial(historialData);
      })
      .catch((cause: unknown) => {
        if (isAbortError(cause)) {
          return;
        }
        setPaciente(null);
        setHistorial([]);
        setError(panelErrorMessage(cause));
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [pacienteId, refreshKey]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        onClose();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const historialVisible = historial.slice(-HISTORIAL_LIMITE);
  const title =
    paciente !== null
      ? `${paciente.apellido}, ${paciente.nombre}`
      : error !== null
        ? "Ficha no disponible"
        : "Cargando ficha…";

  return (
    <aside
      ref={panelRef}
      tabIndex={-1}
      className="ficha-panel"
      aria-labelledby="ficha-title"
    >
      <header className="ficha-panel__header">
        <div>
          <p className="ficha-panel__kicker">Ficha del paciente</p>
          <h2 id="ficha-title">{title}</h2>
        </div>
        <button type="button" className="button button--quiet" onClick={onClose}>
          Cerrar
        </button>
      </header>

      {loading && (
        <p className="state" role="status">
          Cargando ficha e historial…
        </p>
      )}

      {error !== null && (
        <p className="feedback feedback--error" role="alert" aria-live="polite">
          {error}
        </p>
      )}

      {!loading && error === null && paciente !== null && (
        <>
          <section className="ficha-block" aria-labelledby="ficha-contacto">
            <h3 id="ficha-contacto">Contacto</h3>
            <dl className="ficha-data">
              <div>
                <dt>DNI</dt>
                <dd className="mono">{paciente.dni}</dd>
              </div>
              <div>
                <dt>Email</dt>
                <dd>{paciente.email ?? "Sin dato"}</dd>
              </div>
              <div>
                <dt>Teléfono</dt>
                <dd>{paciente.telefono ?? "Sin dato"}</dd>
              </div>
            </dl>
          </section>

          <section className="ficha-block" aria-labelledby="ficha-consentimiento">
            <h3 id="ficha-consentimiento">Consentimiento de datos</h3>
            <p
              className={
                paciente.consentimiento_datos ? "consent consent--ok" : "consent consent--pending"
              }
            >
              {paciente.consentimiento_datos
                ? `Sí · ${paciente.consentimiento_fecha === null ? "fecha no registrada" : formatDate(paciente.consentimiento_fecha)}`
                : "No registrado"}
            </p>
          </section>

          <section className="ficha-block" aria-labelledby="ficha-historial">
            <div className="ficha-block__head">
              <h3 id="ficha-historial">Historial de turnos</h3>
              <span className="ficha-block__meta">{historial.length} registros</span>
            </div>
            {historialVisible.length === 0 ? (
              <p className="state state--inline">Sin turnos registrados.</p>
            ) : (
              <ul className="history-list">
                {historialVisible.map((turno) => (
                  <li key={turno.turno_id} className="history-row">
                    <span className="history-row__time">{formatDate(turno.inicio)}</span>
                    <span className="history-row__range mono">
                      {formatTurnoRange(turno.inicio, turno.fin)}
                    </span>
                    <StatusBadge estado={turno.estado} />
                  </li>
                ))}
              </ul>
            )}
            {historial.length > HISTORIAL_LIMITE && (
              <p className="field__hint">
                Se muestran los {HISTORIAL_LIMITE} turnos más recientes de {historial.length}.
              </p>
            )}
          </section>
        </>
      )}
    </aside>
  );
}
