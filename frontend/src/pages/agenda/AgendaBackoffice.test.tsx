import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getAgenda, markAtendido, markNoShow } from "../../api/agenda";
import {
  borrarBloqueoStaff,
  cancelarTurnoStaff,
  cotizarCancelacionStaff,
  crearBloqueoStaff,
  crearDisponibilidadStaff,
  crearReservaTelefonica,
  getTrazabilidadTurno,
  listarBloqueosStaff,
  listarDisponibilidadStaff,
  reprogramarTurnoStaff,
} from "../../api/backoffice";
import { ApiError } from "../../api/errors";
import { getPaciente, getPacienteTurnos } from "../../api/pacientes";
import { getDisponibilidad } from "../../api/public";
import type { TrazabilidadTurno, TurnoAgenda, UserRole } from "../../api/types";
import { useAuth } from "../../auth/AuthProvider";
import { AppShell } from "../../components/AppShell";
import { AgendaPage } from "./AgendaPage";

vi.mock("../../auth/AuthProvider", () => ({
  useAuth: vi.fn(),
}));

vi.mock("../../api/agenda", () => ({
  getAgenda: vi.fn(),
  markAtendido: vi.fn(),
  markNoShow: vi.fn(),
}));

vi.mock("../../api/backoffice", () => ({
  listarDisponibilidadStaff: vi.fn(),
  crearDisponibilidadStaff: vi.fn(),
  borrarDisponibilidadStaff: vi.fn(),
  listarBloqueosStaff: vi.fn(),
  crearBloqueoStaff: vi.fn(),
  borrarBloqueoStaff: vi.fn(),
  crearReservaTelefonica: vi.fn(),
  cotizarCancelacionStaff: vi.fn(),
  cancelarTurnoStaff: vi.fn(),
  reprogramarTurnoStaff: vi.fn(),
  getTrazabilidadTurno: vi.fn(),
  descargarComprobantePdf: vi.fn(),
}));

vi.mock("../../api/public", () => ({
  getDisponibilidad: vi.fn(),
}));

vi.mock("../../api/pacientes", () => ({
  getPaciente: vi.fn(),
  getPacienteTurnos: vi.fn(),
}));

const OD_ID = "11111111-1111-4111-8111-111111111111";

function fechaFutura(dias: number): string {
  const destino = new Date();
  destino.setDate(destino.getDate() + dias);
  const mes = String(destino.getMonth() + 1).padStart(2, "0");
  const dia = String(destino.getDate()).padStart(2, "0");
  return `${destino.getFullYear()}-${mes}-${dia}`;
}

const FECHA = fechaFutura(5);

const TURNO_CONFIRMADO: TurnoAgenda = {
  id: "turno-staff-1",
  paciente_id: "pac-1",
  odontologo_id: OD_ID,
  inicio: `${FECHA}T13:00:00+00:00`,
  fin: `${FECHA}T13:30:00+00:00`,
  estado: "confirmado",
  canal: "web",
};

const TRAZA_STAFF: TrazabilidadTurno = {
  turno: {
    ...TURNO_CONFIRMADO,
    pago_id: "pago-1",
    reprogramado_de_id: null,
  },
  pago: {
    id: "pago-1",
    estado: "aprobado",
    monto: 65000,
    moneda: "ARS",
    proveedor: "simulado",
  },
  devolucion: null,
  comprobantes: [],
  eventos_pago: [],
  historial: [
    {
      id: "h-1",
      estado_anterior: "creado",
      estado_nuevo: "confirmado",
      actor_tipo: "sistema",
      actor_id: "webhook",
      fecha: `${FECHA}T12:00:00+00:00`,
      motivo: "pago simulado aprobado",
    },
  ],
  marca: "(simulado)",
};

function mockUser(rol: UserRole, odontologoId: string | null): void {
  vi.mocked(useAuth).mockReturnValue({
    status: "authenticated",
    user: {
      sub: "user-1",
      email: `${rol}@clinica-ficticia.example.ar`,
      rol,
      odontologo_id: odontologoId,
    },
    sessionExpired: false,
    login: vi.fn(),
    logout: vi.fn(),
  });
}

function renderAgendaShell(initialUrl = `/agenda?fecha=${FECHA}&odontologo_id=${OD_ID}`): void {
  render(
    <MemoryRouter initialEntries={[initialUrl]}>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/agenda" element={<AgendaPage />} />
          <Route path="/bandeja" element={<div data-testid="bandeja-stub">Bandeja</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("Agenda Backoffice (C-11)", () => {
  beforeEach(() => {
    vi.mocked(getAgenda).mockReset();
    vi.mocked(markAtendido).mockReset();
    vi.mocked(markNoShow).mockReset();
    vi.mocked(listarDisponibilidadStaff).mockReset();
    vi.mocked(crearDisponibilidadStaff).mockReset();
    vi.mocked(listarBloqueosStaff).mockReset();
    vi.mocked(crearBloqueoStaff).mockReset();
    vi.mocked(borrarBloqueoStaff).mockReset();
    vi.mocked(crearReservaTelefonica).mockReset();
    vi.mocked(cotizarCancelacionStaff).mockReset();
    vi.mocked(cancelarTurnoStaff).mockReset();
    vi.mocked(reprogramarTurnoStaff).mockReset();
    vi.mocked(getTrazabilidadTurno).mockReset();
    vi.mocked(getDisponibilidad).mockReset();
    vi.mocked(getPaciente).mockReset();
    vi.mocked(getPacienteTurnos).mockReset();

    vi.mocked(getAgenda).mockResolvedValue([TURNO_CONFIRMADO]);
    vi.mocked(listarDisponibilidadStaff).mockResolvedValue([]);
    vi.mocked(listarBloqueosStaff).mockResolvedValue([
      {
        id: "bloq-1",
        odontologo_id: OD_ID,
        desde: `${FECHA}T16:00:00+00:00`,
        hasta: `${FECHA}T17:00:00+00:00`,
        motivo: "pausa",
      },
    ]);
  });

  it("muestra navegación /agenda y /bandeja, cancela con cotización+motivo, reprograma (Q3) y abre trazabilidad", async () => {
    mockUser("recepcionista", null);
    vi.mocked(cotizarCancelacionStaff).mockResolvedValue({ porcentaje: 100 });
    vi.mocked(cancelarTurnoStaff).mockResolvedValue({
      id: TURNO_CONFIRMADO.id,
      estado: "cancelado",
      devolucion: null,
    });
    vi.mocked(getDisponibilidad).mockResolvedValue({
      slots: [{ inicio: `${FECHA}T15:00:00+00:00`, fin: `${FECHA}T15:30:00+00:00` }],
    });
    vi.mocked(reprogramarTurnoStaff).mockResolvedValue({
      origen: { id: TURNO_CONFIRMADO.id, estado: "reprogramado" },
      nuevo: {
        id: "turno-staff-2",
        estado: "confirmado",
        pago_id: "pago-1",
        reprogramado_de_id: TURNO_CONFIRMADO.id,
      },
    });
    vi.mocked(getTrazabilidadTurno).mockResolvedValue(TRAZA_STAFF);

    renderAgendaShell();

    expect(screen.getByRole("link", { name: "Agenda" })).toHaveAttribute("href", "/agenda");
    expect(screen.getByRole("link", { name: /Bandeja/i })).toHaveAttribute("href", "/bandeja");
    expect(screen.getByText(/Sin gestión de usuarios.*PAGO_MODO.*ARCA/i)).toBeInTheDocument();

    expect(await screen.findByText(/Canal: web/)).toBeInTheDocument();

    // Trazabilidad (B3)
    fireEvent.click(screen.getByRole("button", { name: "Ver trazabilidad" }));
    expect(await screen.findByText(/creado → confirmado/)).toBeInTheDocument();
    expect(screen.getByText(/pago simulado aprobado/)).toBeInTheDocument();

    // Reprogramación (Q3)
    fireEvent.click(screen.getByRole("button", { name: "Reprogramar" }));
    expect(screen.getByText(/conserva la seña original/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Nueva fecha para reprogramar"), {
      target: { value: FECHA },
    });
    const slotRadio = await screen.findByRole("radio");
    fireEvent.click(slotRadio);
    fireEvent.click(screen.getByRole("button", { name: "Confirmar reprogramación" }));

    await waitFor(() => {
      expect(reprogramarTurnoStaff).toHaveBeenCalledWith(
        TURNO_CONFIRMADO.id,
        `${FECHA}T15:00:00+00:00`,
        expect.any(String),
      );
    });

    // Cancelación con cotización y motivo
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(await screen.findByText(/100\s*%/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Motivo de cancelación"), {
      target: { value: "Solicitado por teléfono" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirmar cancelación" }));

    await waitFor(() => {
      expect(cancelarTurnoStaff).toHaveBeenCalledWith(
        TURNO_CONFIRMADO.id,
        "Solicitado por teléfono",
      );
    });
  });

  it("recepcionista crea reserva telefónica Q10 con consentimiento bloqueante y opera disponibilidad/bloqueos", async () => {
    mockUser("recepcionista", null);
    vi.mocked(crearDisponibilidadStaff).mockResolvedValue({
      id: "disp-1",
      odontologo_id: OD_ID,
      dia_semana: 0,
      hora_inicio: "09:00:00",
      hora_fin: "13:00:00",
      duracion_min: 30,
      tope_dia: 8,
      vigente_desde: null,
      vigente_hasta: null,
    });
    vi.mocked(borrarBloqueoStaff).mockResolvedValue(undefined);
    vi.mocked(crearReservaTelefonica).mockResolvedValue({
      id: "turno-tel-1",
      paciente_id: "pac-9",
      odontologo_id: OD_ID,
      inicio: `${FECHA}T14:00:00.000Z`,
      fin: `${FECHA}T14:30:00.000Z`,
      estado: "creado",
      canal: "recepcion",
      pago_id: "pago-9",
      checkout_url: null,
      checkout_token: null,
    });

    renderAgendaShell();
    expect(await screen.findByText(/Canal: web/)).toBeInTheDocument();

    // Disponibilidad & bloqueos
    fireEvent.click(screen.getByRole("button", { name: /Disponibilidad y bloqueos/i }));
    expect(await screen.findByRole("button", { name: "Eliminar bloqueo" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Hora inicio"), { target: { value: "14:00" } });
    fireEvent.change(screen.getByLabelText("Hora fin"), { target: { value: "09:00" } });
    fireEvent.click(screen.getByRole("button", { name: "Agregar franja" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/posterior/i);
    expect(crearDisponibilidadStaff).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Hora inicio"), { target: { value: "09:00" } });
    fireEvent.change(screen.getByLabelText("Hora fin"), { target: { value: "13:00" } });
    fireEvent.click(screen.getByRole("button", { name: "Agregar franja" }));
    await waitFor(() => {
      expect(crearDisponibilidadStaff).toHaveBeenCalled();
    });

    fireEvent.click(screen.getByRole("button", { name: "Eliminar bloqueo" }));
    await waitFor(() => {
      expect(borrarBloqueoStaff).toHaveBeenCalledWith("bloq-1");
    });

    // Reserva telefónica Q10 (consentimiento obligatorio P11)
    fireEvent.click(screen.getByRole("button", { name: /Reserva telefónica/i }));
    fireEvent.change(screen.getByLabelText("Fecha y hora del turno"), {
      target: { value: `${FECHA}T11:00` },
    });
    fireEvent.change(screen.getByLabelText("DNI del paciente"), { target: { value: "30999888" } });
    fireEvent.change(screen.getByLabelText("Nombre del paciente"), { target: { value: "Lucía" } });
    fireEvent.change(screen.getByLabelText("Apellido del paciente"), {
      target: { value: "Ficticia" },
    });
    fireEvent.change(screen.getByLabelText("Email del paciente"), {
      target: { value: "lucia@ficticia.example.ar" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Registrar reserva telefónica" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/consentimiento/i);
    expect(crearReservaTelefonica).not.toHaveBeenCalled();

    fireEvent.click(screen.getByLabelText(/consentimiento informado/i));
    fireEvent.click(screen.getByRole("button", { name: "Registrar reserva telefónica" }));
    await waitFor(() => {
      expect(crearReservaTelefonica).toHaveBeenCalledWith(
        expect.objectContaining({
          odontologo_id: OD_ID,
          dni: "30999888",
          consentimiento_datos: true,
        }),
        expect.any(String),
      );
    });
  });

  it("prohíbe reserva telefónica para odontólogo y conserva aislamiento en agenda (P8)", async () => {
    mockUser("odontologo", OD_ID);

    renderAgendaShell(`/agenda?fecha=${FECHA}`);
    expect(await screen.findByText(/Canal: web/)).toBeInTheDocument();

    expect(
      screen.queryByRole("button", { name: "Registrar reserva telefónica" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(/Solo recepción o administración pueden registrar reservas telefónicas/i),
    ).toBeInTheDocument();
  });

  it("maneja conflicto 409 al reprogramar sin perder contexto ni romper la agenda", async () => {
    mockUser("recepcionista", null);
    vi.mocked(getDisponibilidad).mockResolvedValue({
      slots: [{ inicio: `${FECHA}T15:00:00+00:00`, fin: `${FECHA}T15:30:00+00:00` }],
    });
    vi.mocked(reprogramarTurnoStaff).mockRejectedValue(
      new ApiError(409, "slot objetivo ocupado", "SLOT_OCUPADO"),
    );

    renderAgendaShell();
    expect(await screen.findByText(/Canal: web/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Reprogramar" }));
    fireEvent.change(screen.getByLabelText("Nueva fecha para reprogramar"), {
      target: { value: FECHA },
    });
    fireEvent.click(await screen.findByRole("radio"));
    fireEvent.click(screen.getByRole("button", { name: "Confirmar reprogramación" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/SLOT_OCUPADO|ocupado/i);
    expect(screen.getByRole("button", { name: "Confirmar reprogramación" })).toBeInTheDocument();
  });
});
