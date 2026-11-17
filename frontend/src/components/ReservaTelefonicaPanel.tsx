import { type FormEvent, useEffect, useState } from "react";
import { crearReservaTelefonica } from "../api/backoffice";
import { toErrorMessage } from "../api/errors";
import {
  dniValido,
  normalizarDni,
  nuevaIdempotencyKey,
} from "../pages/reserva/reservaUtils";
import { isUuid } from "../utils/format";

interface ReservaTelefonicaPanelProps {
  odontologoId: string;
  rol: string;
  onCreated: (fechaTurno: string) => void;
}

export function ReservaTelefonicaPanel({
  odontologoId,
  rol,
  onCreated,
}: ReservaTelefonicaPanelProps): JSX.Element {
  const [profesionalId, setProfesionalId] = useState(odontologoId);
  const [fechaHora, setFechaHora] = useState("");
  const [dni, setDni] = useState("");
  const [nombre, setNombre] = useState("");
  const [apellido, setApellido] = useState("");
  const [email, setEmail] = useState("");
  const [telefono, setTelefono] = useState("");
  const [consentimiento, setConsentimiento] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exito, setExito] = useState<string | null>(null);

  useEffect(() => {
    if (odontologoId.trim() !== "") {
      setProfesionalId(odontologoId);
    }
  }, [odontologoId]);

  if (rol !== "recepcionista" && rol !== "admin") {
    return (
      <section className="wizard-step" aria-labelledby="tel-bloqueo-title">
        <h2 id="tel-bloqueo-title">Reserva telefónica</h2>
        <p className="notice">
          Solo recepción o administración pueden registrar reservas telefónicas (Q10).
        </p>
      </section>
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError(null);
    setExito(null);

    const odLimpio = profesionalId.trim();
    if (!isUuid(odLimpio)) {
      setError("Ingresá un UUID válido de profesional.");
      return;
    }
    if (fechaHora.trim() === "") {
      setError("Ingresá la fecha y hora futura del turno.");
      return;
    }
    const fechaParsed = new Date(fechaHora);
    if (Number.isNaN(fechaParsed.getTime()) || fechaParsed.getTime() <= Date.now()) {
      setError("La fecha y hora del turno debe ser futura (RN-PASADO).");
      return;
    }
    const dniLimpio = normalizarDni(dni);
    if (!dniValido(dniLimpio)) {
      setError("Ingresá un DNI numérico válido (7 u 8 dígitos).");
      return;
    }
    if (nombre.trim() === "" || apellido.trim() === "" || email.trim() === "") {
      setError("Completá nombre, apellido y email del paciente.");
      return;
    }
    if (!consentimiento) {
      setError("El consentimiento informado del paciente es obligatorio antes de registrar (P11).");
      return;
    }

    setEnviando(true);
    try {
      const creada = await crearReservaTelefonica(
        {
          odontologo_id: odLimpio,
          inicio: fechaParsed.toISOString(),
          dni: dniLimpio,
          nombre: nombre.trim(),
          apellido: apellido.trim(),
          email: email.trim(),
          telefono: telefono.trim() === "" ? null : telefono.trim(),
          consentimiento_datos: true,
        },
        nuevaIdempotencyKey(),
      );
      setExito(`Reserva telefónica creada (turno ${creada.id}, canal ${creada.canal}).`);
      setDni("");
      setNombre("");
      setApellido("");
      setEmail("");
      setTelefono("");
      setConsentimiento(false);
      onCreated(fechaHora.slice(0, 10));
    } catch (cause: unknown) {
      setError(toErrorMessage(cause));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section className="wizard-step" aria-labelledby="tel-form-title">
      <h2 id="tel-form-title">Reserva telefónica (Q10)</h2>
      <p className="wizard-step__intro">
        Carga asistida por recepción con datos mínimos verificables (DNI, email y consentimiento
        informado).
      </p>

      <form onSubmit={(event) => void handleSubmit(event)} noValidate>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="tel-od">UUID profesional</label>
            <input
              id="tel-od"
              type="text"
              value={profesionalId}
              onChange={(event) => setProfesionalId(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="tel-fecha-hora">Fecha y hora del turno</label>
            <input
              id="tel-fecha-hora"
              type="datetime-local"
              value={fechaHora}
              onChange={(event) => setFechaHora(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="tel-dni">DNI del paciente</label>
            <input
              id="tel-dni"
              type="text"
              inputMode="numeric"
              value={dni}
              onChange={(event) => setDni(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="tel-nombre">Nombre del paciente</label>
            <input
              id="tel-nombre"
              type="text"
              value={nombre}
              onChange={(event) => setNombre(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="tel-apellido">Apellido del paciente</label>
            <input
              id="tel-apellido"
              type="text"
              value={apellido}
              onChange={(event) => setApellido(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="tel-email">Email del paciente</label>
            <input
              id="tel-email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="tel-telefono">Teléfono del paciente (opcional)</label>
            <input
              id="tel-telefono"
              type="text"
              value={telefono}
              onChange={(event) => setTelefono(event.target.value)}
            />
          </div>
        </div>

        <div className="field field--checkbox">
          <label htmlFor="tel-consent">
            <input
              id="tel-consent"
              type="checkbox"
              checked={consentimiento}
              onChange={(event) => setConsentimiento(event.target.checked)}
            />
            <span>
              El paciente otorgó consentimiento informado para el tratamiento de datos clínicos
              (P11).
            </span>
          </label>
        </div>

        {error !== null && (
          <p className="feedback feedback--error" role="alert" aria-live="polite">
            {error}
          </p>
        )}

        {exito !== null && <p className="state state--ok">{exito}</p>}

        <div className="wizard-actions">
          <button type="submit" className="button button--primary" disabled={enviando}>
            {enviando ? "Registrando…" : "Registrar reserva telefónica"}
          </button>
        </div>
      </form>
    </section>
  );
}
