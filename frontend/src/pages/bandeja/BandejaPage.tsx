import { useCallback, useEffect, useState } from "react";
import {
  aprobarDevolucion,
  ejecutarDevolucion,
  listarAlertasConciliacion,
  listarDevoluciones,
  rechazarDevolucion,
} from "../../api/backoffice";
import { isAbortError, toErrorMessage } from "../../api/errors";
import {
  ESTADOS_DEVOLUCION,
  isEstadoDevolucion,
  type AlertaConciliacion,
  type DevolucionBandeja,
  type EjecucionDevolucion,
  type EstadoDevolucion,
} from "../../api/types";
import { TrazabilidadPanel } from "../../components/TrazabilidadPanel";
import { formatDate, formatTime } from "../../utils/format";
import { formatearMonto } from "../reserva/reservaUtils";

type ModoFormulario =
  | { kind: "aprobar"; devolucionId: string; montoConfirmado: string; motivo: string }
  | { kind: "rechazar"; devolucionId: string; motivo: string };

export function BandejaPage(): JSX.Element {
  const [estadoFiltro, setEstadoFiltro] = useState<EstadoDevolucion | "">("");
  const [devoluciones, setDevoluciones] = useState<DevolucionBandeja[]>([]);
  const [alertas, setAlertas] = useState<AlertaConciliacion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [operandoId, setOperandoId] = useState<string | null>(null);
  const [formulario, setFormulario] = useState<ModoFormulario | null>(null);
  const [ultimaEjecucion, setUltimaEjecucion] = useState<EjecucionDevolucion | null>(null);
  const [trazaTurnoId, setTrazaTurnoId] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    Promise.all([
      listarDevoluciones(estadoFiltro === "" ? undefined : estadoFiltro, controller.signal),
      listarAlertasConciliacion(controller.signal),
    ])
      .then(([lista, alertasData]) => {
        if (!controller.signal.aborted) {
          setDevoluciones(lista);
          setAlertas(alertasData);
        }
      })
      .catch((cause: unknown) => {
        if (isAbortError(cause) || controller.signal.aborted) {
          return;
        }
        setDevoluciones([]);
        setAlertas([]);
        setError(toErrorMessage(cause));
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [estadoFiltro, reloadKey]);

  const handleCloseTraza = useCallback(() => {
    setTrazaTurnoId(null);
  }, []);

  async function handleConfirmarAprobacion(): Promise<void> {
    if (formulario === null || formulario.kind !== "aprobar") {
      return;
    }
    const montoLimpio = formulario.montoConfirmado.trim();
    if (montoLimpio === "") {
      setActionError("Ingresá el monto confirmado para aprobar la devolución.");
      return;
    }
    setOperandoId(formulario.devolucionId);
    setActionError(null);
    const motivo = formulario.motivo.trim();
    try {
      await aprobarDevolucion(
        formulario.devolucionId,
        montoLimpio,
        motivo === "" ? undefined : motivo,
      );
      setFormulario(null);
      setReloadKey((k) => k + 1);
    } catch (cause: unknown) {
      setActionError(toErrorMessage(cause));
    } finally {
      setOperandoId(null);
    }
  }

  async function handleConfirmarRechazo(): Promise<void> {
    if (formulario === null || formulario.kind !== "rechazar") {
      return;
    }
    const motivoLimpio = formulario.motivo.trim();
    if (motivoLimpio === "") {
      setActionError("El motivo del rechazo es obligatorio.");
      return;
    }
    setOperandoId(formulario.devolucionId);
    setActionError(null);
    try {
      await rechazarDevolucion(formulario.devolucionId, motivoLimpio);
      setFormulario(null);
      setReloadKey((k) => k + 1);
    } catch (cause: unknown) {
      setActionError(toErrorMessage(cause));
    } finally {
      setOperandoId(null);
    }
  }

  async function handleEjecutar(devolucionId: string): Promise<void> {
    setOperandoId(devolucionId);
    setActionError(null);
    try {
      const ejecutada = await ejecutarDevolucion(devolucionId);
      setUltimaEjecucion(ejecutada);
      setReloadKey((k) => k + 1);
    } catch (cause: unknown) {
      setActionError(toErrorMessage(cause));
    } finally {
      setOperandoId(null);
    }
  }

  const marcaVisible = devoluciones[0]?.marca ?? alertas[0]?.marca ?? "(simulado)";

  return (
    <section className="page">
      <header className="page__header">
        <div>
          <p className="page__kicker">
            Reembolsos y conciliación <span className="badge-simulado">{marcaVisible}</span>
          </p>
          <h1>Bandeja de devoluciones</h1>
        </div>
        <p className="page__meta">
          Toda devolución exige aprobación manual (Q4) y ejecución vía servidor {marcaVisible}.
        </p>
      </header>

      <div className="filters" role="group" aria-label="Filtros de bandeja">
        <div className="field">
          <label htmlFor="bandeja-estado">Estado</label>
          <select
            id="bandeja-estado"
            value={estadoFiltro}
            onChange={(event) => {
              const val = event.target.value;
              setEstadoFiltro(isEstadoDevolucion(val) ? val : "");
            }}
          >
            <option value="">Todas</option>
            {ESTADOS_DEVOLUCION.map((est) => (
              <option key={est} value={est}>
                {est}
              </option>
            ))}
          </select>
        </div>

        <button
          type="button"
          className="button button--ghost"
          disabled={loading}
          onClick={() => {
            setReloadKey((k) => k + 1);
          }}
        >
          Actualizar bandeja
        </button>
      </div>

      {error !== null && (
        <div className="feedback feedback--error" role="alert" aria-live="polite">
          <p>{error}</p>
        </div>
      )}

      {actionError !== null && (
        <p className="feedback feedback--error" role="alert" aria-live="polite">
          {actionError}
        </p>
      )}

      {ultimaEjecucion !== null && (
        <section className="wizard-step" aria-labelledby="ejecucion-ok-title">
          <h2 id="ejecucion-ok-title">
            Devolución ejecutada <span className="badge-simulado">{ultimaEjecucion.marca}</span>
          </h2>
          <p className="state state--ok">
            Refund ID <span className="mono">{ultimaEjecucion.mp_refund_id}</span> · Pago en estado{" "}
            <strong>{ultimaEjecucion.pago_estado}</strong>.
          </p>
        </section>
      )}

      {alertas.length > 0 && (
        <section className="wizard-step" aria-labelledby="alertas-conciliacion-title">
          <h2 id="alertas-conciliacion-title">
            Alertas de conciliación <span className="badge-simulado">{marcaVisible}</span>
          </h2>
          <ul className="history-list">
            {alertas.map((alerta) => (
              <li key={alerta.id} className="history-row">
                <span>
                  <strong>{alerta.tipo}</strong> · {alerta.detalle ?? "Discrepancia detectada"} (pago:{" "}
                  {alerta.estado_pago ?? "-"} vs esperado: {alerta.estado_esperado ?? "-"})
                </span>
                <span className="mono">
                  {formatDate(alerta.fecha)} · {formatTime(alerta.fecha)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div
        className={
          trazaTurnoId !== null ? "agenda-workspace agenda-workspace--panel" : "agenda-workspace"
        }
      >
        <section className="agenda-ledger" aria-labelledby="bandeja-lista-title" aria-busy={loading}>
          <div className="agenda-ledger__head">
            <h2 id="bandeja-lista-title">Solicitudes de devolución</h2>
            <p className="agenda-ledger__count">
              {devoluciones.length} {devoluciones.length === 1 ? "registro" : "registros"}
            </p>
          </div>

          {loading && <p className="state">Cargando devoluciones…</p>}

          {!loading && devoluciones.length === 0 && error === null && (
            <p className="state">No hay devoluciones para el filtro seleccionado.</p>
          )}

          {!loading && devoluciones.length > 0 && (
            <div className="options">
              {devoluciones.map((item) => {
                const ocupado = operandoId === item.id;
                const abriendoAprobar =
                  formulario?.kind === "aprobar" && formulario.devolucionId === item.id;
                const abriendoRechazar =
                  formulario?.kind === "rechazar" && formulario.devolucionId === item.id;

                return (
                  <article key={item.id} className="wizard-step">
                    <dl className="summary">
                      <div>
                        <dt>Estado</dt>
                        <dd>
                          <span className={`status-badge status-badge--${item.estado}`}>
                            {item.estado}
                          </span>
                        </dd>
                      </div>
                      <div>
                        <dt>Monto ({item.porcentaje} %)</dt>
                        <dd>
                          {formatearMonto(String(item.monto))}{" "}
                          <span className="badge-simulado">{item.marca}</span>
                        </dd>
                      </div>
                      <div>
                        <dt>Turno</dt>
                        <dd className="mono">{item.turno_id}</dd>
                      </div>
                      {item.motivo !== null && (
                        <div>
                          <dt>Motivo</dt>
                          <dd>{item.motivo}</dd>
                        </div>
                      )}
                      {item.motivo_rechazo !== null && (
                        <div>
                          <dt>Motivo rechazo</dt>
                          <dd>{item.motivo_rechazo}</dd>
                        </div>
                      )}
                    </dl>

                    <div className="wizard-actions">
                      {item.estado === "pendiente" && (
                        <>
                          <button
                            type="button"
                            className="button button--primary"
                            disabled={ocupado}
                            onClick={() => {
                              setActionError(null);
                              setFormulario({
                                kind: "aprobar",
                                devolucionId: item.id,
                                montoConfirmado: "",
                                motivo: "",
                              });
                            }}
                          >
                            Aprobar devolución
                          </button>
                          <button
                            type="button"
                            className="button button--danger"
                            disabled={ocupado}
                            onClick={() => {
                              setActionError(null);
                              setFormulario({
                                kind: "rechazar",
                                devolucionId: item.id,
                                motivo: "",
                              });
                            }}
                          >
                            Rechazar devolución
                          </button>
                        </>
                      )}

                      {item.estado === "aprobada" && (
                        <button
                          type="button"
                          className="button button--primary"
                          disabled={ocupado}
                          onClick={() => {
                            void handleEjecutar(item.id);
                          }}
                        >
                          {ocupado ? "Ejecutando…" : "Ejecutar devolución"}
                        </button>
                      )}

                      <button
                        type="button"
                        className="button button--quiet"
                        onClick={() => {
                          setTrazaTurnoId(item.turno_id);
                        }}
                      >
                        Ver trazabilidad
                      </button>
                    </div>

                    {abriendoAprobar && formulario.kind === "aprobar" && (
                      <div className="wizard-step">
                        <div className="form-grid">
                          <div className="field">
                            <label htmlFor={`monto-${item.id}`}>Monto confirmado</label>
                            <input
                              id={`monto-${item.id}`}
                              type="text"
                              inputMode="decimal"
                              value={formulario.montoConfirmado}
                              onChange={(event) => {
                                const val = event.target.value;
                                setFormulario((prev) =>
                                  prev?.kind === "aprobar" ? { ...prev, montoConfirmado: val } : prev,
                                );
                              }}
                              placeholder={String(item.monto)}
                            />
                          </div>
                          <div className="field">
                            <label htmlFor={`motivo-aprobar-${item.id}`}>Observación (opcional)</label>
                            <input
                              id={`motivo-aprobar-${item.id}`}
                              type="text"
                              value={formulario.motivo}
                              onChange={(event) => {
                                const val = event.target.value;
                                setFormulario((prev) =>
                                  prev?.kind === "aprobar" ? { ...prev, motivo: val } : prev,
                                );
                              }}
                            />
                          </div>
                        </div>
                        <div className="wizard-actions">
                          <button
                            type="button"
                            className="button button--primary"
                            disabled={ocupado}
                            onClick={() => {
                              void handleConfirmarAprobacion();
                            }}
                          >
                            Confirmar aprobación
                          </button>
                          <button
                            type="button"
                            className="button button--quiet"
                            onClick={() => {
                              setFormulario(null);
                            }}
                          >
                            Cancelar
                          </button>
                        </div>
                      </div>
                    )}

                    {abriendoRechazar && formulario.kind === "rechazar" && (
                      <div className="wizard-step">
                        <div className="field">
                          <label htmlFor={`motivo-rechazar-${item.id}`}>Motivo del rechazo</label>
                          <input
                            id={`motivo-rechazar-${item.id}`}
                            type="text"
                            value={formulario.motivo}
                            onChange={(event) => {
                              const val = event.target.value;
                              setFormulario((prev) =>
                                prev?.kind === "rechazar" ? { ...prev, motivo: val } : prev,
                              );
                            }}
                            placeholder="Indicá el motivo obligatorio"
                          />
                        </div>
                        <div className="wizard-actions">
                          <button
                            type="button"
                            className="button button--danger"
                            disabled={ocupado}
                            onClick={() => {
                              void handleConfirmarRechazo();
                            }}
                          >
                            Confirmar rechazo
                          </button>
                          <button
                            type="button"
                            className="button button--quiet"
                            onClick={() => {
                              setFormulario(null);
                            }}
                          >
                            Cancelar
                          </button>
                        </div>
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </section>

        {trazaTurnoId !== null && (
          <TrazabilidadPanel
            turnoId={trazaTurnoId}
            refreshKey={reloadKey}
            onClose={handleCloseTraza}
          />
        )}
      </div>
    </section>
  );
}
