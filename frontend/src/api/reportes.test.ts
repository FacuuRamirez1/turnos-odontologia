import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setAccessToken } from "../auth/store";
import { ApiError } from "./errors";
import {
  buildReporteQuery,
  descargarExportacion,
  ESTADOS_ASISTENCIA,
  getAsistencia,
  getCaja,
} from "./reportes";

const OD_ID = "19ceb23b-eacd-4ff6-95d6-94f1548d1b30";
const FILTROS = { desde: "2026-12-01", hasta: "2026-12-31" };

function jsonResp(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const fetchMock = vi.fn<typeof fetch>();

function conteosCompletos(): Record<string, number> {
  return Object.fromEntries(ESTADOS_ASISTENCIA.map((estado) => [estado, 0]));
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  setAccessToken("token-test");
});

afterEach(() => {
  setAccessToken(null);
  vi.unstubAllGlobals();
});

describe("buildReporteQuery", () => {
  it("incluye odontologo_id solo cuando viene informado", () => {
    expect(buildReporteQuery(FILTROS)).toBe("desde=2026-12-01&hasta=2026-12-31");
    expect(buildReporteQuery({ ...FILTROS, odontologoId: OD_ID })).toContain(
      `odontologo_id=${OD_ID}`,
    );
    expect(buildReporteQuery({ ...FILTROS, odontologoId: "" })).not.toContain("odontologo_id");
  });
});

describe("getAsistencia", () => {
  it("envía bearer y devuelve los siete conteos", async () => {
    fetchMock.mockResolvedValue(
      jsonResp({ ...FILTROS, odontologo_id: null, conteos: conteosCompletos() }),
    );

    const res = await getAsistencia(FILTROS);

    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(String(url)).toContain("/api/reportes/asistencia?desde=2026-12-01");
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer token-test");
    expect(Object.keys(res.conteos)).toHaveLength(7);
  });

  it("rechaza con 502 una respuesta con conteos incompletos", async () => {
    fetchMock.mockResolvedValue(
      jsonResp({ ...FILTROS, odontologo_id: null, conteos: { atendido: 1 } }),
    );

    await expect(getAsistencia(FILTROS)).rejects.toMatchObject({ status: 502 });
  });

  it("propaga el envelope de error 422 como ApiError", async () => {
    fetchMock.mockResolvedValue(jsonResp({ detail: "desde debe ser anterior" }, 422));

    await expect(getAsistencia(FILTROS)).rejects.toBeInstanceOf(ApiError);
  });
});

describe("getCaja", () => {
  it("acepta caja vacía con marca", async () => {
    fetchMock.mockResolvedValue(
      jsonResp({
        ...FILTROS,
        odontologo_id: null,
        marca: "(simulado)",
        total_aprobado: "0",
        total_devuelto: "0",
        neto: "0",
        filas: [],
      }),
    );

    const caja = await getCaja(FILTROS);

    expect(caja.marca).toBe("(simulado)");
    expect(caja.filas).toEqual([]);
  });
});

describe("descargarExportacion", () => {
  it("pide el archivo con bearer y devuelve el Blob", async () => {
    fetchMock.mockResolvedValue(new Response("a,b", { status: 200 }));

    const blob = await descargarExportacion("turnos.csv", FILTROS);

    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(String(url)).toContain("/api/reportes/turnos.csv?desde=");
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer token-test");
    expect(blob).toBeInstanceOf(Blob);
    expect(blob.size).toBe(3);
  });
});
