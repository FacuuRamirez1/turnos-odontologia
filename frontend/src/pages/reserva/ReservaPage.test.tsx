import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useSearchParams } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PublicApiError } from "../../api/errors";
import { crearReserva, getDisponibilidad, getPrecios } from "../../api/public";
import type { PreciosPublicos, ReservaPublica } from "../../api/types";
import { ReservaPage } from "./ReservaPage";

vi.mock("../../api/public", () => ({
  getPrecios: vi.fn(),
  getDisponibilidad: vi.fn(),
  crearReserva: vi.fn(),
  simularPago: vi.fn(),
}));

const ODONTOLOGO_ID = "19ceb23b-eacd-4ff6-95d6-94f1548d1b30";
const PAGO_ID = "0b6f9a2e-6d7a-4f3e-9a8e-2f1c4a5b6d7e";

function fechaFutura(dias: number): string {
  const destino = new Date();
  destino.setDate(destino.getDate() + dias);
  const mes = String(destino.getMonth() + 1).padStart(2, "0");
  const dia = String(destino.getDate()).padStart(2, "0");
  return `${destino.getFullYear()}-${mes}-${dia}`;
}

const FECHA = fechaFutura(4);
const SLOTS = [
  { inicio: `${FECHA}T13:00:00.000Z`, fin: `${FECHA}T13:30:00.000Z` },
  { inicio: `${FECHA}T14:00:00.000Z`, fin: `${FECHA}T14:30:00.000Z` },
];

const PRECIOS: PreciosPublicos = {
  odontologos: [
    { odontologo_id: ODONTOLOGO_ID, monto_turno: "70000.00", monto_senia: "65000.50" },
  ],
  trial: { disponible: true, requiere_tarjeta: false, dias: null },
  marca: "(simulado)",
};

const RESERVA_CON_CHECKOUT: ReservaPublica = {
  id: "turno-1",
  paciente_id: "paciente-1",
  odontologo_id: ODONTOLOGO_ID,
  inicio: SLOTS[0]?.inicio ?? "",
  fin: SLOTS[0]?.fin ?? "",
  estado: "creado",
  canal: "web",
  pago_id: PAGO_ID,
  checkout_url: `http://localhost:5173/checkout-simulado?pago_id=${PAGO_ID}&token=chk_abc`,
  checkout_token: "chk_abc",
};

const RESERVA_SIN_CHECKOUT: ReservaPublica = {
  ...RESERVA_CON_CHECKOUT,
  pago_id: "pago-senia-cero",
  checkout_url: null,
  checkout_token: null,
};

function CheckoutStub(): JSX.Element {
  const [params] = useSearchParams();
  return (
    <div data-testid="checkout-stub">
      {`${params.get("pago_id") ?? ""}|${params.get("token") ?? ""}`}
    </div>
  );
}

function renderReserva(): void {
  render(
    <MemoryRouter initialEntries={["/reservar"]}>
      <Routes>
        <Route path="/reservar" element={<ReservaPage />} />
        <Route path="/checkout-simulado" element={<CheckoutStub />} />
      </Routes>
    </MemoryRouter>,
  );
}

function completarPasoDatos(dni = "30111222"): void {
  fireEvent.change(screen.getByLabelText("DNI"), { target: { value: dni } });
  fireEvent.change(screen.getByLabelText("Nombre"), { target: { value: "Ana" } });
  fireEvent.change(screen.getByLabelText("Apellido"), { target: { value: "Ficticia" } });
  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: "ana@ficticia.example.ar" },
  });
}

function aceptarConsentimiento(): void {
  fireEvent.click(screen.getByLabelText(/Acepto el tratamiento/));
}

async function avanzarAProfesional(): Promise<void> {
  completarPasoDatos();
  aceptarConsentimiento();
  fireEvent.click(screen.getByRole("button", { name: "Continuar" }));
  await screen.findByRole("heading", { name: "Elegí profesional" });
  await screen.findAllByRole("radio");
}

async function avanzarAFechaYHorario(): Promise<void> {
  await avanzarAProfesional();
  fireEvent.click(screen.getAllByRole("radio")[0] as HTMLElement);
  fireEvent.click(screen.getByRole("button", { name: "Continuar" }));
  await screen.findByRole("heading", { name: "Elegí fecha y horario" });
}

async function avanzarAResumen(): Promise<void> {
  await avanzarAFechaYHorario();
  fireEvent.change(screen.getByLabelText("Fecha"), { target: { value: FECHA } });
  await waitFor(() => {
    expect(getDisponibilidad).toHaveBeenCalled();
  });
  const slots = await screen.findAllByRole("radio");
  fireEvent.click(slots[0] as HTMLElement);
  fireEvent.click(screen.getByRole("button", { name: "Continuar" }));
  await screen.findByRole("heading", { name: "Revisá y confirmá" });
}

describe("ReservaPage", () => {
  beforeEach(() => {
    vi.mocked(getPrecios).mockReset();
    vi.mocked(getDisponibilidad).mockReset();
    vi.mocked(crearReserva).mockReset();
    vi.mocked(getPrecios).mockResolvedValue(PRECIOS);
    vi.mocked(getDisponibilidad).mockResolvedValue({ slots: SLOTS });
  });

  it("completa la reserva y navega al checkout simulado con pago_id y token", async () => {
    vi.mocked(crearReserva).mockResolvedValue(RESERVA_CON_CHECKOUT);
    renderReserva();

    await avanzarAResumen();

    expect(screen.getByText(/70\.000/)).toBeInTheDocument();
    expect(screen.getByText(/65\.000/)).toBeInTheDocument();
    expect(screen.getAllByText("(simulado)").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Confirmar reserva" }));

    const stub = await screen.findByTestId("checkout-stub");
    expect(stub).toHaveTextContent(`${PAGO_ID}|chk_abc`);

    const llamada = vi.mocked(crearReserva).mock.calls[0];
    expect(llamada).toBeDefined();
    const [cuerpo, idempotencyKey] = llamada ?? [null, null];
    expect(cuerpo).toMatchObject({
      odontologo_id: ODONTOLOGO_ID,
      inicio: SLOTS[0]?.inicio,
      dni: "30111222",
      nombre: "Ana",
      apellido: "Ficticia",
      consentimiento_datos: true,
    });
    expect(typeof idempotencyKey).toBe("string");
    expect(String(idempotencyKey).length).toBeGreaterThan(0);
  });

  it("bloquea el avance sin consentimiento y no persiste nada", () => {
    renderReserva();

    completarPasoDatos();
    fireEvent.click(screen.getByRole("button", { name: "Continuar" }));

    expect(screen.getByRole("alert")).toHaveTextContent(/consentimiento/i);
    expect(screen.getByLabelText("DNI")).toHaveValue("30111222");
    expect(getPrecios).not.toHaveBeenCalled();
    expect(crearReserva).not.toHaveBeenCalled();
  });

  it("rechaza un DNI inválido sin llamar a la API", () => {
    renderReserva();

    completarPasoDatos("123");
    aceptarConsentimiento();
    fireEvent.click(screen.getByRole("button", { name: "Continuar" }));

    expect(screen.getByRole("alert")).toHaveTextContent(/DNI válido/i);
    expect(getPrecios).not.toHaveBeenCalled();
    expect(screen.getByLabelText("DNI")).toHaveValue("123");
  });

  it("ante 409 vuelve a fecha/horario, recarga slots y conserva los datos del Paso 1", async () => {
    vi.mocked(crearReserva).mockRejectedValue(
      new PublicApiError(
        "conflicto",
        "El horario ya no está disponible. Elegí otro turno.",
        409,
        "SLOT_OCUPADO",
      ),
    );
    renderReserva();

    await avanzarAResumen();
    fireEvent.click(screen.getByRole("button", { name: "Confirmar reserva" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/no está disponible/i);
    await screen.findByRole("heading", { name: "Elegí fecha y horario" });
    await waitFor(() => {
      expect(getDisponibilidad).toHaveBeenCalledTimes(2);
    });

    fireEvent.click(screen.getByRole("button", { name: "Volver" }));
    fireEvent.click(screen.getByRole("button", { name: "Volver" }));

    expect(await screen.findByLabelText("DNI")).toHaveValue("30111222");
    expect(screen.getByLabelText("Nombre")).toHaveValue("Ana");
  });

  it("advierte fechas pasadas, respeta la anticipación mínima y permite recargar slots", async () => {
    renderReserva();

    await avanzarAFechaYHorario();

    expect(screen.getByText(/24 horas de anticipación/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Fecha"), { target: { value: "2020-01-01" } });

    expect(await screen.findByRole("alert")).toHaveTextContent(/ya pasó/i);
    expect(getDisponibilidad).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Fecha"), { target: { value: FECHA } });

    await waitFor(() => {
      expect(getDisponibilidad).toHaveBeenCalledTimes(1);
    });
    await screen.findAllByRole("radio");

    fireEvent.click(screen.getByRole("button", { name: "Actualizar horarios" }));

    await waitFor(() => {
      expect(getDisponibilidad).toHaveBeenCalledTimes(2);
    });
  });

  it("con seña $0 confirma el turno sin abrir checkout", async () => {
    vi.mocked(getPrecios).mockResolvedValue({
      ...PRECIOS,
      odontologos: [
        { odontologo_id: ODONTOLOGO_ID, monto_turno: "70000.00", monto_senia: "0.00" },
      ],
    });
    vi.mocked(crearReserva).mockResolvedValue(RESERVA_SIN_CHECKOUT);
    renderReserva();

    await avanzarAResumen();
    fireEvent.click(screen.getByRole("button", { name: "Confirmar reserva" }));

    expect(await screen.findByRole("heading", { name: "Turno reservado" })).toBeInTheDocument();
    expect(screen.queryByTestId("checkout-stub")).not.toBeInTheDocument();
  });
});
