import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getAgenda, markAtendido, markNoShow } from "../../api/agenda";
import { isAbortError, toErrorMessage } from "../../api/errors";
import type { TurnoAgenda } from "../../api/types";
import { useAuth } from "../../auth/AuthProvider";
import { FichaPacientePanel } from "../../components/FichaPacientePanel";
import { StatusBadge } from "../../components/StatusBadge";
import {
  formatDate,
  formatTime,
  isFinPast,
  isIsoDate,
  isUuid,
  todayLocal,
} from "../../utils/format";

type AccionTurno = "atendido" | "no_show";

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
  const [selectedTurno, setSelectedTurno] = useState<TurnoAgenda | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [fichaRefreshKey, setFichaRefreshKey] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  const actionControllerRef = useRef<AbortController | null>(null);

  const role = user?.rol ?? "";
  const isOdontologo = role === "odontologo";
  const canManageAgenda =
    role === "odontologo" || role === "recepcionista" || role === "admin";
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
    setSelectedTurno(null);
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
    setSelectedTurno((current) => {
      if (current === null) {
        return null;
      }
      return turnos.find((turno) => turno.id === current.id) ?? null;
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

        setSelectedTurno((current) =>
          current !== null && current.id === updated.id ? updated : current,
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

  const handleClosePanel = useCallback(() => {
    setSelectedTurno(null);
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
        className={selectedTurno !== null ? "agenda-workspace agenda-workspace--panel" : "agenda-workspace"}
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
                const isSelected = selectedTurno !== null && selectedTurno.id === turno.id;

                return (
                  <li
                    key={turno.id}
                    className={isSelected ? "agenda-row agenda-row--selected" : "agenda-row"}
                  >
                    <button
                      type="button"
                      className="agenda-row__select"
                      onClick={() => setSelectedTurno(turno)}
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

                    {isConfirmado && (
                      <div className="agenda-row__actions">
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
                        {!finPasado && (
                          <span className="agenda-row__hint">
                            No show desde {formatTime(turno.fin)}
                          </span>
                        )}
                      </div>
                    )}
                  </li>
                );
              })}
            </ol>
          )}
        </section>

        {selectedTurno !== null && (
          <FichaPacientePanel
            pacienteId={selectedTurno.paciente_id}
            refreshKey={fichaRefreshKey}
            onClose={handleClosePanel}
          />
        )}
      </div>
    </section>
  );
}
