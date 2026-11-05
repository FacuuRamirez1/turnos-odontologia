import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { ApiError, toErrorMessage } from "../../api/errors";
import { useAuth } from "../../auth/AuthProvider";

interface FieldErrors {
  email?: string;
  password?: string;
}

function loginErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return "Credenciales inválidas. Revisá tu email y contraseña.";
    }
    if (error.status === 429) {
      return "Demasiados intentos. Esperá un momento antes de volver a probar.";
    }
    return error.detail;
  }
  return toErrorMessage(error);
}

export function LoginPage(): JSX.Element {
  const { status, login, sessionExpired } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (status === "loading") {
    return (
      <main className="screen-status" role="status">
        Verificando sesión…
      </main>
    );
  }

  if (status === "authenticated") {
    return <Navigate to="/agenda" replace />;
  }

  function validate(): boolean {
    const next: FieldErrors = {};
    if (email.trim() === "") {
      next.email = "Ingresá tu email.";
    }
    if (password === "") {
      next.password = "Ingresá tu contraseña.";
    }
    setFieldErrors(next);
    return Object.keys(next).length === 0;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setSubmitError(null);
    if (!validate()) {
      return;
    }

    setSubmitting(true);
    try {
      await login(email.trim(), password);
      navigate("/agenda", { replace: true });
    } catch (error) {
      setSubmitError(loginErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-screen">
      <section className="login-brand" aria-labelledby="login-brand-title">
        <p className="login-brand__label">Turnos odontología</p>
        <h1 id="login-brand-title">Bitácora clínica</h1>
        <p className="login-brand__text">
          La agenda del consultorio en una sola vista: horarios, estados y ficha del paciente.
        </p>
      </section>

      <section className="login-panel" aria-labelledby="login-title">
        <h2 id="login-title">Ingreso del equipo</h2>
        <p className="login-panel__intro">
          Usá tu cuenta para consultar la agenda del día y registrar la atención.
        </p>

        {sessionExpired && (
          <p className="notice" role="status">
            Tu sesión expiró. Ingresá de nuevo para continuar.
          </p>
        )}

        {submitError !== null && (
          <p className="feedback feedback--error" role="alert" aria-live="polite">
            {submitError}
          </p>
        )}

        <form
          className="login-form"
          onSubmit={(event) => {
            void handleSubmit(event);
          }}
          noValidate
        >
          <div className="field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              aria-invalid={fieldErrors.email !== undefined}
              aria-describedby={fieldErrors.email !== undefined ? "email-error" : undefined}
              disabled={submitting}
              required
            />
            {fieldErrors.email !== undefined && (
              <p id="email-error" className="field__error">
                {fieldErrors.email}
              </p>
            )}
          </div>

          <div className="field">
            <label htmlFor="password">Contraseña</label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              aria-invalid={fieldErrors.password !== undefined}
              aria-describedby={fieldErrors.password !== undefined ? "password-error" : undefined}
              disabled={submitting}
              required
            />
            {fieldErrors.password !== undefined && (
              <p id="password-error" className="field__error">
                {fieldErrors.password}
              </p>
            )}
          </div>

          <button type="submit" className="button button--primary" disabled={submitting}>
            {submitting ? "Ingresando…" : "Ingresar"}
          </button>
        </form>
      </section>
    </main>
  );
}
