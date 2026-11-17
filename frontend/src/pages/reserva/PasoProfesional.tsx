import type { PrecioOdontologoPublico, PreciosPublicos } from "../../api/types";
import { formatearMonto } from "./reservaUtils";

interface PasoProfesionalProps {
  precios: PreciosPublicos | null;
  seleccionado: PrecioOdontologoPublico | null;
  cargando: boolean;
  error: string | null;
  onSeleccionar: (precio: PrecioOdontologoPublico) => void;
  onReintentar: () => void;
  onVolver: () => void;
  onContinuar: () => void;
}

export function PasoProfesional({
  precios,
  seleccionado,
  cargando,
  error,
  onSeleccionar,
  onReintentar,
  onVolver,
  onContinuar,
}: PasoProfesionalProps): JSX.Element {
  const marca = precios?.marca ?? "";

  return (
    <section className="wizard-step" aria-labelledby="paso-profesional-title">
      <h2 id="paso-profesional-title">Elegí profesional</h2>
      <p className="wizard-step__intro">
        Los montos los define cada profesional. La seña se abona al confirmar.
      </p>

      {cargando && (
        <p className="state" role="status">
          Cargando aranceles…
        </p>
      )}

      {error !== null && (
        <div className="feedback feedback--error" role="alert" aria-live="polite">
          <p>{error}</p>
          <button type="button" className="button button--quiet" onClick={onReintentar}>
            Reintentar
          </button>
        </div>
      )}

      {precios !== null && precios.odontologos.length === 0 && (
        <p className="state state--warning">
          No hay profesionales activos para reservar en este momento.
        </p>
      )}

      {precios !== null && precios.odontologos.length > 0 && (
        <fieldset className="options">
          <legend className="field__label">Profesionales disponibles</legend>
          {precios.odontologos.map((precio) => {
            const activo = seleccionado?.odontologo_id === precio.odontologo_id;
            return (
              <label key={precio.odontologo_id} className={activo ? "option option--selected" : "option"}>
                <input
                  type="radio"
                  name="profesional"
                  value={precio.odontologo_id}
                  checked={activo}
                  onChange={() => onSeleccionar(precio)}
                />
                <span className="option__body">
                  <span className="option__title">
                    Profesional {precio.odontologo_id.slice(0, 8)}
                    {marca !== "" && <span className="badge-simulado">{marca}</span>}
                  </span>
                  <span className="option__meta">
                    Turno {formatearMonto(precio.monto_turno)} · Seña{" "}
                    {formatearMonto(precio.monto_senia)}
                  </span>
                </span>
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
          disabled={seleccionado === null}
        >
          Continuar
        </button>
      </div>
    </section>
  );
}
