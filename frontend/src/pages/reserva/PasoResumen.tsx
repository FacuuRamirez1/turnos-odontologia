import type { PrecioOdontologoPublico, SlotDisponible } from "../../api/types";
import type { DatosPaciente } from "./reservaTypes";
import { fechaHoraSlot, formatearMonto } from "./reservaUtils";

interface PasoResumenProps {
  datos: DatosPaciente;
  profesional: PrecioOdontologoPublico;
  slot: SlotDisponible;
  marca: string;
  enviando: boolean;
  error: string | null;
  onVolver: () => void;
  onConfirmar: () => void;
}

export function PasoResumen({
  datos,
  profesional,
  slot,
  marca,
  enviando,
  error,
  onVolver,
  onConfirmar,
}: PasoResumenProps): JSX.Element {
  return (
    <section className="wizard-step" aria-labelledby="paso-resumen-title">
      <h2 id="paso-resumen-title">Revisá y confirmá</h2>
      <p className="wizard-step__intro">
        Al confirmar se crea una pre-reserva por 15 minutos. Sin el pago de la seña el
        turno no queda confirmado.
      </p>

      {error !== null && (
        <p className="feedback feedback--error" role="alert" aria-live="polite">
          {error}
        </p>
      )}

      <dl className="summary">
        <div>
          <dt>Paciente</dt>
          <dd>
            {datos.nombre} {datos.apellido}
          </dd>
        </div>
        <div>
          <dt>DNI</dt>
          <dd className="mono">{datos.dni}</dd>
        </div>
        <div>
          <dt>Contacto</dt>
          <dd>{datos.email === "" ? "Sin email informado" : datos.email}</dd>
        </div>
        <div>
          <dt>Profesional</dt>
          <dd>Profesional {profesional.odontologo_id.slice(0, 8)}</dd>
        </div>
        <div>
          <dt>Fecha y hora</dt>
          <dd>{fechaHoraSlot(slot.inicio)}</dd>
        </div>
        <div>
          <dt>Monto del turno</dt>
          <dd>{formatearMonto(profesional.monto_turno)}</dd>
        </div>
        <div>
          <dt>
            Seña a abonar
            {marca !== "" && <span className="badge-simulado">{marca}</span>}
          </dt>
          <dd>{formatearMonto(profesional.monto_senia)}</dd>
        </div>
      </dl>

      <p className="field__hint">
        Si no se aprueba el pago de la seña, el horario se libera automáticamente
        (RN-LIBERACION).
      </p>

      <div className="wizard-actions">
        <button type="button" className="button button--quiet" onClick={onVolver} disabled={enviando}>
          Volver
        </button>
        <button
          type="button"
          className="button button--primary"
          onClick={onConfirmar}
          disabled={enviando}
        >
          {enviando ? "Creando reserva…" : "Confirmar reserva"}
        </button>
      </div>
    </section>
  );
}
