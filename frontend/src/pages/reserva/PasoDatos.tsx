import type { DatosPaciente } from "./reservaTypes";

interface PasoDatosProps {
  datos: DatosPaciente;
  error: string | null;
  onCambio: (parcial: Partial<DatosPaciente>) => void;
  onContinuar: () => void;
}

export function PasoDatos({ datos, error, onCambio, onContinuar }: PasoDatosProps): JSX.Element {
  return (
    <section className="wizard-step" aria-labelledby="paso-datos-title">
      <h2 id="paso-datos-title">Tus datos</h2>
      <p className="wizard-step__intro">
        Usamos tus datos solo para gestionar el turno y avisarte por correo.
      </p>

      {error !== null && (
        <p className="feedback feedback--error" role="alert" aria-live="polite">
          {error}
        </p>
      )}

      <div className="form-grid">
        <div className="field">
          <label htmlFor="dni">DNI</label>
          <input
            id="dni"
            name="dni"
            type="text"
            inputMode="numeric"
            autoComplete="off"
            value={datos.dni}
            onChange={(event) => onCambio({ dni: event.target.value })}
            placeholder="30111222"
          />
          <p className="field__hint">7 u 8 dígitos, sin puntos.</p>
        </div>

        <div className="field">
          <label htmlFor="nombre">Nombre</label>
          <input
            id="nombre"
            name="nombre"
            type="text"
            autoComplete="given-name"
            value={datos.nombre}
            onChange={(event) => onCambio({ nombre: event.target.value })}
          />
        </div>

        <div className="field">
          <label htmlFor="apellido">Apellido</label>
          <input
            id="apellido"
            name="apellido"
            type="text"
            autoComplete="family-name"
            value={datos.apellido}
            onChange={(event) => onCambio({ apellido: event.target.value })}
          />
        </div>

        <div className="field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            value={datos.email}
            onChange={(event) => onCambio({ email: event.target.value })}
          />
        </div>

        <div className="field">
          <label htmlFor="telefono">Teléfono</label>
          <input
            id="telefono"
            name="telefono"
            type="tel"
            autoComplete="tel"
            value={datos.telefono}
            onChange={(event) => onCambio({ telefono: event.target.value })}
          />
        </div>
      </div>

      <div className="field field--checkbox">
        <label htmlFor="consentimiento">
          <input
            id="consentimiento"
            name="consentimiento_datos"
            type="checkbox"
            checked={datos.consentimiento_datos}
            onChange={(event) => onCambio({ consentimiento_datos: event.target.checked })}
          />
          <span>Acepto el tratamiento de mis datos personales (obligatorio)</span>
        </label>
        <p className="field__hint">
          Sin este consentimiento no podemos registrar la reserva (RN-CONSENTIMIENTO).
        </p>
      </div>

      <div className="wizard-actions">
        <button type="button" className="button button--primary" onClick={onContinuar}>
          Continuar
        </button>
      </div>
    </section>
  );
}
