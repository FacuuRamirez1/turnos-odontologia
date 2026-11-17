import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PublicApiError } from "./errors";
import {
  cancelarDesdeMail,
  cancelarTurnoPublico,
  confirmarDesdeMail,
  cotizarCancelacionPublica,
  crearReserva,
  getDisponibilidad,
  getMisTurnos,
  getPrecios,
  reprogramarTurnoPublico,
  simularPago,
} from "./public";
import type { ReservaPublicaRequest } from "./types";

const ODONTOLOGO_ID = "19ceb23b-eacd-4ff6-95d6-94f1548d1b30";
const PAGO_ID = "0b6f9a2e-6d7a-4f3e-9a8e-2f1c4a5b6d7e";

function respuesta(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const fetchMock = vi.fn<typeof fetch>();

function ultimaLlamada(): { url: string; init: RequestInit } {
  const llamada = fetchMock.mock.calls[fetchMock.mock.calls.length - 1];
  if (llamada === undefined) {
    throw new Error("fetch no fue invocado");
  }
  const [url, init] = llamada;
  return { url: String(url), init: init ?? {} };
}

function headersDe(init: RequestInit): Record<string, string> {
  return (init.headers ?? {}) as Record<string, string>;
}

const preciosPayload = {
  odontologos: [
    { odontologo_id: ODONTOLOGO_ID, monto_turno: "70000.00", monto_senia: "65000.50" },
  ],
  trial: { disponible: true, requiere_tarjeta: false, dias: null },
  marca: "(simulado)",
};

const reservaPayload = {
  id: "turno-1",
  paciente_id: "paciente-1",
  odontologo_id: ODONTOLOGO_ID,
  inicio: "2030-05-20T13:00:00+00:00",
  fin: "2030-05-20T13:30:00+00:00",
  estado: "creado",
  canal: "web",
  pago_id: PAGO_ID,
  checkout_url: `http://localhost:5173/checkout-simulado?pago_id=${PAGO_ID}&token=chk_abc`,
  checkout_token: "chk_abc",
};

describe("cliente API público", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("serializa GET /api/precios sin credenciales y con montos como texto", async () => {
    fetchMock.mockResolvedValue(respuesta(preciosPayload));

    const precios = await getPrecios();

    const { url, init } = ultimaLlamada();
    expect(url).toBe("/api/precios");
    expect(init.method).toBe("GET");
    expect(headersDe(init).Authorization).toBeUndefined();
    expect(headersDe(init).Accept).toBe("application/json");
    expect(precios.odontologos[0]?.monto_turno).toBe("70000.00");
    expect(precios.odontologos[0]?.monto_senia).toBe("65000.50");
    expect(precios.marca).toBe("(simulado)");
  });

  it("serializa POST /api/reservas con Idempotency-Key y cuerpo JSON", async () => {
    fetchMock.mockResolvedValue(respuesta(reservaPayload, 201));
    const cuerpo: ReservaPublicaRequest = {
      odontologo_id: ODONTOLOGO_ID,
      inicio: "2030-05-20T13:00:00+00:00",
      dni: "30111222",
      nombre: "Ana",
      apellido: "Ficticia",
      email: "ana@ficticia.example.ar",
      telefono: null,
      consentimiento_datos: true,
    };

    const reserva = await crearReserva(cuerpo, "idem-prueba-1");

    const { url, init } = ultimaLlamada();
    expect(url).toBe("/api/reservas");
    expect(init.method).toBe("POST");
    expect(headersDe(init)["Idempotency-Key"]).toBe("idem-prueba-1");
    expect(headersDe(init)["Content-Type"]).toBe("application/json");
    expect(JSON.parse(String(init.body))).toEqual(cuerpo);
    expect(reserva.pago_id).toBe(PAGO_ID);
    expect(reserva.checkout_token).toBe("chk_abc");
  });

  it("consulta disponibilidad con query acotada", async () => {
    fetchMock.mockResolvedValue(
      respuesta({ slots: [{ inicio: "2030-05-20T13:00:00+00:00", fin: "2030-05-20T13:30:00+00:00" }] }),
    );

    const disponibilidad = await getDisponibilidad(ODONTOLOGO_ID, "2030-05-20");

    expect(ultimaLlamada().url).toBe(
      `/api/disponibilidad?odontologo_id=${ODONTOLOGO_ID}&fecha=2030-05-20`,
    );
    expect(disponibilidad.slots).toHaveLength(1);
  });

  it("envía checkout_token como cabecera al sandbox y acción en el cuerpo", async () => {
    fetchMock.mockResolvedValue(
      respuesta({
        pago_id: PAGO_ID,
        estado_pago: "aprobado",
        turno_id: "turno-1",
        estado_turno: "confirmado",
        transicionado: true,
        idempotente: false,
        proveedor: "simulado",
        marca: "(simulado)",
      }),
    );

    const resultado = await simularPago(PAGO_ID, "aprobar", "chk_abc");

    const { url, init } = ultimaLlamada();
    expect(url).toBe(`/api/pagos/${PAGO_ID}/simular`);
    expect(init.method).toBe("POST");
    expect(headersDe(init).checkout_token).toBe("chk_abc");
    expect(JSON.parse(String(init.body))).toEqual({ accion: "aprobar" });
    expect(resultado.estado_pago).toBe("aprobado");
    expect(resultado.estado_turno).toBe("confirmado");
  });

  it("lee los turnos propios con dni + token", async () => {
    fetchMock.mockResolvedValueOnce(
      respuesta([
        {
          id: "turno-1",
          odontologo_id: ODONTOLOGO_ID,
          inicio: "2030-05-20T13:00:00+00:00",
          fin: "2030-05-20T13:30:00+00:00",
          estado: "confirmado",
        },
      ]),
    );

    const turnos = await getMisTurnos("30111222", "tok-accion");

    expect(turnos[0]?.id).toBe("turno-1");
    const { url } = ultimaLlamada();
    expect(url).toBe("/api/mis-turnos?dni=30111222&token=tok-accion");
  });

  it("cotiza, cancela y reprograma un turno propio con dni y token", async () => {
    fetchMock
      .mockResolvedValueOnce(respuesta({ porcentaje: 60 }))
      .mockResolvedValueOnce(
        respuesta({
          id: "turno-1",
          estado: "cancelado",
          devolucion: {
            id: "dev-1",
            porcentaje: 60,
            monto: 39000.3,
            estado: "pendiente",
          },
        }),
      )
      .mockResolvedValueOnce(
        respuesta({
          origen: { id: "turno-1", estado: "reprogramado" },
          nuevo: {
            id: "turno-2",
            estado: "confirmado",
            pago_id: PAGO_ID,
            reprogramado_de_id: "turno-1",
          },
        }),
      );

    const cotizacion = await cotizarCancelacionPublica("turno-1", "30111222", "tok-1");
    expect(cotizacion.porcentaje).toBe(60);
    expect(ultimaLlamada().url).toBe(
      "/api/reservas/turno-1/cotizar-cancelacion?dni=30111222&token=tok-1",
    );

    const cancelacion = await cancelarTurnoPublico("turno-1", "30111222", "tok-1", "Viaje");
    expect(cancelacion.estado).toBe("cancelado");
    expect(cancelacion.devolucion?.porcentaje).toBe(60);
    expect(ultimaLlamada().url).toBe("/api/reservas/turno-1/cancelar?dni=30111222&token=tok-1");
    expect(JSON.parse(String(ultimaLlamada().init.body))).toEqual({ motivo: "Viaje" });

    const reprog = await reprogramarTurnoPublico(
      "turno-1",
      "30111222",
      "tok-1",
      "2030-05-25T15:00:00+00:00",
      "idem-reprog-1",
    );
    expect(reprog.origen.estado).toBe("reprogramado");
    expect(reprog.nuevo.id).toBe("turno-2");
    expect(ultimaLlamada().url).toBe("/api/reservas/turno-1/reprogramar?dni=30111222&token=tok-1");
    expect(headersDe(ultimaLlamada().init)["Idempotency-Key"]).toBe("idem-reprog-1");
  });

  it("consume acciones de mail con Accept JSON", async () => {
    fetchMock.mockResolvedValueOnce(
      respuesta({
        ok: true,
        accion: "confirmar",
        estado: "confirmado_desde_mail",
        turno_id: "turno-1",
      }),
    );
    fetchMock.mockResolvedValueOnce(
      respuesta({
        ok: true,
        accion: "cancelar",
        estado: "cancelado",
        turno_id: "turno-1",
        porcentaje: 100,
        devolucion: null,
        marca: "(simulado)",
      }),
    );

    const confirmacion = await confirmarDesdeMail("tok-mail");
    const cancelacion = await cancelarDesdeMail("tok-mail");

    expect(confirmacion.ok).toBe(true);
    expect(cancelacion.porcentaje).toBe(100);
    expect(ultimaLlamada().url).toBe("/api/mail/cancelar?token=tok-mail");
    expect(headersDe(ultimaLlamada().init).Accept).toBe("application/json");
  });

  it.each([
    [400, "validacion"],
    [404, "no_encontrado"],
    [409, "conflicto"],
    [422, "no_procesable"],
    [429, "rate_limit"],
  ] as const)("mapea HTTP %i a error público %s", async (status, kind) => {
    fetchMock.mockResolvedValue(respuesta({ code: "CODIGO_X", detail: "detalle servidor" }, status));

    const error = await getPrecios().catch((cause: unknown) => cause);

    expect(error).toBeInstanceOf(PublicApiError);
    const publico = error as PublicApiError;
    expect(publico.kind).toBe(kind);
    expect(publico.status).toBe(status);
    expect(publico.code).toBe("CODIGO_X");
    expect(publico.mensaje.length).toBeGreaterThan(0);
  });

  it("mapea caída de red a error público 'red'", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    const error = await getPrecios().catch((cause: unknown) => cause);

    expect(error).toBeInstanceOf(PublicApiError);
    expect((error as PublicApiError).kind).toBe("red");
  });

  it("mapea respuesta con formato inesperado a error público 'formato'", async () => {
    fetchMock.mockResolvedValue(
      new Response("<html>no json</html>", {
        status: 200,
        headers: { "Content-Type": "text/html" },
      }),
    );

    const error = await getPrecios().catch((cause: unknown) => cause);

    expect(error).toBeInstanceOf(PublicApiError);
    expect((error as PublicApiError).kind).toBe("formato");
  });
});
