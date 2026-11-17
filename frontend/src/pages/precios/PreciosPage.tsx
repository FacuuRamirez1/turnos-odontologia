import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { isAbortError, mapPublicError } from "../../api/errors";
import { getPrecios } from "../../api/public";
import type { PreciosPublicos } from "../../api/types";
import { formatearMonto } from "../reserva/reservaUtils";

export function PreciosPage(): JSX.Element {
  const [precios, setPrecios] = useState<PreciosPublicos | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [intento, setIntento] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let activo = true;
    setCargando(true);
    setError(null);

    getPrecios(controller.signal)
      .then((respuesta) => {
        if (!activo) {
          return;
        }
        setPrecios(respuesta);
      })
      .catch((cause: unknown) => {
        if (!activo || isAbortError(cause)) {
          return;
        }
        setPrecios(null);
        setError(mapPublicError(cause).mensaje);
      })
      .finally(() => {
        if (activo) {
          setCargando(false);
        }
      });

    return () => {
      activo = false;
      controller.abort();
    };
  }, [intento]);

  return (
    <main className="public-page">
      <header className="public-page__header">
        <div>
          <p className="page__kicker">Transparencia de aranceles</p>
          <h1>
            Precios y condiciones
            {precios !== null && <span className="badge-simulado">{precios.marca}</span>}
          </h1>
        </div>
        <Link to="/reservar" className="button button--primary">
          Reservar turno
        </Link>
      </header>

      {cargando && (
        <section className="wizard-step" aria-busy="true">
          <p className="state">Consultando aranceles vigentes...</p>
        </section>
      )}

      {!cargando && error !== null && (
        <section className="wizard-step" aria-labelledby="precios-error-title">
          <h2 id="precios-error-title">No pudimos cargar los aranceles</h2>
          <p className="feedback feedback--error" role="alert" aria-live="polite">
            {error}
          </p>
          <div className="wizard-actions">
            <button
              type="button"
              className="button button--primary"
              onClick={() => {
                setIntento((valor) => valor + 1);
              }}
            >
              Reintentar
            </button>
          </div>
        </section>
      )}

      {!cargando && precios !== null && (
        <>
          <section className="wizard-step" aria-labelledby="precios-lista-title">
            <h2 id="precios-lista-title">Aranceles por profesional</h2>
            <p className="notice">
              El pago de seña en esta etapa opera en modo {precios.marca}, sin cobros reales de
              dinero ni emisión fiscal.
            </p>

            {precios.odontologos.length === 0 ? (
              <p className="state">No hay profesionales activos publicados en este momento.</p>
            ) : (
              <ul className="options">
                {precios.odontologos.map((item, indice) => (
                  <li key={item.odontologo_id} className="option">
                    <div className="option__body">
                      <span className="option__title">
                        Profesional #{indice + 1}{" "}
                        <span className="badge-simulado">{precios.marca}</span>
                      </span>
                      <span className="option__meta">
                        Turno: {formatearMonto(item.monto_turno)} · Seña:{" "}
                        {formatearMonto(item.monto_senia)}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="wizard-step" aria-labelledby="precios-trial-title">
            <h2 id="precios-trial-title">Prueba de reserva online (Trial)</h2>
            <dl className="summary">
              <div>
                <dt>Estado</dt>
                <dd>{precios.trial.disponible ? "Disponible" : "No disponible"}</dd>
              </div>
              <div>
                <dt>Requisito de pago</dt>
                <dd>
                  {precios.trial.requiere_tarjeta
                    ? "Requiere tarjeta asociada"
                    : "Sin tarjeta requerida"}
                </dd>
              </div>
              <div>
                <dt>Duración</dt>
                <dd>
                  {precios.trial.dias !== null
                    ? `${precios.trial.dias} días`
                    : "Según configuración vigente del consultorio"}
                </dd>
              </div>
            </dl>
          </section>
        </>
      )}
    </main>
  );
}
