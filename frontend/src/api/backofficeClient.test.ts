import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setAccessToken } from "../auth/store";
import {
  aprobarDevolucion,
  borrarBloqueoStaff,
  borrarDisponibilidadStaff,
  cancelarTurnoStaff,
  cotizarCancelacionStaff,
  crearBloqueoStaff,
  crearDisponibilidadStaff,
  crearReservaTelefonica,
  descargarComprobantePdf,
  editarDisponibilidadStaff,
  ejecutarDevolucion,
  getComprobante,
  getTrazabilidadTurno,
  listarAlertasConciliacion,
  listarBloqueosStaff,
  listarDevoluciones,
  listarDisponibilidadStaff,
  rechazarDevolucion,
  reprogramarTurnoStaff,
} from "./backoffice";
import { ApiError } from "./errors";

const OD_ID = "19ceb23b-eacd-4ff6-95d6-94f1548d1b30";
const DEV_ID = "aa111111-1111-1111-1111-111111111111";
const COMP_ID = "bb222222-2222-2222-2222-222222222222";
const TURNO_ID = "cc333333-3333-3333-3333-333333333333";

function jsonResp(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const fetchMock = vi.fn<typeof fetch>();

function lastCall(): { url: string; init: RequestInit } {
  const llamada = fetchMock.mock.calls[fetchMock.mock.calls.length - 1];
  if (llamada === undefined) {
    throw new Error("fetch no fue invocado");
  }
  const [url, init] = llamada;
  return { url: String(url), init: init ?? {} };
}

function headersOf(init: RequestInit): Record<string, string> {
  return (init.headers ?? {}) as Record<string, string>;
}

const DEVOLUCION_DTO = {
  id: DEV_ID,
  pago_id: "pago-1",
  turno_id: TURNO_ID,
  monto: 39000,
  porcentaje: 60,
  motivo: "Cancelado fuera de término",
  motivo_rechazo: null,
  estado: "pendiente",
  aprobada_at: null,
  rechazada_at: null,
  marca: "(simulado)",
};

describe("cliente API backoffice", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    setAccessToken("jwt-staff-token");
  });

  afterEach(() => {
    setAccessToken(null);
    vi.unstubAllGlobals();
  });

  it("serializa bandeja de devoluciones, aprobar, rechazar, ejecutar, comprobante PDF y trazabilidad con Bearer JWT", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResp([DEVOLUCION_DTO]))
      .mockResolvedValueOnce(
        jsonResp([
          {
            id: "ev-1",
            pago_id: "pago-1",
            turno_id: TURNO_ID,
            tipo: "devolucion",
            detalle: "discrepancia simulada",
            estado_pago: "aprobado",
            estado_esperado: "reembolsado_parcial",
            estado_turno: "devuelto",
            discrepancia: true,
            actor: "sistema",
            fecha: "2030-05-01T12:00:00+00:00",
            marca: "(simulado)",
          },
        ]),
      )
      .mockResolvedValueOnce(jsonResp({ ...DEVOLUCION_DTO, estado: "aprobada" }))
      .mockResolvedValueOnce(
        jsonResp({ ...DEVOLUCION_DTO, estado: "rechazada", motivo_rechazo: "Sin respaldo" }),
      )
      .mockResolvedValueOnce(
        jsonResp({
          id: DEV_ID,
          estado: "ejecutada",
          monto: 39000,
          porcentaje: 60,
          mp_refund_id: "sim_refund_1",
          pago_estado: "reembolsado_parcial",
          marca: "(simulado)",
        }),
      )
      .mockResolvedValueOnce(
        jsonResp({
          id: COMP_ID,
          pago_id: "pago-1",
          devolucion_id: DEV_ID,
          turno_id: TURNO_ID,
          tipo: "recibo_interno",
          concepto: "devolucion",
          numero: "REC-0002",
          monto: 39000,
          moneda: "ARS",
          cae: null,
          emitida_at: "2030-05-01T12:05:00+00:00",
          simulado: true,
          marca: "(simulado)",
        }),
      )
      .mockResolvedValueOnce(
        new Response("%PDF-1.4\n%%EOF", {
          status: 200,
          headers: { "Content-Type": "application/pdf" },
        }),
      )
      .mockResolvedValueOnce(
        jsonResp({
          turno: {
            id: TURNO_ID,
            paciente_id: "pac-1",
            odontologo_id: OD_ID,
            inicio: "2030-05-10T12:00:00+00:00",
            fin: "2030-05-10T12:30:00+00:00",
            estado: "devuelto",
            canal: "web",
            pago_id: "pago-1",
            reprogramado_de_id: null,
          },
          pago: {
            id: "pago-1",
            estado: "reembolsado_parcial",
            monto: 65000,
            moneda: "ARS",
            proveedor: "simulado",
          },
          devolucion: null,
          comprobantes: [],
          eventos_pago: [],
          historial: [],
          marca: "(simulado)",
        }),
      );

    const lista = await listarDevoluciones("pendiente");
    expect(lista).toHaveLength(1);
    expect(lastCall().url).toBe("/api/devoluciones?estado=pendiente");
    expect(headersOf(lastCall().init).Authorization).toBe("Bearer jwt-staff-token");

    const alertas = await listarAlertasConciliacion();
    expect(alertas[0]?.discrepancia).toBe(true);
    expect(lastCall().url).toBe("/api/devoluciones/alertas");

    const aprobada = await aprobarDevolucion(DEV_ID, "39000", "OK");
    expect(aprobada.estado).toBe("aprobada");
    expect(JSON.parse(String(lastCall().init.body))).toEqual({
      monto_confirmado: "39000",
      motivo: "OK",
    });

    const rechazada = await rechazarDevolucion(DEV_ID, "Sin respaldo");
    expect(rechazada.estado).toBe("rechazada");
    expect(lastCall().url).toBe(`/api/devoluciones/${DEV_ID}/rechazar`);

    const ejecutada = await ejecutarDevolucion(DEV_ID);
    expect(ejecutada.mp_refund_id).toBe("sim_refund_1");
    expect(lastCall().url).toBe(`/api/devoluciones/${DEV_ID}/ejecutar`);

    const comp = await getComprobante(COMP_ID);
    expect(comp.simulado).toBe(true);
    expect(lastCall().url).toBe(`/api/comprobantes/${COMP_ID}`);

    const blob = await descargarComprobantePdf(COMP_ID);
    expect(blob).toBeInstanceOf(Blob);
    expect(lastCall().url).toBe(`/api/comprobantes/${COMP_ID}/pdf`);
    expect(headersOf(lastCall().init).Authorization).toBe("Bearer jwt-staff-token");

    const traza = await getTrazabilidadTurno(TURNO_ID);
    expect(traza.marca).toBe("(simulado)");
    expect(lastCall().url).toBe(`/api/turnos/${TURNO_ID}/trazabilidad`);
  });

  it("opera disponibilidad, bloqueos, reserva telefónica y cancelar/reprogramar staff", async () => {
    fetchMock
      .mockResolvedValueOnce(
        jsonResp([
          {
            id: "disp-1",
            odontologo_id: OD_ID,
            dia_semana: 1,
            hora_inicio: "09:00:00",
            hora_fin: "13:00:00",
            duracion_min: 30,
            tope_dia: 8,
            vigente_desde: null,
            vigente_hasta: null,
          },
        ]),
      )
      .mockResolvedValueOnce(
        jsonResp(
          {
            id: "disp-1",
            odontologo_id: OD_ID,
            dia_semana: 1,
            hora_inicio: "09:00:00",
            hora_fin: "13:00:00",
            duracion_min: 30,
            tope_dia: 8,
            vigente_desde: null,
            vigente_hasta: null,
          },
          201,
        ),
      )
      .mockResolvedValueOnce(
        jsonResp({
          id: "disp-1",
          odontologo_id: OD_ID,
          dia_semana: 1,
          hora_inicio: "10:00:00",
          hora_fin: "13:00:00",
          duracion_min: 30,
          tope_dia: 6,
          vigente_desde: null,
          vigente_hasta: null,
        }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(
        jsonResp([
          {
            id: "bloq-1",
            odontologo_id: OD_ID,
            desde: "2030-05-12T12:00:00+00:00",
            hasta: "2030-05-12T13:00:00+00:00",
            motivo: "pausa",
          },
        ]),
      )
      .mockResolvedValueOnce(
        jsonResp(
          {
            id: "bloq-1",
            odontologo_id: OD_ID,
            desde: "2030-05-12T12:00:00+00:00",
            hasta: "2030-05-12T13:00:00+00:00",
            motivo: "pausa",
          },
          201,
        ),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(
        jsonResp(
          {
            id: TURNO_ID,
            paciente_id: "pac-1",
            odontologo_id: OD_ID,
            inicio: "2030-05-15T13:00:00+00:00",
            fin: "2030-05-15T13:30:00+00:00",
            estado: "creado",
            canal: "recepcion",
            pago_id: "pago-1",
            checkout_url: null,
            checkout_token: null,
          },
          201,
        ),
      )
      .mockResolvedValueOnce(jsonResp({ porcentaje: 100 }))
      .mockResolvedValueOnce(jsonResp({ id: TURNO_ID, estado: "cancelado", devolucion: null }))
      .mockResolvedValueOnce(
        jsonResp({
          origen: { id: TURNO_ID, estado: "reprogramado" },
          nuevo: {
            id: "turno-2",
            estado: "confirmado",
            pago_id: "pago-1",
            reprogramado_de_id: TURNO_ID,
          },
        }),
      );

    expect(await listarDisponibilidadStaff(OD_ID)).toHaveLength(1);
    expect(lastCall().url).toBe(`/api/staff/disponibilidad?odontologo_id=${OD_ID}`);

    await crearDisponibilidadStaff({
      odontologo_id: OD_ID,
      dia_semana: 1,
      hora_inicio: "09:00",
      hora_fin: "13:00",
      duracion_min: 30,
      tope_dia: 8,
    });
    expect(lastCall().url).toBe("/api/staff/disponibilidad");

    await editarDisponibilidadStaff("disp-1", { tope_dia: 6, hora_inicio: "10:00" });
    expect(lastCall().init.method).toBe("PUT");

    await borrarDisponibilidadStaff("disp-1");
    expect(lastCall().init.method).toBe("DELETE");

    expect(await listarBloqueosStaff(OD_ID)).toHaveLength(1);
    await crearBloqueoStaff({
      odontologo_id: OD_ID,
      desde: "2030-05-12T12:00:00+00:00",
      hasta: "2030-05-12T13:00:00+00:00",
      motivo: "pausa",
    });
    await borrarBloqueoStaff("bloq-1");
    expect(lastCall().url).toBe("/api/staff/bloqueos/bloq-1");

    const tel = await crearReservaTelefonica(
      {
        odontologo_id: OD_ID,
        inicio: "2030-05-15T13:00:00+00:00",
        dni: "30111222",
        nombre: "Ana",
        apellido: "Ficticia",
        email: "ana@ficticia.example.ar",
        telefono: null,
        consentimiento_datos: true,
      },
      "idem-tel-1",
    );
    expect(tel.canal).toBe("recepcion");
    expect(lastCall().url).toBe("/api/reservas/telefonica");
    expect(headersOf(lastCall().init)["Idempotency-Key"]).toBe("idem-tel-1");

    expect((await cotizarCancelacionStaff(TURNO_ID)).porcentaje).toBe(100);
    expect(lastCall().url).toBe(`/api/reservas/${TURNO_ID}/cotizar-cancelacion`);

    const canc = await cancelarTurnoStaff(TURNO_ID, "Pedido paciente");
    expect(canc.estado).toBe("cancelado");

    const reprog = await reprogramarTurnoStaff(
      TURNO_ID,
      "2030-05-20T14:00:00+00:00",
      "idem-reprog-staff-1",
    );
    expect(reprog.nuevo.id).toBe("turno-2");
    expect(headersOf(lastCall().init)["Idempotency-Key"]).toBe("idem-reprog-staff-1");
  });

  it("propaga ApiError 403/422 y rechaza formatos inesperados en borde", async () => {
    fetchMock
      .mockResolvedValueOnce(
        jsonResp({ code: "MONTO_NO_COINCIDE", detail: "monto no coincide" }, 422),
      )
      .mockResolvedValueOnce(jsonResp({ inesperado: true }, 200));

    const err1 = await aprobarDevolucion(DEV_ID, "10").catch((e: unknown) => e);
    expect(err1).toBeInstanceOf(ApiError);
    expect((err1 as ApiError).code).toBe("MONTO_NO_COINCIDE");
    expect((err1 as ApiError).status).toBe(422);

    const err2 = await getTrazabilidadTurno(TURNO_ID).catch((e: unknown) => e);
    expect(err2).toBeInstanceOf(ApiError);
    expect((err2 as ApiError).status).toBe(502);
  });
});
