import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  aprobarDevolucion,
  descargarComprobantePdf,
  ejecutarDevolucion,
  getTrazabilidadTurno,
  listarAlertasConciliacion,
  listarDevoluciones,
  rechazarDevolucion,
} from "../../api/backoffice";
import { ApiError } from "../../api/errors";
import type {
  AlertaConciliacion,
  DevolucionBandeja,
  TrazabilidadTurno,
} from "../../api/types";
import { BandejaPage } from "./BandejaPage";

vi.mock("../../api/backoffice", () => ({
  listarDevoluciones: vi.fn(),
  listarAlertasConciliacion: vi.fn(),
  aprobarDevolucion: vi.fn(),
  rechazarDevolucion: vi.fn(),
  ejecutarDevolucion: vi.fn(),
  getTrazabilidadTurno: vi.fn(),
  descargarComprobantePdf: vi.fn(),
}));

const DEV_PENDIENTE: DevolucionBandeja = {
  id: "dev-1",
  pago_id: "pago-1",
  turno_id: "turno-1",
  monto: 39000,
  porcentaje: 60,
  motivo: "Cancelado fuera de término",
  motivo_rechazo: null,
  estado: "pendiente",
  aprobada_at: null,
  rechazada_at: null,
  marca: "(simulado)",
};

const ALERTA_CONCILIACION: AlertaConciliacion = {
  id: "alerta-1",
  pago_id: "pago-2",
  turno_id: "turno-2",
  tipo: "devolucion",
  detalle: "Reembolso pendiente de conciliar",
  estado_pago: "aprobado",
  estado_esperado: "reembolsado_parcial",
  estado_turno: "devuelto",
  discrepancia: true,
  actor: "sistema",
  fecha: "2030-05-01T14:00:00+00:00",
  marca: "(simulado)",
};

const TRAZA_OK: TrazabilidadTurno = {
  turno: {
    id: "turno-1",
    paciente_id: "pac-1",
    odontologo_id: "od-1",
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
  devolucion: {
    id: "dev-1",
    estado: "ejecutada",
    monto: 39000,
    porcentaje: 60,
    motivo: "Cancelado fuera de término",
    mp_refund_id: "sim_refund_1",
    aprobada_at: "2030-05-02T10:00:00+00:00",
    rechazada_at: null,
    ejecutada_at: "2030-05-02T10:05:00+00:00",
  },
  comprobantes: [
    {
      id: "comp-1",
      concepto: "devolucion",
      numero: "REC-0002",
      monto: 39000,
      moneda: "ARS",
      emitida_at: "2030-05-02T10:05:00+00:00",
      simulado: true,
    },
  ],
  eventos_pago: [
    {
      id: "ev-1",
      tipo_evento: "devolucion_ejecutada",
      actor: "sistema",
      fecha: "2030-05-02T10:05:00+00:00",
      payload_json: {},
    },
  ],
  historial: [
    {
      id: "hist-1",
      estado_anterior: "cancelado",
      estado_nuevo: "devuelto",
      actor_tipo: "sistema",
      actor_id: "webhook",
      fecha: "2030-05-02T10:05:00+00:00",
      motivo: "devolucion ejecutada",
    },
  ],
  marca: "(simulado)",
};

function renderBandeja(): void {
  render(
    <MemoryRouter>
      <BandejaPage />
    </MemoryRouter>,
  );
}

describe("BandejaPage", () => {
  beforeEach(() => {
    vi.mocked(listarDevoluciones).mockReset();
    vi.mocked(listarAlertasConciliacion).mockReset();
    vi.mocked(aprobarDevolucion).mockReset();
    vi.mocked(rechazarDevolucion).mockReset();
    vi.mocked(ejecutarDevolucion).mockReset();
    vi.mocked(getTrazabilidadTurno).mockReset();
    vi.mocked(descargarComprobantePdf).mockReset();

    vi.mocked(listarDevoluciones).mockResolvedValue([DEV_PENDIENTE]);
    vi.mocked(listarAlertasConciliacion).mockResolvedValue([ALERTA_CONCILIACION]);
  });

  it("filtra, aprueba manualmente con monto_confirmado, ejecuta y abre trazabilidad + PDF simulado", async () => {
    const aprobada: DevolucionBandeja = { ...DEV_PENDIENTE, estado: "aprobada" };
    const ejecutadaList: DevolucionBandeja = { ...DEV_PENDIENTE, estado: "ejecutada" };

    vi.mocked(aprobarDevolucion).mockResolvedValue(aprobada);
    vi.mocked(ejecutarDevolucion).mockResolvedValue({
      id: "dev-1",
      estado: "ejecutada",
      monto: 39000,
      porcentaje: 60,
      mp_refund_id: "sim_refund_1",
      pago_estado: "reembolsado_parcial",
      marca: "(simulado)",
    });
    vi.mocked(getTrazabilidadTurno).mockResolvedValue(TRAZA_OK);
    vi.mocked(descargarComprobantePdf).mockResolvedValue(new Blob(["%PDF-1.4"]));

    renderBandeja();

    expect(await screen.findByText(/39\.000/)).toBeInTheDocument();
    expect(screen.getAllByText("(simulado)").length).toBeGreaterThan(0);
    expect(screen.getByText(/Reembolso pendiente de conciliar/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Aprobar devolución" }));
    fireEvent.change(screen.getByLabelText("Monto confirmado"), { target: { value: "39000" } });

    vi.mocked(listarDevoluciones).mockResolvedValueOnce([aprobada]);
    fireEvent.click(screen.getByRole("button", { name: "Confirmar aprobación" }));

    await waitFor(() => {
      expect(aprobarDevolucion).toHaveBeenCalledWith("dev-1", "39000", undefined);
    });
    expect(await screen.findByRole("button", { name: "Ejecutar devolución" })).toBeInTheDocument();

    vi.mocked(listarDevoluciones).mockResolvedValueOnce([ejecutadaList]);
    fireEvent.click(screen.getByRole("button", { name: "Ejecutar devolución" }));

    expect(await screen.findByText(/sim_refund_1/)).toBeInTheDocument();
    expect(screen.getAllByText(/reembolsado_parcial/).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Ver trazabilidad" }));
    expect(await screen.findByRole("heading", { name: /Trazabilidad del turno/ })).toBeInTheDocument();
    expect(screen.getByText(/cancelado → devuelto/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Descargar PDF REC-0002" }));
    await waitFor(() => {
      expect(descargarComprobantePdf).toHaveBeenCalledWith("comp-1");
    });
  });

  it("bloquea rechazo sin motivo y maneja error 422 MONTO_NO_COINCIDE sin mutar estado", async () => {
    vi.mocked(aprobarDevolucion).mockRejectedValue(
      new ApiError(422, "monto confirmado 100 no coincide con 39000", "MONTO_NO_COINCIDE"),
    );

    renderBandeja();

    fireEvent.click(await screen.findByRole("button", { name: "Rechazar devolución" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmar rechazo" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/motivo/i);
    expect(rechazarDevolucion).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Aprobar devolución" }));
    fireEvent.change(screen.getByLabelText("Monto confirmado"), { target: { value: "100" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirmar aprobación" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/MONTO_NO_COINCIDE|no coincide/i);
    expect(screen.getByText("pendiente", { selector: "span" })).toBeInTheDocument();
  });

  it("ante 503 PROVEEDOR_NO_DISPONIBLE informa error v1 recuperable sin fallback en cliente", async () => {
    vi.mocked(listarDevoluciones).mockResolvedValue([{ ...DEV_PENDIENTE, estado: "aprobada" }]);
    vi.mocked(ejecutarDevolucion).mockRejectedValue(
      new ApiError(503, "PAGO_MODO=mercadopago no construido en v1 (P15)", "PROVEEDOR_NO_DISPONIBLE"),
    );

    renderBandeja();

    fireEvent.click(await screen.findByRole("button", { name: "Ejecutar devolución" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/PROVEEDOR_NO_DISPONIBLE|no construido/i);
    expect(screen.queryByText(/sim_refund_/)).not.toBeInTheDocument();
  });
});
