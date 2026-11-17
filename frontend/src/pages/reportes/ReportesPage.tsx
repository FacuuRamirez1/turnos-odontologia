import { useCallback, useEffect, useState, type FormEvent } from "react";
import { isAbortError, toErrorMessage } from "../../api/errors";
import {
  descargarExportacion,
  ESTADOS_ASISTENCIA,
  ESTADOS_MAIL,
  getAsistencia,
  getCaja,
  getMailReporte,
  type AsistenciaReporte,
  type CajaReporte,
  type ExportacionReporte,
  type FiltrosReporte,
  type MailReporte,
} from "../../api/reportes";
import { useAuth } from "../../auth/AuthProvider";
import { isIsoDate, isUuid, todayLocal } from "../../utils/format";

const EXPORTACIONES: ReadonlyArray<{ clave: ExportacionReporte; etiqueta: string }> = [
  { clave: "turnos.csv", etiqueta: "Turnos CSV" },
  { clave: "turnos.pdf", etiqueta: "Turnos PDF" },
  { clave: "caja.csv", etiqueta: "Caja CSV" },
  { clave: "caja.pdf", etiqueta: "Caja PDF" },
  { clave: "auditoria.csv", etiqueta: "Auditoría CSV" },
];

function primerDiaDelMes(): string {
  return `${todayLocal().slice(0, 8)}01`;
}

function validarFiltros(desde: string, hasta: string, profesional: string): string | null {
  if (!isIsoDate(desde) || !isIsoDate(hasta)) {
    return "Ingresá un período válido.";
  }
  if (desde > hasta) {
    return "La fecha desde no puede ser posterior a la fecha hasta.";
  }
  if (profesional !== "" && !isUuid(profesional)) {
    return "El profesional debe ser un UUID válido.";
  }
  return null;
}

function guardarArchivo(blob: Blob, nombre: string): void {
  const url = URL.createObjectURL(blob);
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = nombre;
  enlace.click();
  URL.revokeObjectURL(url);
}

interface Resultado {
  asistencia: AsistenciaReporte;
  caja: CajaReporte;
  mail: MailReporte;
}

export function ReportesPage(): JSX.Element {
  const { user } = useAuth();
  const esOdontologo = user?.rol === "odontologo";
  const [desde, setDesde] = useState(primerDiaDelMes());
  const [hasta, setHasta] = useState(todayLocal());
  const [profesional, setProfesional] = useState("");
  const [consulta, setConsulta] = useState<FiltrosReporte | null>(null);
  const [resultado, setResultado] = useState<Resultado | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [descargando, setDescargando] = useState<ExportacionReporte | null>(null);

  const construirFiltros = useCallback((): FiltrosReporte => {
    const filtros: FiltrosReporte = { desde, hasta };
    if (!esOdontologo && profesional !== "") {
      filtros.odontologoId = profesional;
    }
    return filtros;
  }, [desde, hasta, profesional, esOdontologo]);

  const consultar = useCallback(
    (filtros: FiltrosReporte) => {
      setConsulta(filtros);
    },
    [],
  );

  // Consulta inicial al montar (el período por defecto es el mes en curso).
  useEffect(() => {
    consultar({ desde: primerDiaDelMes(), hasta: todayLocal() });
  }, [consultar]);

  useEffect(() => {
    if (consulta === null) {
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    Promise.all([
      getAsistencia(consulta, controller.signal),
      getCaja(consulta, controller.signal),
      getMailReporte(consulta, controller.signal),
    ])
      .then(([asistencia, caja, mail]) => {
        setResultado({ asistencia, caja, mail });
      })
      .catch((err: unknown) => {
        if (!isAbortError(err)) {
          setError(toErrorMessage(err));
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });
    return () => {
      controller.abort();
    };
  }, [consulta]);

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const invalido = validarFiltros(desde, hasta, esOdontologo ? "" : profesional);
    if (invalido !== null) {
      setError(invalido);
      return;
    }
    // Nuevo objeto cada vez: reintentar relanza la consulta aunque no cambien los valores.
    consultar(construirFiltros());
  }

  async function handleDescarga(clave: ExportacionReporte): Promise<void> {
    setDescargando(clave);
    setError(null);
    try {
      const blob = await descargarExportacion(clave, construirFiltros());
      guardarArchivo(blob, clave);
    } catch (err: unknown) {
      setError(toErrorMessage(err));
    } finally {
      setDescargando(null);
    }
  }

  return (
    <section className="wizard-step" aria-labelledby="reportes-title">
      <h2 id="reportes-title">Reportes y exportaciones</h2>

      <form onSubmit={handleSubmit} className="wizard-actions">
        <div className="field">
          <label htmlFor="rep-desde">Desde</label>
          <input
            id="rep-desde"
            type="date"
            value={desde}
            onChange={(e) => {
              setDesde(e.target.value);
            }}
          />
        </div>
        <div className="field">
          <label htmlFor="rep-hasta">Hasta</label>
          <input
            id="rep-hasta"
            type="date"
            value={hasta}
            onChange={(e) => {
              setHasta(e.target.value);
            }}
          />
        </div>
        {!esOdontologo && (
          <div className="field">
            <label htmlFor="rep-prof">Profesional (UUID)</label>
            <input
              id="rep-prof"
              type="text"
              value={profesional}
              placeholder="Todos"
              onChange={(e) => {
                setProfesional(e.target.value.trim());
              }}
            />
          </div>
        )}
        <button type="submit" className="button button--primary" disabled={loading}>
          Consultar
        </button>
      </form>

      {error !== null && (
        <div className="feedback feedback--error" role="alert" aria-live="polite">
          <p>{error}</p>
          <button
            type="button"
            className="button button--quiet"
            onClick={() => {
              consultar(construirFiltros());
            }}
          >
            Reintentar
          </button>
        </div>
      )}

      {loading && <p aria-live="polite">Cargando reportes…</p>}

      {resultado !== null && (
        <>
          <section aria-labelledby="rep-asistencia-title">
            <h3 id="rep-asistencia-title">Asistencia por estado</h3>
            <table>
              <thead>
                <tr>
                  <th scope="col">Estado</th>
                  <th scope="col">Turnos</th>
                </tr>
              </thead>
              <tbody>
                {ESTADOS_ASISTENCIA.map((estado) => (
                  <tr key={estado}>
                    <th scope="row">{estado}</th>
                    <td data-testid={`conteo-${estado}`}>{resultado.asistencia.conteos[estado]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section aria-labelledby="rep-caja-title">
            <h3 id="rep-caja-title">
              Caja{" "}
              {resultado.caja.marca !== "" && (
                <span className="badge-simulado">{resultado.caja.marca}</span>
              )}
            </h3>
            <p>Aprobado: {resultado.caja.total_aprobado}</p>
            <p>Devuelto: {resultado.caja.total_devuelto}</p>
            <p>Neto: {resultado.caja.neto}</p>
          </section>

          <section aria-labelledby="rep-mail-title">
            <h3 id="rep-mail-title">Entrega de mails</h3>
            <ul>
              {ESTADOS_MAIL.map((estado) => (
                <li key={estado}>
                  {estado}: <span data-testid={`mail-${estado}`}>{resultado.mail.conteos[estado]}</span>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}

      <section aria-labelledby="rep-export-title">
        <h3 id="rep-export-title">Exportaciones</h3>
        <div className="wizard-actions">
          {EXPORTACIONES.map(({ clave, etiqueta }) => (
            <button
              key={clave}
              type="button"
              className="button button--quiet"
              disabled={descargando !== null}
              onClick={() => {
                void handleDescarga(clave);
              }}
            >
              {descargando === clave ? "Descargando…" : etiqueta}
            </button>
          ))}
        </div>
      </section>
    </section>
  );
}
