import { type FormEvent, useEffect, useState } from "react";
import {
  borrarBloqueoStaff,
  borrarDisponibilidadStaff,
  crearBloqueoStaff,
  crearDisponibilidadStaff,
  listarBloqueosStaff,
  listarDisponibilidadStaff,
} from "../api/backoffice";
import { isAbortError, toErrorMessage } from "../api/errors";
import {
  MOTIVOS_BLOQUEO,
  type BloqueoStaff,
  type DisponibilidadStaff,
  type MotivoBloqueo,
} from "../api/types";
import { formatDate, formatTime } from "../utils/format";

const DIAS_SEMANA: readonly string[] = [
  "Lunes",
  "Martes",
  "Miércoles",
  "Jueves",
  "Viernes",
  "Sábado",
  "Domingo",
];

interface DisponibilidadBloqueosPanelProps {
  odontologoId: string;
  isOdontologo: boolean;
}

export function DisponibilidadBloqueosPanel({
  odontologoId,
  isOdontologo,
}: DisponibilidadBloqueosPanelProps): JSX.Element {
  const [franjas, setFranjas] = useState<DisponibilidadStaff[]>([]);
  const [bloqueos, setBloqueos] = useState<BloqueoStaff[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const [diaSemana, setDiaSemana] = useState("0");
  const [horaInicio, setHoraInicio] = useState("09:00");
  const [horaFin, setHoraFin] = useState("13:00");
  const [duracionMin, setDuracionMin] = useState("30");
  const [topeDia, setTopeDia] = useState("8");

  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [motivo, setMotivo] = useState<MotivoBloqueo>("pausa");

  useEffect(() => {
    if (odontologoId.trim() === "") {
      setFranjas([]);
      setBloqueos([]);
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(null);
    const paramOd = isOdontologo ? undefined : odontologoId;

    Promise.all([
      listarDisponibilidadStaff(paramOd, controller.signal),
      listarBloqueosStaff(paramOd, controller.signal),
    ])
      .then(([franjasData, bloqueosData]) => {
        if (!controller.signal.aborted) {
          setFranjas(franjasData);
          setBloqueos(bloqueosData);
        }
      })
      .catch((cause: unknown) => {
        if (!isAbortError(cause) && !controller.signal.aborted) {
          setError(toErrorMessage(cause));
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [odontologoId, isOdontologo, reloadKey]);

  async function handleCrearFranja(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError(null);

    if (horaInicio === "" || horaFin === "" || horaFin <= horaInicio) {
      setError("La hora de fin debe ser posterior a la hora de inicio.");
      return;
    }
    const duracion = Number(duracionMin);
    const tope = Number(topeDia);
    if (!Number.isInteger(duracion) || duracion <= 0 || !Number.isInteger(tope) || tope <= 0) {
      setError("Duración y tope diario deben ser enteros positivos.");
      return;
    }

    setSubmitting(true);
    try {
      await crearDisponibilidadStaff({
        odontologo_id: isOdontologo ? undefined : odontologoId,
        dia_semana: Number(diaSemana),
        hora_inicio: horaInicio,
        hora_fin: horaFin,
        duracion_min: duracion,
        tope_dia: tope,
      });
      setReloadKey((k) => k + 1);
    } catch (cause: unknown) {
      setError(toErrorMessage(cause));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleEliminarFranja(filaId: string): Promise<void> {
    setSubmitting(true);
    setError(null);
    try {
      await borrarDisponibilidadStaff(filaId);
      setReloadKey((k) => k + 1);
    } catch (cause: unknown) {
      setError(toErrorMessage(cause));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCrearBloqueo(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError(null);

    if (desde === "" || hasta === "") {
      setError("Completá fecha y hora de inicio y fin del bloqueo.");
      return;
    }
    const dDesde = new Date(desde);
    const dHasta = new Date(hasta);
    if (Number.isNaN(dDesde.getTime()) || Number.isNaN(dHasta.getTime()) || dHasta <= dDesde) {
      setError("El fin del bloqueo debe ser posterior al inicio.");
      return;
    }

    setSubmitting(true);
    try {
      await crearBloqueoStaff({
        odontologo_id: isOdontologo ? undefined : odontologoId,
        desde: dDesde.toISOString(),
        hasta: dHasta.toISOString(),
        motivo,
      });
      setDesde("");
      setHasta("");
      setReloadKey((k) => k + 1);
    } catch (cause: unknown) {
      setError(toErrorMessage(cause));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleEliminarBloqueo(filaId: string): Promise<void> {
    setSubmitting(true);
    setError(null);
    try {
      await borrarBloqueoStaff(filaId);
      setReloadKey((k) => k + 1);
    } catch (cause: unknown) {
      setError(toErrorMessage(cause));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="wizard-step" aria-labelledby="dispo-bloqueos-title">
      <h2 id="dispo-bloqueos-title">Disponibilidad semanal y bloqueos</h2>

      {error !== null && (
        <p className="feedback feedback--error" role="alert" aria-live="polite">
          {error}
        </p>
      )}

      {loading ? (
        <p className="state">Cargando disponibilidad y bloqueos…</p>
      ) : (
        <>
          <form onSubmit={(event) => void handleCrearFranja(event)} noValidate>
            <h3>Nueva franja horaria</h3>
            <div className="form-grid">
              <div className="field">
                <label htmlFor="disp-dia">Día</label>
                <select
                  id="disp-dia"
                  value={diaSemana}
                  onChange={(event) => setDiaSemana(event.target.value)}
                >
                  {DIAS_SEMANA.map((nombre, indice) => (
                    <option key={nombre} value={String(indice)}>
                      {nombre}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="disp-inicio">Hora inicio</label>
                <input
                  id="disp-inicio"
                  type="time"
                  value={horaInicio}
                  onChange={(event) => setHoraInicio(event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="disp-fin">Hora fin</label>
                <input
                  id="disp-fin"
                  type="time"
                  value={horaFin}
                  onChange={(event) => setHoraFin(event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="disp-duracion">Duración (min)</label>
                <input
                  id="disp-duracion"
                  type="number"
                  min={5}
                  value={duracionMin}
                  onChange={(event) => setDuracionMin(event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="disp-tope">Tope diario</label>
                <input
                  id="disp-tope"
                  type="number"
                  min={1}
                  value={topeDia}
                  onChange={(event) => setTopeDia(event.target.value)}
                />
              </div>
            </div>
            <div className="wizard-actions">
              <button type="submit" className="button button--primary" disabled={submitting}>
                Agregar franja
              </button>
            </div>
          </form>

          {franjas.length === 0 ? (
            <p className="state state--inline">Sin franjas semanales configuradas.</p>
          ) : (
            <ul className="history-list">
              {franjas.map((franja) => (
                <li key={franja.id} className="history-row">
                  <span>
                    <strong>{DIAS_SEMANA[franja.dia_semana] ?? `Día ${franja.dia_semana}`}</strong> ·{" "}
                    {franja.hora_inicio.slice(0, 5)}–{franja.hora_fin.slice(0, 5)} (
                    {franja.duracion_min} min, tope {franja.tope_dia})
                  </span>
                  <button
                    type="button"
                    className="button button--quiet"
                    disabled={submitting}
                    onClick={() => {
                      void handleEliminarFranja(franja.id);
                    }}
                  >
                    Eliminar franja
                  </button>
                </li>
              ))}
            </ul>
          )}

          <form onSubmit={(event) => void handleCrearBloqueo(event)} noValidate>
            <h3>Nuevo bloqueo o pausa</h3>
            <div className="form-grid">
              <div className="field">
                <label htmlFor="bloq-desde">Desde</label>
                <input
                  id="bloq-desde"
                  type="datetime-local"
                  value={desde}
                  onChange={(event) => setDesde(event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="bloq-hasta">Hasta</label>
                <input
                  id="bloq-hasta"
                  type="datetime-local"
                  value={hasta}
                  onChange={(event) => setHasta(event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="bloq-motivo">Motivo</label>
                <select
                  id="bloq-motivo"
                  value={motivo}
                  onChange={(event) => setMotivo(event.target.value as MotivoBloqueo)}
                >
                  {MOTIVOS_BLOQUEO.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="wizard-actions">
              <button type="submit" className="button button--primary" disabled={submitting}>
                Agregar bloqueo
              </button>
            </div>
          </form>

          {bloqueos.length === 0 ? (
            <p className="state state--inline">Sin bloqueos activos.</p>
          ) : (
            <ul className="history-list">
              {bloqueos.map((bloq) => (
                <li key={bloq.id} className="history-row">
                  <span>
                    <strong>{bloq.motivo}</strong> · {formatDate(bloq.desde)} {formatTime(bloq.desde)}{" "}
                    → {formatDate(bloq.hasta)} {formatTime(bloq.hasta)}
                  </span>
                  <button
                    type="button"
                    className="button button--quiet"
                    disabled={submitting}
                    onClick={() => {
                      void handleEliminarBloqueo(bloq.id);
                    }}
                  >
                    Eliminar bloqueo
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
