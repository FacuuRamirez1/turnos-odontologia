import { type FormEvent, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { mapPublicError, PublicApiError } from "../../api/errors";
import {
  cancelarTurnoPublico,
  cotizarCancelacionPublica,
  getDisponibilidad,
  getMisTurnos,
  reprogramarTurnoPublico,
} from "../../api/public";
import type {
  CancelacionTurnoPublico,
  MisTurnoPublico,
  ReprogramacionTurnoPublico,
  SlotDisponible,
} from "../../api/types";
import { formatTime, todayLocal } from "../../utils/format";
import {
  dniValido,
  esFechaPasada,
  fechaHoraSlot,
  formatearMonto,
  fueraDeAnticipacion,
  normalizarDni,
  nuevaIdempotencyKey,
} from "../reserva/reservaUtils";

interface CancelacionActiva {
  turnoId: string;
  porcentaje: number;
  motivo: string;
}

interface ReprogramacionActiva {
  turnoId: string;
  odontologoId: string;
  fecha: string;
  slots: SlotDisponible[];
  cargandoSlots: boolean;
  slotError: string | null;
  nuevoInicio: string;
}

function esErrorDeToken(error: PublicApiError): boolean {
  return (
    error.status === 401 ||
    error.status === 403 ||
    error.code === "TOKEN_INVALIDO" ||
    error.code === "NO_AUTORIZADO"
  );
}

function descripcionPolitica(porcentaje: number): string {
  if (porcentaje === 100) {
    return "Cancelación en término: devolución del 100 % de la seña.";
  }
  if (porcentaje > 0) {
    return `Cancelación fuera de término: devolución del ${porcentaje} % de la seña.`;
  }
  return "Sin devolución de seña aplicable (0 %).";
}

export function MisTurnosPage(): JSX.Element {
  const [params] = useSearchParams();
  const dniInicial = (params.get("dni") ?? "").trim();
  const tokenInicial = (params.get("token") ?? "").trim();

  const [dni, setDni] = useState(dniInicial);
  const [token, setToken] = useState(tokenInicial);
  const [cargando, setCargando] = useState(false);
  const [errorConsulta, setErrorConsulta] = useState<string | null>(null);
  const [turnos, setTurnos] = useState<MisTurnoPublico[] | null>(null);
  const [credencialesActivas, setCredencialesActivas] = useState<{
    dni: string;
    token: string;
  } | null>(null);

  const [accionError, setAccionError] = useState<string | null>(null);
  const [operando, setOperando] = useState(false);
  const [cancelacionActiva, setCancelacionActiva] = useState<CancelacionActiva | null>(null);
  const [resultadoCancelacion, setResultadoCancelacion] =
    useState<CancelacionTurnoPublico | null>(null);

  const [reprogActiva, setReprogActiva] = useState<ReprogramacionActiva | null>(null);
  const [resultadoReprog, setResultadoReprog] = useState<ReprogramacionTurnoPublico | null>(null);

  async function ejecutarConsulta(dniRaw: string, tokenRaw: string): Promise<void> {
    const dniLimpio = normalizarDni(dniRaw);
    const tokenLimpio = tokenRaw.trim();

    if (!dniValido(dniLimpio)) {
      setErrorConsulta("Ingresá un DNI numérico válido (7 u 8 dígitos).");
      return;
    }
    if (tokenLimpio === "") {
      setErrorConsulta(
        "Necesitás ingresar el token enviado por correo además de tu DNI para consultar tus turnos.",
      );
      return;
    }

    setCargando(true);
    setErrorConsulta(null);
    setAccionError(null);
    setCancelacionActiva(null);
    setReprogActiva(null);

    try {
      const lista = await getMisTurnos(dniLimpio, tokenLimpio);
      setTurnos(lista);
      setCredencialesActivas({ dni: dniLimpio, token: tokenLimpio });
    } catch (cause: unknown) {
      const publico = cause instanceof PublicApiError ? cause : mapPublicError(cause);
      if (esErrorDeToken(publico)) {
        setTurnos(null);
        setCredencialesActivas(null);
        setErrorConsulta(
          "No pudimos validar tu token de acceso. Solicitá un nuevo enlace válido enviado por correo.",
        );
      } else {
        setErrorConsulta(publico.mensaje);
      }
    } finally {
      setCargando(false);
    }
  }

  useEffect(() => {
    if (dniInicial === "" || tokenInicial === "") {
      return;
    }
    const dniLimpio = normalizarDni(dniInicial);
    if (!dniValido(dniLimpio)) {
      return;
    }
    let activo = true;
    setCargando(true);
    setErrorConsulta(null);

    getMisTurnos(dniLimpio, tokenInicial)
      .then((lista) => {
        if (!activo) {
          return;
        }
        setTurnos(lista);
        setCredencialesActivas({ dni: dniLimpio, token: tokenInicial });
      })
      .catch((cause: unknown) => {
        if (!activo) {
          return;
        }
        const publico = cause instanceof PublicApiError ? cause : mapPublicError(cause);
        setTurnos(null);
        setCredencialesActivas(null);
        setErrorConsulta(
          esErrorDeToken(publico)
            ? "No pudimos validar tu token de acceso. Solicitá un nuevo enlace válido enviado por correo."
            : publico.mensaje,
        );
      })
      .finally(() => {
        if (activo) {
          setCargando(false);
        }
      });

    return () => {
      activo = false;
    };
  }, [dniInicial, tokenInicial]);

  function onSubmitConsulta(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    void ejecutarConsulta(dni, token);
  }

  function credencialesDisponibles(): { dni: string; token: string } {
    if (credencialesActivas !== null) {
      return credencialesActivas;
    }
    return { dni: normalizarDni(dni), token: token.trim() };
  }

  async function iniciarCancelacion(turno: MisTurnoPublico): Promise<void> {
    const creds = credencialesDisponibles();
    setOperando(true);
    setAccionError(null);
    setReprogActiva(null);
    setResultadoCancelacion(null);

    try {
      const cotizacion = await cotizarCancelacionPublica(turno.id, creds.dni, creds.token);
      setCancelacionActiva({
        turnoId: turno.id,
        porcentaje: cotizacion.porcentaje,
        motivo: "",
      });
    } catch (cause: unknown) {
      const publico = cause instanceof PublicApiError ? cause : mapPublicError(cause);
      if (esErrorDeToken(publico)) {
        setTurnos(null);
        setErrorConsulta(
          "Tu enlace de acceso expiró o no corresponde a este turno. Solicitá uno nuevo por correo.",
        );
      } else {
        setAccionError(publico.detail?.trim() || publico.mensaje);
      }
    } finally {
      setOperando(false);
    }
  }

  async function confirmarCancelacion(): Promise<void> {
    if (cancelacionActiva === null) {
      return;
    }
    const creds = credencialesDisponibles();
    const motivoLimpio = cancelacionActiva.motivo.trim();
    setOperando(true);
    setAccionError(null);

    try {
      const respuesta = await cancelarTurnoPublico(
        cancelacionActiva.turnoId,
        creds.dni,
        creds.token,
        motivoLimpio === "" ? undefined : motivoLimpio,
      );
      setResultadoCancelacion(respuesta);
      setTurnos((prev) =>
        prev === null
          ? null
          : prev.map((item) =>
              item.id === cancelacionActiva.turnoId ? { ...item, estado: respuesta.estado } : item,
            ),
      );
      setCancelacionActiva(null);
    } catch (cause: unknown) {
      const publico = cause instanceof PublicApiError ? cause : mapPublicError(cause);
      if (esErrorDeToken(publico)) {
        setErrorConsulta(
          "Tu token ya fue consumido o no es válido. Solicitá un nuevo enlace por correo.",
        );
      } else {
        setAccionError(publico.detail?.trim() || publico.mensaje);
      }
    } finally {
      setOperando(false);
    }
  }

  function iniciarReprogramacion(turno: MisTurnoPublico): void {
    setAccionError(null);
    setCancelacionActiva(null);
    setResultadoReprog(null);
    setReprogActiva({
      turnoId: turno.id,
      odontologoId: turno.odontologo_id,
      fecha: "",
      slots: [],
      cargandoSlots: false,
      slotError: null,
      nuevoInicio: "",
    });
  }

  async function cargarSlotsReprogramacion(fecha: string): Promise<void> {
    if (reprogActiva === null) {
      return;
    }
    if (fecha === "" || esFechaPasada(fecha)) {
      setReprogActiva((prev) =>
        prev === null
          ? null
          : {
              ...prev,
              fecha,
              slots: [],
              nuevoInicio: "",
              slotError: esFechaPasada(fecha) ? "No podés reprogramar a una fecha pasada." : null,
            },
      );
      return;
    }

    const odontologoId = reprogActiva.odontologoId;
    setReprogActiva((prev) =>
      prev === null
        ? null
        : {
            ...prev,
            fecha,
            slots: [],
            nuevoInicio: "",
            cargandoSlots: true,
            slotError: null,
          },
    );

    try {
      const respuesta = await getDisponibilidad(odontologoId, fecha);
      setReprogActiva((prev) =>
        prev === null
          ? null
          : {
              ...prev,
              slots: respuesta.slots,
              cargandoSlots: false,
              slotError: null,
            },
      );
    } catch (cause: unknown) {
      const publico = cause instanceof PublicApiError ? cause : mapPublicError(cause);
      setReprogActiva((prev) =>
        prev === null
          ? null
          : {
              ...prev,
              slots: [],
              cargandoSlots: false,
              slotError: publico.mensaje,
            },
      );
    }
  }

  async function confirmarReprogramacion(): Promise<void> {
    if (reprogActiva === null || reprogActiva.nuevoInicio === "") {
      return;
    }
    const creds = credencialesDisponibles();
    setOperando(true);
    setAccionError(null);

    try {
      const respuesta = await reprogramarTurnoPublico(
        reprogActiva.turnoId,
        creds.dni,
        creds.token,
        reprogActiva.nuevoInicio,
        nuevaIdempotencyKey(),
      );
      setResultadoReprog(respuesta);
      const nuevoInicio = reprogActiva.nuevoInicio;
      setTurnos((prev) =>
        prev === null
          ? null
          : prev.map((item) =>
              item.id === reprogActiva.turnoId
                ? { ...item, id: respuesta.nuevo.id, inicio: nuevoInicio, estado: respuesta.nuevo.estado }
                : item,
            ),
      );
      setReprogActiva(null);
    } catch (cause: unknown) {
      const publico = cause instanceof PublicApiError ? cause : mapPublicError(cause);
      if (esErrorDeToken(publico)) {
        setErrorConsulta(
          "Tu token ya fue consumido o no es válido. Solicitá un nuevo enlace por correo.",
        );
      } else {
        setAccionError(publico.detail?.trim() || publico.mensaje);
      }
    } finally {
      setOperando(false);
    }
  }

  return (
    <main className="public-page">
      <header className="public-page__header">
        <div>
          <p className="page__kicker">Autogestión del paciente</p>
          <h1>Mis turnos</h1>
        </div>
        <Link to="/reservar" className="button button--quiet">
          Reservar un turno
        </Link>
      </header>

      <section className="wizard-step" aria-labelledby="mis-turnos-form-title">
        <h2 id="mis-turnos-form-title">Ingresá con DNI y token</h2>
        <p className="wizard-step__intro">
          Por privacidad, la consulta exige tu DNI y el token recibido en tu correo. Nunca se
          muestran datos de otros pacientes.
        </p>

        <form onSubmit={onSubmitConsulta} noValidate>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="mis-turnos-dni">DNI</label>
              <input
                id="mis-turnos-dni"
                type="text"
                inputMode="numeric"
                value={dni}
                onChange={(event) => {
                  setDni(event.target.value);
                }}
                placeholder="Ej. 30111222"
              />
            </div>

            <div className="field">
              <label htmlFor="mis-turnos-token">Token de acceso</label>
              <input
                id="mis-turnos-token"
                type="text"
                value={token}
                onChange={(event) => {
                  setToken(event.target.value);
                }}
                placeholder="Pegá el token del correo"
              />
            </div>
          </div>

          {errorConsulta !== null && (
            <p className="feedback feedback--error" role="alert" aria-live="polite">
              {errorConsulta}
            </p>
          )}

          <div className="wizard-actions">
            <button type="submit" className="button button--primary" disabled={cargando}>
              {cargando ? "Consultando..." : "Consultar mis turnos"}
            </button>
          </div>
        </form>
      </section>

      {accionError !== null && (
        <p className="feedback feedback--error" role="alert" aria-live="polite">
          {accionError}
        </p>
      )}

      {resultadoCancelacion !== null && (
        <section className="wizard-step" aria-labelledby="cancelacion-res-title">
          <h2 id="cancelacion-res-title">Turno cancelado</h2>
          <p className="state state--ok">
            El turno quedó en estado <strong>{resultadoCancelacion.estado}</strong>.
          </p>
          {resultadoCancelacion.devolucion !== null ? (
            <dl className="summary">
              <div>
                <dt>Porcentaje de devolución</dt>
                <dd>{resultadoCancelacion.devolucion.porcentaje} %</dd>
              </div>
              <div>
                <dt>Monto de la devolución</dt>
                <dd>
                  {formatearMonto(String(resultadoCancelacion.devolucion.monto))}{" "}
                  <span className="badge-simulado">(simulado)</span>
                </dd>
              </div>
              <div>
                <dt>Estado de devolución</dt>
                <dd>{resultadoCancelacion.devolucion.estado}</dd>
              </div>
            </dl>
          ) : (
            <p className="state state--inline">
              No se generó devolución de seña para esta cancelación.
            </p>
          )}
        </section>
      )}

      {resultadoReprog !== null && (
        <section className="wizard-step" aria-labelledby="reprog-res-title">
          <h2 id="reprog-res-title">Turno reprogramado</h2>
          <p className="state state--ok">
            Turno reprogramado correctamente. El nuevo turno ({resultadoReprog.nuevo.id}) quedó{" "}
            {resultadoReprog.nuevo.estado}.
          </p>
        </section>
      )}

      {turnos !== null && (
        <section className="wizard-step" aria-labelledby="turnos-lista-title">
          <h2 id="turnos-lista-title">Turnos registrados</h2>

          {turnos.length === 0 ? (
            <p className="state">No tenés turnos activos registrados.</p>
          ) : (
            <div className="options">
              {turnos.map((turno) => (
                <article key={turno.id} className="wizard-step">
                  <dl className="summary">
                    <div>
                      <dt>Horario</dt>
                      <dd>{fechaHoraSlot(turno.inicio)}</dd>
                    </div>
                    <div>
                      <dt>Estado</dt>
                      <dd>{turno.estado}</dd>
                    </div>
                  </dl>

                  {turno.estado === "confirmado" && (
                    <div className="wizard-actions">
                      <button
                        type="button"
                        className="button button--quiet"
                        disabled={operando}
                        onClick={() => {
                          void iniciarCancelacion(turno);
                        }}
                      >
                        Cancelar turno
                      </button>
                      <button
                        type="button"
                        className="button button--primary"
                        disabled={operando}
                        onClick={() => {
                          iniciarReprogramacion(turno);
                        }}
                      >
                        Reprogramar
                      </button>
                    </div>
                  )}

                  {cancelacionActiva !== null && cancelacionActiva.turnoId === turno.id && (
                    <div className="wizard-step">
                      <p className="notice">{descripcionPolitica(cancelacionActiva.porcentaje)}</p>
                      <div className="field">
                        <label htmlFor={`motivo-${turno.id}`}>Motivo (opcional)</label>
                        <input
                          id={`motivo-${turno.id}`}
                          type="text"
                          value={cancelacionActiva.motivo}
                          onChange={(event) => {
                            const valor = event.target.value;
                            setCancelacionActiva((prev) =>
                              prev === null ? null : { ...prev, motivo: valor },
                            );
                          }}
                        />
                      </div>
                      <div className="wizard-actions">
                        <button
                          type="button"
                          className="button button--primary"
                          disabled={operando}
                          onClick={() => {
                            void confirmarCancelacion();
                          }}
                        >
                          Confirmar cancelación
                        </button>
                        <button
                          type="button"
                          className="button button--quiet"
                          disabled={operando}
                          onClick={() => {
                            setCancelacionActiva(null);
                          }}
                        >
                          Volver
                        </button>
                      </div>
                    </div>
                  )}

                  {reprogActiva !== null && reprogActiva.turnoId === turno.id && (
                    <div className="wizard-step">
                      <p className="notice">
                        En esta versión, al reprogramar se conserva la seña original sin cargos ni
                        recálculos adicionales (Q3).
                      </p>

                      <div className="field">
                        <label htmlFor={`fecha-reprog-${turno.id}`}>Nueva fecha</label>
                        <input
                          id={`fecha-reprog-${turno.id}`}
                          type="date"
                          min={todayLocal()}
                          value={reprogActiva.fecha}
                          onChange={(event) => {
                            void cargarSlotsReprogramacion(event.target.value);
                          }}
                        />
                      </div>

                      {reprogActiva.cargandoSlots && (
                        <p className="state">Buscando horarios disponibles...</p>
                      )}

                      {reprogActiva.slotError !== null && (
                        <p className="feedback feedback--error" role="alert">
                          {reprogActiva.slotError}
                        </p>
                      )}

                      {!reprogActiva.cargandoSlots &&
                        reprogActiva.fecha !== "" &&
                        !esFechaPasada(reprogActiva.fecha) &&
                        reprogActiva.slots.length === 0 && (
                          <p className="state">No hay horarios disponibles para esa fecha.</p>
                        )}

                      {reprogActiva.slots.length > 0 && (
                        <fieldset className="slot-grid">
                          <legend className="field__label">Horarios disponibles</legend>
                          {reprogActiva.slots.map((slot) => {
                            const deshabilitado = fueraDeAnticipacion(slot.inicio);
                            const elegido = reprogActiva.nuevoInicio === slot.inicio;
                            return (
                              <label
                                key={slot.inicio}
                                className={[
                                  "slot",
                                  elegido ? "slot--selected" : "",
                                  deshabilitado ? "slot--disabled" : "",
                                ]
                                  .filter(Boolean)
                                  .join(" ")}
                              >
                                <input
                                  type="radio"
                                  name={`reprog-slot-${turno.id}`}
                                  value={slot.inicio}
                                  checked={elegido}
                                  disabled={deshabilitado}
                                  onChange={() => {
                                    setReprogActiva((prev) =>
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
                          disabled={operando || reprogActiva.nuevoInicio === ""}
                          onClick={() => {
                            void confirmarReprogramacion();
                          }}
                        >
                          Confirmar reprogramación
                        </button>
                        <button
                          type="button"
                          className="button button--quiet"
                          disabled={operando}
                          onClick={() => {
                            setReprogActiva(null);
                          }}
                        >
                          Cancelar edición
                        </button>
                      </div>
                    </div>
                  )}
                </article>
              ))}
            </div>
          )}
        </section>
      )}
    </main>
  );
}
