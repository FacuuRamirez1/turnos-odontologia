import { useEffect, useRef, useState } from "react";
import { descargarComprobantePdf, getTrazabilidadTurno } from "../api/backoffice";
import { ApiError, isAbortError, toErrorMessage } from "../api/errors";
import type { TrazabilidadTurno } from "../api/types";
import { formatearMonto } from "../pages/reserva/reservaUtils";
import { formatDate, formatTime } from "../utils/format";
import { StatusBadge } from "./StatusBadge";

interface TrazabilidadPanelProps {
  turnoId: string;
  refreshKey?: number;
  onClose: () => void;
}

function panelError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401 || error.status === 403) {
      return "No tenés permisos para ver la trazabilidad de este turno.";
    }
    if (error.status === 404) {
      return "No se encontró el turno solicitado.";
    }
  }
  return toErrorMessage(error);
}

function formatDateTime(iso: string | null): string {
  if (iso === null || iso.trim() === "") {
    return "Sin registro";
  }
  return `${formatDate(iso)} · ${formatTime(iso)}`;
}

export function TrazabilidadPanel({
  turnoId,
  refreshKey = 0,
  onClose,
}: TrazabilidadPanelProps): JSX.Element {
  const [traza, setTraza] = useState<TrazabilidadTurno | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const panelRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    panelRef.current?.focus();
  }, [turnoId]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setPdfError(null);
    setTraza(null);

    getTrazabilidadTurno(turnoId, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          setTraza(data);
        }
      })
      .catch((cause: unknown) => {
        if (isAbortError(cause) || controller.signal.aborted) {
          return;
        }
        setTraza(null);
        setError(panelError(cause));
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [turnoId, refreshKey]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  async function handleDescargarPdf(comprobanteId: string, numero: string): Promise<void> {
    setDownloadingId(comprobanteId);
    setPdfError(null);
    try {
      const blob = await descargarComprobantePdf(comprobanteId);
      if (typeof URL.createObjectURL === "function") {
        const objectUrl = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = objectUrl;
        anchor.download = `comprobante-${numero}.pdf`;
        anchor.click();
        URL.revokeObjectURL(objectUrl);
      }
    } catch (cause: unknown) {
      setPdfError(panelError(cause));
    } finally {
      setDownloadingId(null);
    }
  }

  return (
    <aside
      ref={panelRef}
      tabIndex={-1}
      className="ficha-panel"
      aria-labelledby="trazabilidad-title"
    >
      <header className="ficha-panel__header">
        <div>
          <p className="ficha-panel__kicker">Cadena auditable</p>
          <h2 id="trazabilidad-title">
            Trazabilidad del turno{" "}
            {traza !== null && <span className="badge-simulado">{traza.marca}</span>}
          </h2>
        </div>
        <button type="button" className="button button--quiet" onClick={onClose}>
          Cerrar trazabilidad
        </button>
      </header>

      {loading && (
        <p className="state" role="status">
          Cargando trazabilidad…
        </p>
      )}

      {error !== null && (
        <p className="feedback feedback--error" role="alert" aria-live="polite">
          {error}
        </p>
      )}

      {pdfError !== null && (
        <p className="feedback feedback--error" role="alert" aria-live="polite">
          {pdfError}
        </p>
      )}

      {!loading && error === null && traza !== null && (
        <>
          <section className="ficha-block" aria-labelledby="traza-turno">
            <h3 id="traza-turno">Turno</h3>
            <dl className="ficha-data">
              <div>
                <dt>ID</dt>
                <dd className="mono">{traza.turno.id}</dd>
              </div>
              <div>
                <dt>Horario</dt>
                <dd>{formatDateTime(traza.turno.inicio)}</dd>
              </div>
              <div>
                <dt>Estado</dt>
                <dd>
                  <StatusBadge estado={traza.turno.estado} />
                </dd>
              </div>
              <div>
                <dt>Canal</dt>
                <dd>{traza.turno.canal}</dd>
              </div>
            </dl>
          </section>

          <section className="ficha-block" aria-labelledby="traza-pago">
            <h3 id="traza-pago">Pago</h3>
            {traza.pago === null ? (
              <p className="state state--inline">Sin pago asociado.</p>
            ) : (
              <dl className="ficha-data">
                <div>
                  <dt>Estado</dt>
                  <dd>{traza.pago.estado}</dd>
                </div>
                <div>
                  <dt>Monto</dt>
                  <dd>
                    {formatearMonto(String(traza.pago.monto))} {traza.pago.moneda}{" "}
                    <span className="badge-simulado">{traza.marca}</span>
                  </dd>
                </div>
                <div>
                  <dt>Proveedor</dt>
                  <dd>{traza.pago.proveedor}</dd>
                </div>
              </dl>
            )}
          </section>

          <section className="ficha-block" aria-labelledby="traza-devolucion">
            <h3 id="traza-devolucion">Devolución</h3>
            {traza.devolucion === null ? (
              <p className="state state--inline">Sin devolución asociada.</p>
            ) : (
              <dl className="ficha-data">
                <div>
                  <dt>Estado</dt>
                  <dd>{traza.devolucion.estado}</dd>
                </div>
                <div>
                  <dt>Monto ({traza.devolucion.porcentaje} %)</dt>
                  <dd>{formatearMonto(String(traza.devolucion.monto))}</dd>
                </div>
                <div>
                  <dt>Refund ID</dt>
                  <dd className="mono">{traza.devolucion.mp_refund_id ?? "Pendiente"}</dd>
                </div>
              </dl>
            )}
          </section>

          <section className="ficha-block" aria-labelledby="traza-comprobantes">
            <h3 id="traza-comprobantes">Recibos internos</h3>
            {traza.comprobantes.length === 0 ? (
              <p className="state state--inline">Sin comprobantes emitidos.</p>
            ) : (
              <ul className="history-list">
                {traza.comprobantes.map((comp) => (
                  <li key={comp.id} className="history-row">
                    <span>
                      <strong>{comp.numero}</strong> · {comp.concepto} ·{" "}
                      {formatearMonto(String(comp.monto))}{" "}
                      {comp.simulado && <span className="badge-simulado">(simulado)</span>}
                    </span>
                    <button
                      type="button"
                      className="button button--quiet"
                      disabled={downloadingId === comp.id}
                      onClick={() => {
                        void handleDescargarPdf(comp.id, comp.numero);
                      }}
                    >
                      {downloadingId === comp.id ? "Descargando…" : `Descargar PDF ${comp.numero}`}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="ficha-block" aria-labelledby="traza-eventos">
            <h3 id="traza-eventos">Eventos de pago</h3>
            {traza.eventos_pago.length === 0 ? (
              <p className="state state--inline">Sin eventos de pago.</p>
            ) : (
              <ul className="history-list">
                {traza.eventos_pago.map((ev) => (
                  <li key={ev.id} className="history-row">
                    <span>
                      <strong>{ev.tipo_evento}</strong> · actor: {ev.actor}
                    </span>
                    <span className="mono">{formatDateTime(ev.fecha)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="ficha-block" aria-labelledby="traza-historial">
            <h3 id="traza-historial">Historial de estados</h3>
            {traza.historial.length === 0 ? (
              <p className="state state--inline">Sin transiciones registradas.</p>
            ) : (
              <ul className="history-list">
                {traza.historial.map((h) => (
                  <li key={h.id} className="history-row">
                    <span>
                      <strong>
                        {h.estado_anterior} → {h.estado_nuevo}
                      </strong>{" "}
                      · actor: {h.actor_tipo} ({h.actor_id})
                      {h.motivo !== null && h.motivo !== "" ? ` · motivo: ${h.motivo}` : ""}
                    </span>
                    <span className="mono">{formatDateTime(h.fecha)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </aside>
  );
}
