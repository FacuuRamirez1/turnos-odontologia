import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { isAbortError, mapPublicError, PublicApiError, toPublicErrorMessage } from "../../api/errors";
import { crearReserva, getDisponibilidad, getPrecios } from "../../api/public";
import type {
  PrecioOdontologoPublico,
  PreciosPublicos,
  ReservaPublica,
  SlotDisponible,
} from "../../api/types";
import { PasoDatos } from "./PasoDatos";
import { PasoFechaHora } from "./PasoFechaHora";
import { PasoProfesional } from "./PasoProfesional";
import { PasoResumen } from "./PasoResumen";
import {
  DATOS_PACIENTE_INICIALES,
  PASOS_RESERVA,
  type DatosPaciente,
  type PasoReserva,
} from "./reservaTypes";
import { dniValido, esFechaPasada, fechaHoraSlot, nuevaIdempotencyKey } from "./reservaUtils";

export function ReservaPage(): JSX.Element {
  const navigate = useNavigate();

  const [paso, setPaso] = useState<PasoReserva>(1);
  const [datos, setDatos] = useState<DatosPaciente>(DATOS_PACIENTE_INICIALES);
  const [datosError, setDatosError] = useState<string | null>(null);

  const [precios, setPrecios] = useState<PreciosPublicos | null>(null);
  const [cargandoPrecios, setCargandoPrecios] = useState(false);
  const [preciosError, setPreciosError] = useState<string | null>(null);
  const [recargaPrecios, setRecargaPrecios] = useState(0);
  const [profesional, setProfesional] = useState<PrecioOdontologoPublico | null>(null);

  const [fecha, setFecha] = useState("");
  const [slots, setSlots] = useState<SlotDisponible[]>([]);
  const [slot, setSlot] = useState<SlotDisponible | null>(null);
  const [cargandoSlots, setCargandoSlots] = useState(false);
  const [slotsError, setSlotsError] = useState<string | null>(null);
  const [recargaSlots, setRecargaSlots] = useState(0);

  const [idempotencyKey, setIdempotencyKey] = useState<string>(() => nuevaIdempotencyKey());
  const [enviando, setEnviando] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [reserva, setReserva] = useState<ReservaPublica | null>(null);

  useEffect(() => {
    if (paso !== 2 || precios !== null) {
      return;
    }
    const controller = new AbortController();
    setCargandoPrecios(true);
    setPreciosError(null);

    getPrecios(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          setPrecios(data);
        }
      })
      .catch((cause: unknown) => {
        if (!isAbortError(cause) && !controller.signal.aborted) {
          setPreciosError(toPublicErrorMessage(cause));
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setCargandoPrecios(false);
        }
      });

    return () => controller.abort();
  }, [paso, precios, recargaPrecios]);

  useEffect(() => {
    if (paso !== 3 || profesional === null || fecha === "" || esFechaPasada(fecha)) {
      return;
    }
    const controller = new AbortController();
    setCargandoSlots(true);
    setSlotsError(null);

    getDisponibilidad(profesional.odontologo_id, fecha, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) {
          return;
        }
        setSlots(data.slots);
        setSlot((actual) =>
          actual !== null && data.slots.some((libre) => libre.inicio === actual.inicio)
            ? actual
            : null,
        );
      })
      .catch((cause: unknown) => {
        if (!isAbortError(cause) && !controller.signal.aborted) {
          setSlots([]);
          setSlotsError(toPublicErrorMessage(cause));
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setCargandoSlots(false);
        }
      });

    return () => controller.abort();
  }, [paso, profesional, fecha, recargaSlots]);

  function cambiarDatos(parcial: Partial<DatosPaciente>): void {
    setDatos((previos) => ({ ...previos, ...parcial }));
    setDatosError(null);
  }

  function continuarDesdeDatos(): void {
    const faltantes: string[] = [];
    if (!dniValido(datos.dni)) {
      faltantes.push("un DNI válido de 7 u 8 dígitos");
    }
    if (datos.nombre.trim() === "") {
      faltantes.push("tu nombre");
    }
    if (datos.apellido.trim() === "") {
      faltantes.push("tu apellido");
    }
    if (!datos.consentimiento_datos) {
      setDatosError(
        "Para continuar necesitamos tu consentimiento para el tratamiento de datos personales.",
      );
      return;
    }
    if (faltantes.length > 0) {
      setDatosError(`Completá ${faltantes.join(", ")} para continuar.`);
      return;
    }
    setDatosError(null);
    setPaso(2);
  }

  function seleccionarProfesional(precio: PrecioOdontologoPublico): void {
    setProfesional(precio);
    setSlots([]);
    setSlot(null);
    setIdempotencyKey(nuevaIdempotencyKey());
  }

  function cambiarFecha(nueva: string): void {
    setFecha(nueva);
    setSlots([]);
    setSlot(null);
    setSlotsError(null);
    setConfirmError(null);
  }

  function seleccionarSlot(elegido: SlotDisponible): void {
    setSlot(elegido);
    setConfirmError(null);
    setIdempotencyKey(nuevaIdempotencyKey());
  }

  function reintentarPrecios(): void {
    setPrecios(null);
    setPreciosError(null);
    setRecargaPrecios((valor) => valor + 1);
  }

  function actualizarSlots(): void {
    setRecargaSlots((valor) => valor + 1);
  }

  async function confirmarReserva(): Promise<void> {
    if (profesional === null || slot === null) {
      return;
    }
    setEnviando(true);
    setConfirmError(null);

    try {
      const respuesta = await crearReserva(
        {
          odontologo_id: profesional.odontologo_id,
          inicio: slot.inicio,
          dni: datos.dni.replace(/[\s.-]/g, ""),
          nombre: datos.nombre.trim(),
          apellido: datos.apellido.trim(),
          email: datos.email.trim() === "" ? null : datos.email.trim(),
          telefono: datos.telefono.trim() === "" ? null : datos.telefono.trim(),
          consentimiento_datos: true,
        },
        idempotencyKey,
      );

      if (respuesta.pago_id !== null && respuesta.checkout_token !== null) {
        const params = new URLSearchParams({
          pago_id: respuesta.pago_id,
          token: respuesta.checkout_token,
          monto_senia: profesional.monto_senia,
        });
        navigate(`/checkout-simulado?${params.toString()}`);
        return;
      }

      setReserva(respuesta);
    } catch (cause: unknown) {
      const publico = cause instanceof PublicApiError ? cause : mapPublicError(cause);
      if (publico.kind === "conflicto") {
        setPaso(3);
        setSlot(null);
        setRecargaSlots((valor) => valor + 1);
      }
      setConfirmError(publico.mensaje);
    } finally {
      setEnviando(false);
    }
  }

  const marca = precios?.marca ?? "";

  if (reserva !== null) {
    return (
      <main className="public-page">
        <section className="wizard-step" aria-labelledby="reserva-ok-title">
          <h2 id="reserva-ok-title">Turno reservado</h2>
          <p className="wizard-step__intro">
            Registramos tu turno para el {fechaHoraSlot(reserva.inicio)}.
          </p>
          <p className="state state--inline">
            No se requiere seña para este turno. Te esperamos.
          </p>
          <dl className="summary">
            <div>
              <dt>Estado</dt>
              <dd>{reserva.estado}</dd>
            </div>
            <div>
              <dt>Identificador</dt>
              <dd className="mono">{reserva.id}</dd>
            </div>
          </dl>
        </section>
      </main>
    );
  }

  return (
    <main className="public-page">
      <header className="public-page__header">
        <p className="page__kicker">Reserva de turnos</p>
        <h1>Reservá tu turno</h1>
        <p className="page__meta">
          Consultorio único · Hora local · Pagos simulados {marca}
        </p>
      </header>

      <ol className="wizard-progress">
        {PASOS_RESERVA.map(({ paso: numero, etiqueta }) => (
          <li
            key={numero}
            aria-current={paso === numero ? "step" : undefined}
            className={
              paso === numero
                ? "wizard-progress__item wizard-progress__item--actual"
                : paso > numero
                  ? "wizard-progress__item wizard-progress__item--hecho"
                  : "wizard-progress__item"
            }
          >
            <span className="wizard-progress__numero">{numero}</span>
            {etiqueta}
          </li>
        ))}
      </ol>

      {paso === 1 && (
        <PasoDatos
          datos={datos}
          error={datosError}
          onCambio={cambiarDatos}
          onContinuar={continuarDesdeDatos}
        />
      )}

      {paso === 2 && (
        <PasoProfesional
          precios={precios}
          seleccionado={profesional}
          cargando={cargandoPrecios}
          error={preciosError}
          onSeleccionar={seleccionarProfesional}
          onReintentar={reintentarPrecios}
          onVolver={() => setPaso(1)}
          onContinuar={() => setPaso(3)}
        />
      )}

      {paso === 3 && (
        <PasoFechaHora
          fecha={fecha}
          slots={slots}
          seleccionado={slot}
          cargando={cargandoSlots}
          error={slotsError}
          aviso={confirmError}
          onFechaCambio={cambiarFecha}
          onSeleccionar={seleccionarSlot}
          onActualizar={actualizarSlots}
          onVolver={() => setPaso(2)}
          onContinuar={() => setPaso(4)}
        />
      )}

      {paso === 4 && profesional !== null && slot !== null && (
        <PasoResumen
          datos={datos}
          profesional={profesional}
          slot={slot}
          marca={marca}
          enviando={enviando}
          error={confirmError}
          onVolver={() => setPaso(3)}
          onConfirmar={() => {
            void confirmarReserva();
          }}
        />
      )}
    </main>
  );
}
