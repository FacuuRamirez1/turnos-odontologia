import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { isAbortError, mapPublicError, PublicApiError } from "../../api/errors";
import { cancelarDesdeMail, confirmarDesdeMail } from "../../api/public";
import type { MailAccionResult } from "../../api/types";
import { fechaHoraSlot, formatearMonto } from "../reserva/reservaUtils";

export type AccionMail = "confirmar" | "cancelar";

export interface MailAccionPageProps {
  accion: AccionMail;
}

const TITULO_POR_ACCION: Record<AccionMail, string> = {
  confirmar: "Confirmación de turno",
  cancelar: "Cancelación de turno",
};

function mensajeDeError(cause: unknown): {
  texto: string;
  reintentable: boolean;
} {
  const publico = cause instanceof PublicApiError ? cause : mapPublicError(cause);
  if (publico.kind === "rate_limit" || publico.kind === "red" || publico.kind === "servidor") {
    return { texto: publico.mensaje, reintentable: true };
  }
  if (
    (publico.code === "TOKEN_INVALIDO" || publico.code === "ESTADO_INCOMPATIBLE") &&
    publico.detail !== null &&
    publico.detail.trim() !== ""
  ) {
    return { texto: publico.detail, reintentable: false };
  }
  return { texto: publico.mensaje, reintentable: false };
}

export function MailAccionPage({ accion }: MailAccionPageProps): JSX.Element {
  const [params] = useSearchParams();
  const token = (params.get("token") ?? "").trim();

  const [cargando, setCargando] = useState(token !== "");
  const [resultado, setResultado] = useState<MailAccionResult | null>(null);
  const [error, setError] = useState<{ texto: string; reintentable: boolean } | null>(null);
  const [intento, setIntento] = useState(0);

  useEffect(() => {
    if (token === "") {
      setCargando(false);
      setResultado(null);
      setError(null);
      return;
    }

    const controller = new AbortController();
    let activo = true;
    setCargando(true);
    setError(null);

    const llamada =
      accion === "confirmar"
        ? confirmarDesdeMail(token, controller.signal)
        : cancelarDesdeMail(token, controller.signal);

    llamada
      .then((respuesta) => {
        if (!activo) {
          return;
        }
        if (!respuesta.ok) {
          setResultado(null);
          setError({
            texto:
              respuesta.detail?.trim() ||
              respuesta.mensaje?.trim() ||
              "El enlace ya no es válido o el turno no admite esta acción.",
            reintentable: respuesta.code === "RATE_LIMIT",
          });
          return;
        }
        setResultado(respuesta);
      })
      .catch((cause: unknown) => {
        if (!activo || isAbortError(cause)) {
          return;
        }
        setResultado(null);
        setError(mensajeDeError(cause));
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
  }, [accion, token, intento]);

  return (
    <main className="public-page">
      <header className="public-page__header">
        <p className="page__kicker">Gestión por correo</p>
        <h1>{TITULO_POR_ACCION[accion]}</h1>
      </header>

      {token === "" && (
        <section className="wizard-step" aria-labelledby="mail-sin-token-title">
          <h2 id="mail-sin-token-title">Enlace incompleto</h2>
          <p className="feedback feedback--error" role="alert" aria-live="polite">
            Falta el token de verificación en el enlace. Abrí el enlace completo desde tu correo.
          </p>
          <div className="wizard-actions">
            <Link to="/reservar" className="button button--primary">
              Volver a reservar
            </Link>
            <Link to="/mis-turnos" className="button button--quiet">
              Ir a mis turnos
            </Link>
          </div>
        </section>
      )}

      {token !== "" && cargando && (
        <section className="wizard-step" aria-busy="true">
          <p className="state">Procesando solicitud...</p>
        </section>
      )}

      {token !== "" && !cargando && error !== null && (
        <section className="wizard-step" aria-labelledby="mail-error-title">
          <h2 id="mail-error-title">No se pudo completar la acción</h2>
          <p className="feedback feedback--error" role="alert" aria-live="polite">
            {error.texto}
          </p>
          <div className="wizard-actions">
            {error.reintentable && (
              <button
                type="button"
                className="button button--primary"
                onClick={() => {
                  setIntento((valor) => valor + 1);
                }}
              >
                Reintentar
              </button>
            )}
            <Link to="/reservar" className="button button--quiet">
              Volver a reservar
            </Link>
          </div>
        </section>
      )}

      {token !== "" && !cargando && resultado !== null && (
        <section className="wizard-step" aria-labelledby="mail-ok-title">
          <h2 id="mail-ok-title">
            {resultado.estado === "cancelado" ? "Turno cancelado" : "Turno confirmado"}
            {resultado.marca !== undefined && (
              <span className="badge-simulado">{resultado.marca}</span>
            )}
          </h2>

          <p className="state state--ok">
            {resultado.mensaje ??
              (accion === "confirmar"
                ? "Tu turno quedó confirmado."
                : "Tu turno fue cancelado correctamente.")}
          </p>

          <dl className="summary">
            {resultado.estado !== undefined && (
              <div>
                <dt>Estado</dt>
                <dd>{resultado.estado}</dd>
              </div>
            )}
            {resultado.inicio !== undefined && (
              <div>
                <dt>Fecha y horario</dt>
                <dd>{fechaHoraSlot(resultado.inicio)}</dd>
              </div>
            )}
            {resultado.porcentaje !== undefined && (
              <div>
                <dt>Porcentaje de devolución</dt>
                <dd>{resultado.porcentaje} %</dd>
              </div>
            )}
            {resultado.devolucion !== undefined && resultado.devolucion !== null && (
              <>
                <div>
                  <dt>Monto a reintegrar</dt>
                  <dd>
                    {formatearMonto(String(resultado.devolucion.monto))}{" "}
                    {resultado.marca !== undefined && (
                      <span className="badge-simulado">{resultado.marca}</span>
                    )}
                  </dd>
                </div>
                <div>
                  <dt>Estado de la devolución</dt>
                  <dd>{resultado.devolucion.estado}</dd>
                </div>
              </>
            )}
          </dl>

          <div className="wizard-actions">
            <Link to="/reservar" className="button button--primary">
              Reservar otro turno
            </Link>
            <Link to="/mis-turnos" className="button button--quiet">
              Consultar mis turnos
            </Link>
          </div>
        </section>
      )}
    </main>
  );
}
