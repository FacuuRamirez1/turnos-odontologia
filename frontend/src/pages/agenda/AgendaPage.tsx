import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getAgenda, markAtendido, markNoShow } from "../../api/agenda";
import {
  cancelarTurnoStaff,
  cotizarCancelacionStaff,
  reprogramarTurnoStaff,
} from "../../api/backoffice";
import { isAbortError, toErrorMessage } from "../../api/errors";
import { getDisponibilidad } from "../../api/public";
import type { SlotDisponible, TurnoAgenda } from "../../api/types";
import { useAuth } from "../../auth/AuthProvider";
import { DisponibilidadBloqueosPanel } from "../../components/DisponibilidadBloqueosPanel";
import { FichaPacientePanel } from "../../components/FichaPacientePanel";
import { ReservaTelefonicaPanel } from "../../components/ReservaTelefonicaPanel";
import { StatusBadge } from "../../components/StatusBadge";
import { TrazabilidadPanel } from "../../components/TrazabilidadPanel";
import {
  formatDate,
  formatTime,
  isFinPast,
  isIsoDate,
  isUuid,
  todayLocal,
} from "../../utils/format";
import {
  esFechaPasada,
  fueraDeAnticipacion,
  nuevaIdempotencyKey,
} from "../reserva/reservaUtils";

type AccionTurno = "atendido" | "no_show";

interface CancelacionStaffState {
  turnoId: string;
  porcentaje: number;
  motivo: string;
}

interface ReprogramacionStaffState {
  turnoId: string;
  odontologoId: string;
  fecha: string;
  slots: SlotDisponible[];
  loadingSlots: boolean;
  slotError: string | null;
  nuevoInicio: string;
}

type SidePanelState =
  | { kind: "ficha"; turno: TurnoAgenda }
  | { kind: "traza"; turnoId: string }
  | null;

export function AgendaPage(): JSX.Element {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const rawFecha = searchParams.get("fecha");
  const fecha = rawFecha !== null && isIsoDate(rawFecha) ? rawFecha : todayLocal();
  const urlProfessionalId = searchParams.get("odontologo_id") ?? "";

  const [professionalInput, setProfessionalInput] = useState(urlProfessionalId);
  const lastProfessionalParamRef = useRef(urlProfessionalId);
  const [turnos, setTurnos] = useState<TurnoAgenda[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingTurnoId, setPendingTurnoId] = useState<string | null>(null);
  const [sidePanel, setSidePanel] = useState<SidePanelState>(null);
  const [cancelacion, setCancelacion] = useState<CancelacionStaffState | null>(null);
  const [reprogramacion, setReprogramacion] = useState<ReprogramacionStaffState | null>(null);
  const [showDisponibilidad, setShowDisponibilidad] = useState(false);
  const [showTelefonica, setShowTelefonica] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [fichaRefreshKey, setFichaRefreshKey] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  const actionControllerRef = useRef<AbortController | null>(null);

  const role = user?.rol ?? "";
  const isOdontologo = role === "odontologo";
  const canManageAgenda =
    role === "odontologo" || role === "recepcionista" || role === "admin";
  const canCreateTelefonica = role === "recepcionista" || role === "admin";
  const professionalInputTrimmed = professionalInput.trim();
  const invalidProfessional =
    !isOdontologo && professionalInputTrimmed !== "" && !isUuid(professionalInputTrimmed);
  const awaitingProfessional = !isOdontologo && professionalInputTrimmed === "";
  const effectiveOdontologoId = isOdontologo
    ? (user?.odontologo_id ?? "")
    : isUuid(professionalInputTrimmed)
      ? professionalInputTrimmed
      : "";
  const missingProfessional = isOdontologo && effectiveOdontologoId === "";

  useEffect(() => {
    if (rawFecha === fecha) {
      return;
    }
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        next.set("fecha", fecha);
        return next;
      },
      { replace: true },
    );
  }, [rawFecha, fecha, setSearchParams]);

  useEffect(() => {
    if (urlProfessionalId !== lastProfessionalParamRef.current) {
      lastProfessionalParamRef.current = urlProfessionalId;
      setProfessionalInput(urlProfessionalId);
    }
  }, [urlProfessionalId]);

  useEffect(() => {
    setTurnos([]);
    setSidePanel(null);
    setCancelacion(null);
    setReprogramacion(null);
    setActionError(null);
  }, [fecha, effectiveOdontologoId]);

  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!canManageAgenda || effectiveOdontologoId === "") {
      setLoading(false);
      setError(null);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(null);

    getAgenda(fecha, effectiveOdontologoId, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          setTurnos(data);
        }
      })
      .catch((cause: unknown) => {
        if (isAbortError(cause)) {
          return;
        }
        setTurnos([]);
        setError(toErrorMessage(cause));
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [canManageAgenda, effectiveOdontologoId, fecha, reloadKey]);

  useEffect(() => {
    setSidePanel((current) => {
      if (current === null || current.kind !== "ficha") {
        return current;
      }
      const updated = turnos.find((turno) => turno.id === current.turno.id);
      return updated !== undefined ? { kind: "ficha", turno: updated } : null;
    });
  }, [turnos]);

  useEffect(() => {
    return () => {
      actionControllerRef.current?.abort();
    };
  }, []);

  const runAction = useCallback(
    async (turno: TurnoAgenda, action: AccionTurno): Promise<void> => {
      actionControllerRef.current?.abort();
      const controller = new AbortController();
      actionControllerRef.current = controller;
      setActionError(null);
      setPendingTurnoId(turno.id);

      try {
        const updated =
          action === "atendido"
            ? await markAtendido(turno.id, controller.signal)
            : await markNoShow(turno.id, controller.signal);

        if (controller.signal.aborted) {
          return;
        }

        setSidePanel((current) =>
          current !== null && current.kind === "ficha" && current.turno.id === updated.id
            ? { kind: "ficha", turno: updated }
            : current,
        );
        setReloadKey((key) => key + 1);
        setFichaRefreshKey((key) => key + 1);
      } catch (cause: unknown) {
        if (!isAbortError(cause) && !controller.signal.aborted) {
          setActionError(toErrorMessage(cause));
        }
      } finally {
        if (!controller.signal.aborted) {
          setPendingTurnoId(null);
        }
      }
    },
    [],
  );

  async function handleStartCancel(turno: TurnoAgenda): Promise<void> {
    setPendingTurnoId(turno.id);
    setActionError(null);
    setReprogramacion(null);
    try {
      const cotizacion = await cotizarCancelacionStaff(turno.id);
      setCancelacion({ turnoId: turno.id, porcentaje: cotizacion.porcentaje, motivo: "" });
    } catch (cause: unknown) {
      setActionError(toErrorMessage(cause));
    } finally {
      setPendingTurnoId(null);
    }
  }

  async function handleConfirmCancel(): Promise<void> {
    if (cancelacion === null) {
      return;
    }
    setPendingTurnoId(cancelacion.turnoId);
    setActionError(null);
    try {
      await cancelarTurnoStaff(cancelacion.turnoId, cancelacion.motivo);
      setCancelacion(null);
      setReloadKey((key) => key + 1);
      setFichaRefreshKey((key) => key + 1);
    } catch (cause: unknown) {
      setActionError(toErrorMessage(cause));
    } finally {
      setPendingTurnoId(null);
    }
  }

  function handleStartReprogram(turno: TurnoAgenda): void {
    setActionError(null);
    setCancelacion(null);
    setReprogramacion({
      turnoId: turno.id,
      odontologoId: turno.odontologo_id,
      fecha: "",
      slots: [],
      loadingSlots: false,
      slotError: null,
      nuevoInicio: "",
    });
  }

  async function handleReprogramFechaChange(nuevaFecha: string): Promise<void> {
    if (reprogramacion === null) {
      return;
    }
    if (nuevaFecha === "" || esFechaPasada(nuevaFecha)) {
      setReprogramacion((prev) =>
        prev === null
          ? null
          : {
              ...prev,
              fecha: nuevaFecha,
              slots: [],
              nuevoInicio: "",
              slotError: esFechaPasada(nuevaFecha) ? "No se puede reprogramar al pasado." : null,
            },
      );
      return;
    }

    const odId = reprogramacion.odontologoId;
    setReprogramacion((prev) =>
      prev === null
        ? null
        : {
            ...prev,
            fecha: nuevaFecha,
            slots: [],
            nuevoInicio: "",
            loadingSlots: true,
            slotError: null,
          },
    );

    try {
      const disp = await getDisponibilidad(odId, nuevaFecha);
      setReprogramacion((prev) =>
        prev === null
          ? null
          : {
              ...prev,
              slots: disp.slots,
              loadingSlots: false,
              slotError: null,
            },
      );
    } catch (cause: unknown) {
      setReprogramacion((prev) =>
        prev === null
          ? null
          : {
              ...prev,
              slots: [],
              loadingSlots: false,
              slotError: toErrorMessage(cause),
            },
      );
    }
  }

  async function handleConfirmReprogram(): Promise<void> {
    if (reprogramacion === null || reprogramacion.nuevoInicio === "") {
      return;
    }
    setPendingTurnoId(reprogramacion.turnoId);
    setActionError(null);
    try {
      await reprogramarTurnoStaff(
        reprogramacion.turnoId,
        reprogramacion.nuevoInicio,
        nuevaIdempotencyKey(),
      );
      setReprogramacion(null);
      setReloadKey((key) => key + 1);
      setFichaRefreshKey((key) => key + 1);
    } catch (cause: unknown) {
      setActionError(toErrorMessage(cause));
    } finally {
      setPendingTurnoId(null);
    }
  }

  const handleClosePanel = useCallback(() => {
    setSidePanel(null);
  }, []);

  function handleDateChange(value: string): void {
    if (!isIsoDate(value) || value === rawFecha) {
      return;
    }
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        next.set("fecha", value);
        return next;
      },
      { replace: true },
    );
  }

  function handleProfessionalChange(value: string): void {
    setProfessionalInput(value);
    const trimmed = value.trim();
    const nextParam = isUuid(trimmed) ? trimmed : null;
    if (nextParam === searchParams.get("odontologo_id")) {
      return;
    }
    lastProfessionalParamRef.current = nextParam ?? "";
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        if (nextParam === null) {
          next.delete("odontologo_id");
        } else {
          next.set("odontologo_id", nextParam);
        }
        return next;
      },
      { replace: true },
    );
  }

  function handleRefresh(): void {
    setReloadKey((key) => key + 1);
  }

  if (!canManageAgenda) {
    return (
      <section className="page">
        <header className="page__header">
          <div>
            <p className="page__kicker">Agenda del día</p>
            <h1>Turnos y estados</h1>
          </div>
        </header>
        <p className="feedback feedback--error" role="alert" aria-live="polite">
          Tu usuario no tiene acceso a la agenda del consultorio.
        </p>
      </section>
    );
  }

  const hasTurnos = turnos.length > 0;
  const showEmptyState =
    !loading &&
    !hasTurnos &&
    error === null &&
    !missingProfessional &&
    !awaitingProfessional &&
    !invalidProfessional;
  const selectedFichaId = sidePanel?.kind === "ficha" ? sidePanel.turno.id : null;

  return (
    <section className="page agenda-page">
      <header className="page__header">
        <div>
          <p className="page__kicker">Agenda del día</p>
          <h1>Turnos y estados</h1>
        </div>
        <p className="page__meta">Consultorio único · Hora local</p>
      </header>

      <div className="filters" role="group" aria-label="Filtros de agenda">
        <div className="field">
          <label htmlFor="fecha">Fecha</label>
          <input
            id="fecha"
            type="date"
            value={fecha}
            onChange={(event) => handleDateChange(event.target.value)}
          />
        </div>

        {isOdontologo ? (
          <div className="field">
            <span className="field__label">Profesional</span>
            <p className="field__static">
              {effectiveOdontologoId === ""
                ? "Sin profesional asociado"
                : effectiveOdontologoId}
            </p>
            <p className="field__hint">Definido por tu usuario. Solo se consulta tu agenda.</p>
          </div>
        ) : (
          <div className="field">
            <label htmlFor="odontologo_id">UUID del profesional</label>
            <input
              id="odontologo_id"
              type="text"
              value={professionalInput}
              onChange={(event) => handleProfessionalChange(event.target.value)}
              placeholder="00000000-0000-0000-0000-000000000000"
              autoComplete="off"
              spellCheck={false}
              aria-invalid={invalidProfessional}
              aria-describedby={
                invalidProfessional ? "odontologo-error" : "odontologo-hint"
              }
            />
            {invalidProfessional ? (
              <p id="odontologo-error" className="field__error">
                El UUID ingresado no es válido.
              </p>
            ) : (
              <p id="odontologo-hint" className="field__hint">
                Formato UUID. Lo provee administración; no se guarda en el navegador.
              </p>
            )}
          </div>
        )}

        <button
          type="button"
          className="button button--ghost"
          onClick={handleRefresh}
          disabled={loading || effectiveOdontologoId === ""}
        >
          Actualizar agenda
        </button>
      </div>

      {error !== null && (
        <div className="feedback feedback--error" role="alert" aria-live="polite">
          <p>{error}</p>
          <button type="button" className="button button--quiet" onClick={handleRefresh}>
            Reintentar
          </button>
        </div>
      )}

      {actionError !== null && (
        <p className="feedback feedback--error" role="alert" aria-live="polite">
          {actionError}
        </p>
      )}

      <div
        className={sidePanel !== null ? "agenda-workspace agenda-workspace--panel" : "agenda-workspace"}
      >
        <section className="agenda-ledger" aria-labelledby="agenda-list-title" aria-busy={loading}>
          <div className="agenda-ledger__head">
            <h2 id="agenda-list-title">Turnos del {formatDate(fecha)}</h2>
            <p className="agenda-ledger__count">
              {turnos.length} {turnos.length === 1 ? "turno" : "turnos"}
            </p>
          </div>

          {loading && !hasTurnos && (
            <p className="state" role="status">
              Cargando agenda…
            </p>
          )}

          {loading && hasTurnos && (
            <p className="state state--inline" role="status">
              Actualizando agenda…
            </p>
          )}

          {!loading && missingProfessional && (
            <p className="state state--warning">
              Tu usuario no tiene un profesional asociado. No se puede consultar la agenda.
            </p>
          )}

          {!loading && awaitingProfessional && (
            <p className="state">Ingresá el UUID del profesional para ver la agenda.</p>
          )}

          {!loading && invalidProfessional && (
            <p className="state state--warning">Corregí el UUID para consultar la agenda.</p>
          )}

          {showEmptyState && (
            <p className="state">No hay turnos para esta fecha y profesional.</p>
          )}

          {hasTurnos && (
            <ol className="agenda-list">
              {turnos.map((turno) => {
                const isConfirmado = turno.estado === "confirmado";
                const finPasado = isFinPast(turno.fin, now);
                const isPending = pendingTurnoId === turno.id;
                const actionsDisabled = pendingTurnoId !== null;
                const isSelected = selectedFichaId === turno.id;

                return (
                  <li
                    key={turno.id}
                    className={isSelected ? "agenda-row agenda-row--selected" : "agenda-row"}
                  >
                    <button
                      type="button"
                      className="agenda-row__select"
                      onClick={() => setSidePanel({ kind: "ficha", turno })}
                      aria-pressed={isSelected}
                    >
                      <span className="agenda-row__time">
                        {formatTime(turno.inicio)}
                        <span aria-hidden="true">–</span>
                        {formatTime(turno.fin)}
                      </span>
                      <span className="agenda-row__body">
                        <span className="agenda-row__canal">Canal: {turno.canal}</span>
                        <span className="agenda-row__id">
                          Paciente #{turno.paciente_id.slice(0, 8)}
                        </span>
                      </span>
                      <StatusBadge estado={turno.estado} />
                    </button>

                    <div className="agenda-row__actions">
                      {isConfirmado && (
                        <>
                          <button
                            type="button"
                            className="button button--primary"
                            onClick={() => {
                              void runAction(turno, "atendido");
                            }}
                            disabled={actionsDisabled}
                          >
                            {isPending ? "Guardando…" : "Atendido"}
                          </button>
                          <button
                            type="button"
                            className="button button--danger"
                            onClick={() => {
                              void runAction(turno, "no_show");
                            }}
                            disabled={!finPasado || actionsDisabled}
                            title={
                              finPasado
                                ? undefined
                                : `Disponible desde las ${formatTime(turno.fin)}`
                            }
                          >
                            No show
                          </button>
                          <button
                            type="button"
                            className="button button--quiet"
                            disabled={actionsDisabled}
                            onClick={() => {
                              void handleStartCancel(turno);
                            }}
                          >
                            Cancelar
                          </button>
                          <button
                            type="button"
                            className="button button--quiet"
                            disabled={actionsDisabled}
                            onClick={() => {
                              handleStartReprogram(turno);
                            }}
                          >
                            Reprogramar
                          </button>
                          {!finPasado && (
                            <span className="agenda-row__hint">
                              No show desde {formatTime(turno.fin)}
                            </span>
                          )}
                        </>
                      )}

                      <button
                        type="button"
                        className="button button--quiet"
                        onClick={() => setSidePanel({ kind: "traza", turnoId: turno.id })}
                      >
                        Ver trazabilidad
                      </button>
                    </div>

                    {cancelacion !== null && cancelacion.turnoId === turno.id && (
                      <div className="wizard-step">
                        <p className="notice">
                          Devolución aplicable según anticipación: {cancelacion.porcentaje} %.
                        </p>
                        <div className="field">
                          <label htmlFor={`cancel-motivo-${turno.id}`}>Motivo de cancelación</label>
                          <input
                            id={`cancel-motivo-${turno.id}`}
                            type="text"
                            value={cancelacion.motivo}
                            onChange={(event) => {
                              const val = event.target.value;
                              setCancelacion((prev) =>
                                prev === null ? null : { ...prev, motivo: val },
                              );
                            }}
                          />
                        </div>
                        <div className="wizard-actions">
                          <button
                            type="button"
                            className="button button--danger"
                            disabled={actionsDisabled}
                            onClick={() => {
                              void handleConfirmCancel();
                            }}
                          >
                            Confirmar cancelación
                          </button>
                          <button
                            type="button"
                            className="button button--quiet"
                            onClick={() => setCancelacion(null)}
                          >
                            Volver
                          </button>
                        </div>
                      </div>
                    )}

                    {reprogramacion !== null && reprogramacion.turnoId === turno.id && (
                      <div className="wizard-step">
                        <p className="notice">
                          Al reprogramar se conserva la seña original sin cargos ni recálculos
                          adicionales (Q3).
                        </p>
                        <div className="field">
                          <label htmlFor={`reprog-fecha-${turno.id}`}>
                            Nueva fecha para reprogramar
                          </label>
                          <input
                            id={`reprog-fecha-${turno.id}`}
                            type="date"
                            min={todayLocal()}
                            value={reprogramacion.fecha}
                            onChange={(event) => {
                              void handleReprogramFechaChange(event.target.value);
                            }}
                          />
                        </div>
                        {reprogramacion.loadingSlots && (
                          <p className="state">Consultando slots disponibles…</p>
                        )}
                        {reprogramacion.slotError !== null && (
                          <p className="feedback feedback--error" role="alert">
                            {reprogramacion.slotError}
                          </p>
                        )}
                        {reprogramacion.slots.length > 0 && (
                          <fieldset className="slot-grid">
                            <legend className="field__label">Elegí nuevo horario</legend>
                            {reprogramacion.slots.map((slot) => {
                              const blocked = fueraDeAnticipacion(slot.inicio);
                              const checked = reprogramacion.nuevoInicio === slot.inicio;
                              return (
                                <label
                                  key={slot.inicio}
                                  className={checked ? "slot slot--selected" : "slot"}
                                >
                                  <input
                                    type="radio"
                                    name={`reprog-staff-${turno.id}`}
                                    value={slot.inicio}
                                    checked={checked}
                                    disabled={blocked}
                                    onChange={() => {
                                      setReprogramacion((prev) =>
                                        prev === null ? null : { ...prev, nuevoInicio: slot.inicio },
                                      );
                                    }}
                                  />
                                  <span>{formatTime(slot.inicio)}</span>
                                </label>
                              );
                            })}
                          </fieldset>
                        )}
                        <div className="wizard-actions">
                          <button
                            type="button"
                            className="button button--primary"
                            disabled={actionsDisabled || reprogramacion.nuevoInicio === ""}
                            onClick={() => {
                              void handleConfirmReprogram();
                            }}
                          >
                            Confirmar reprogramación
                          </button>
                          <button
                            type="button"
                            className="button button--quiet"
                            onClick={() => setReprogramacion(null)}
                          >
                            Cancelar edición
                          </button>
                        </div>
                      </div>
                    )}
                  </li>
                );
              })}
            </ol>
          )}
        </section>

        {sidePanel?.kind === "ficha" && (
          <FichaPacientePanel
            pacienteId={sidePanel.turno.paciente_id}
            refreshKey={fichaRefreshKey}
            onClose={handleClosePanel}
          />
        )}

        {sidePanel?.kind === "traza" && (
          <TrazabilidadPanel
            turnoId={sidePanel.turnoId}
            refreshKey={fichaRefreshKey}
            onClose={handleClosePanel}
          />
        )}
      </div>

      <section className="wizard-step" aria-label="Herramientas operativas">
        <div className="wizard-actions">
          <button
            type="button"
            className="button button--quiet"
            disabled={effectiveOdontologoId === ""}
            onClick={() => setShowDisponibilidad((v) => !v)}
          >
            {showDisponibilidad ? "Ocultar disponibilidad y bloqueos" : "Disponibilidad y bloqueos"}
          </button>
          {canCreateTelefonica && (
            <button
              type="button"
              className="button button--quiet"
              onClick={() => setShowTelefonica((v) => !v)}
            >
              {showTelefonica ? "Ocultar reserva telefónica" : "Reserva telefónica (Q10)"}
            </button>
          )}
        </div>

        {showDisponibilidad && effectiveOdontologoId !== "" && (
          <DisponibilidadBloqueosPanel
            odontologoId={effectiveOdontologoId}
            isOdontologo={isOdontologo}
          />
        )}

        {(showTelefonica || !canCreateTelefonica) && (
          <ReservaTelefonicaPanel
            odontologoId={effectiveOdontologoId}
            rol={role}
            onCreated={(fechaCreada) => {
              if (fechaCreada === fecha) {
                setReloadKey((k) => k + 1);
              } else if (isIsoDate(fechaCreada)) {
                handleDateChange(fechaCreada);
              }
            }}
          />
        )}
      </section>
    </section>
  );
}
