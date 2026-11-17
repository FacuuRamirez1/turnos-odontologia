export interface DatosPaciente {
  dni: string;
  nombre: string;
  apellido: string;
  email: string;
  telefono: string;
  consentimiento_datos: boolean;
}

export const DATOS_PACIENTE_INICIALES: DatosPaciente = {
  dni: "",
  nombre: "",
  apellido: "",
  email: "",
  telefono: "",
  consentimiento_datos: false,
};

export type PasoReserva = 1 | 2 | 3 | 4;

export const PASOS_RESERVA: readonly { paso: PasoReserva; etiqueta: string }[] = [
  { paso: 1, etiqueta: "Datos" },
  { paso: 2, etiqueta: "Profesional" },
  { paso: 3, etiqueta: "Fecha y hora" },
  { paso: 4, etiqueta: "Confirmación" },
];
