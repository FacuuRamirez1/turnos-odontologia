import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { mapPublicError } from "../../api/errors";
import { simularPago } from "../../api/public";
import {
  ACCIONES_PAGO_SIMULADO,
  type AccionPagoSimulado,
  type SimulacionPago,
} from "../../api/types";
import { formatearMonto } from "./reservaUtils";

const ETIQUETA_ACCION: Record<AccionPagoSimulado, string> = {
  aprobar: "Aprobar",
  rechazar: "Rechazar",
  expirar: "Expirar",
};

const LEYENDA_SIMULADA = "SIMULADO — sin valor fiscal ni movimiento de dinero";

export function CheckoutSimuladoPage(): JSX.Element {
  const [params] = useSearchParams();
  const pagoId = (params.get("pago_id") ?? "").trim();
  const token = (params.get("token") ?? "").trim();
  const montoSenia = params.get("monto_senia");
  const faltantes = [pagoId === "" ? "pago_id" : null, token === "" ? "token" : null].filter(
    (campo): campo is string => campo !== null,
  );

  const [accionEnCurso, setAccionEnCurso] = useState<AccionPagoSimulado | null>(null);
  const [resultado, setResultado] = useState<SimulacionPago | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [bloqueado, setBloqueado] = useState(false);

  const marca = resultado?.marca ?? "(simulado)";
  const estadoPago = resultado?.estado_pago ?? "pendiente";
  const estadoTurno = resultado?.estado_turno ?? null;
  const puedeOperar = faltantes.length === 0 && !bloqueado && resultado === null;
  const accionesDeshabilitadas = !puedeOperar || accionEnCurso !== null;

  async function ejecutar(elegida: AccionPagoSimulado): Promise<void> {
    if (!puedeOperar || accionEnCurso !== null) {
      return;
    }
    setAccionEnCurso(elegida);
    setError(null);

    try {
      const respuesta = await simularPago(pagoId, elegida, token);
      setResultado(respuesta);
    } catch (cause: unknown) {
      const publico = mapPublicError(cause);
      if (
        publico.code === "TOKEN_INVALIDO" ||
        publico.status === 403 ||
        publico.status === 404 ||
        publico.status === 409 ||
        publico.status === 422
      ) {
        setBloqueado(true);
        setError(
          "El enlace de pago simulado ya fue utilizado o expiró. Generá una nueva reserva para reintentar.",
        );
      } else {
        setError(publico.mensaje);
      }
    } finally {
      setAccionEnCurso(null);
    }
  }

  return (
    <main className="public-page">
      <header className="public-page__header">
        <p className="page__kicker">Pago de seña</p>
        <h1>
          Checkout Simulado <span className="badge-simulado">{marca}</span>
        </h1>
        <p className="page__meta">{LEYENDA_SIMULADA}</p>
      </header>

      {faltantes.length > 0 && (
        <section className="wizard-step" aria-labelledby="checkout-incompleto-title">
          <h2 id="checkout-incompleto-title">Enlace incompleto</h2>
          <p className="feedback feedback--error" role="alert" aria-live="polite">
            Falta {faltantes.join(" y ")} en el enlace de pago. Volvé a iniciar la reserva.
          </p>
          <p>
            <Link to="/reservar">Volver a reservar</Link>
          </p>
        </section>
      )}

      {faltantes.length === 0 && (
        <section className="wizard-step" aria-labelledby="checkout-acciones-title">
          <h2 id="checkout-acciones-title">Acciones del pago simulado</h2>
          <p className="wizard-step__intro">
            Ninguna acción mueve dinero real. El servidor procesa el evento simulado y el turno
            cambia de estado recién cuando el webhook interno lo confirma.
          </p>

          <dl className="summary">
            <div>
              <dt>Identificador de pago</dt>
              <dd className="mono">{pagoId}</dd>
            </div>
            <div>
              <dt>Estado del pago</dt>
              <dd>{estadoPago}</dd>
            </div>
            <div>
              <dt>Estado del turno</dt>
              <dd>{estadoTurno ?? "sin cambios"}</dd>
            </div>
            {montoSenia !== null && montoSenia.trim() !== "" && (
              <div>
                <dt>Monto de la seña</dt>
                <dd>{formatearMonto(montoSenia)}</dd>
              </div>
            )}
          </dl>

          {error !== null && (
            <p className="feedback feedback--error" role="alert" aria-live="polite">
              {error}
            </p>
          )}

          <div className="wizard-actions">
            {ACCIONES_PAGO_SIMULADO.map((accion) => (
              <button
                key={accion}
                type="button"
                className={accion === "aprobar" ? "button button--primary" : "button button--quiet"}
                onClick={() => {
                  void ejecutar(accion);
                }}
                disabled={accionesDeshabilitadas}
              >
                {ETIQUETA_ACCION[accion]}
              </button>
            ))}
          </div>

          {estadoPago === "aprobado" && (
            <p className="state state--ok">
              Pago aprobado {marca}. El turno quedó en estado{" "}
              {estadoTurno ?? "confirmado"}.
            </p>
          )}

          {(bloqueado || (resultado !== null && estadoPago !== "aprobado")) && (
            <p className="state state--warning">
              El horario fue liberado automáticamente (RN-LIBERACION). Podés reservar otro turno.
            </p>
          )}

          {(bloqueado || (resultado !== null && estadoPago !== "aprobado")) && (
            <p>
              <Link to="/reservar">Volver a reservar</Link>
            </p>
          )}
        </section>
      )}
    </main>
  );
}
