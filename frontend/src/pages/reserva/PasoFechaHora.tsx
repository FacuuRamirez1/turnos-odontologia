import type { SlotDisponible } from "../../api/types";
import { todayLocal } from "../../utils/format";
import {
  ANTICIPACION_MIN_HORAS,
  esFechaPasada,
  fechaHoraSlot,
  fueraDeAnticipacion,
} from "./reservaUtils";

interface PasoFechaHoraProps {
  fecha: string;
  slots: SlotDisponible[];
  seleccionado: SlotDisponible | null;
  cargando: boolean;
  error: string | null;
  aviso: string | null;
  onFechaCambio: (fecha: string) => void;
  onSeleccionar: (slot: SlotDisponible) => void;
  onActualizar: () => void;
  onVolver: () => void;
  onContinuar: () => void;
}

export function PasoFechaHora({
  fecha,
  slots,
  seleccionado,
  cargando,
  error,
  aviso,
  onFechaCambio,
  onSeleccionar,
  onActualizar,
  onVolver,
  onContinuar,
}: PasoFechaHoraProps): JSX.Element {
  const fechaPasada = esFechaPasada(fecha);
  const sinFecha = fecha === "";

  return (
    <section className="wizard-step" aria-labelledby="paso-fecha-title">
      <h2 id="paso-fecha-title">Elegí fecha y horario</h2>
      <p className="wizard-step__intro">
        Mostramos solo los huecos libres del profesional elegido.
      </p>

      <div className="filters">
        <div className="field">
          <label htmlFor="fecha">Fecha</label>
          <input
            id="fecha"
            name="fecha"
            type="date"
            min={todayLocal()}
            value={fecha}
            onChange={(event) => onFechaCambio(event.target.value)}
            aria-invalid={fechaPasada}
          />
          <p className="field__hint">
            Las reservas requieren al menos {ANTICIPACION_MIN_HORAS} horas de anticipación.
          </p>
        </div>
        <button
          type="button"
          className="button button--ghost"
          onClick={onActualizar}
          disabled={cargando || sinFecha || fechaPasada}
        >
          Actualizar horarios
        </button>
      </div>

      {fechaPasada && (
        <p className="feedback feedback--error" role="alert" aria-live="polite">
          La fecha ya pasó. Elegí una fecha futura.
        </p>
      )}

      {aviso !== null && (
        <p className="feedback feedback--error" role="alert" aria-live="polite">
          {aviso}
        </p>
      )}

      {sinFecha && !fechaPasada && (
        <p className="state">Elegí una fecha para ver los horarios disponibles.</p>
      )}

      {cargando && (
        <p className="state" role="status">
          Buscando horarios libres…
        </p>
      )}

      {error !== null && (
        <div className="feedback feedback--error" role="alert" aria-live="polite">
          <p>{error}</p>
          <button type="button" className="button button--quiet" onClick={onActualizar}>
            Reintentar
          </button>
        </div>
      )}

      {!cargando && !sinFecha && !fechaPasada && error === null && slots.length === 0 && (
        <p className="state state--warning">
          No hay horarios disponibles para esa fecha. Probá con otro día.
        </p>
      )}

      {slots.length > 0 && (
        <fieldset className="slot-grid">
          <legend className="field__label">Horarios disponibles</legend>
          {slots.map((slot) => {
            const activo = seleccionado?.inicio === slot.inicio;
            const anticipacion = fueraDeAnticipacion(slot.inicio);
            return (
              <label
                key={slot.inicio}
                className={
                  activo ? "slot slot--selected" : anticipacion ? "slot slot--disabled" : "slot"
                }
                title={anticipacion ? `Requiere ${ANTICIPACION_MIN_HORAS} h de anticipación` : undefined}
              >
                <input
                  type="radio"
                  name="slot"
                  value={slot.inicio}
                  checked={activo}
                  onChange={() => onSeleccionar(slot)}
                  disabled={anticipacion}
                />
                <span>{fechaHoraSlot(slot.inicio)}</span>
              </label>
            );
          })}
        </fieldset>
      )}

      <div className="wizard-actions">
        <button type="button" className="button button--quiet" onClick={onVolver}>
          Volver
        </button>
        <button
          type="button"
          className="button button--primary"
          onClick={onContinuar}
          disabled={seleccionado === null || cargando}
        >
          Continuar
        </button>
      </div>
    </section>
  );
}
