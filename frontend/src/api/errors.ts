function asRecord(value: unknown): Record<string, unknown> | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function readDetail(payload: unknown): string | null {
  const record = asRecord(payload);
  if (record === null) {
    return null;
  }

  if (typeof record.detail === "string" && record.detail.trim() !== "") {
    return record.detail;
  }

  if (Array.isArray(record.detail)) {
    const messages = record.detail
      .map((item: unknown) => {
        const issue = asRecord(item);
        return issue !== null && typeof issue.msg === "string" ? issue.msg : null;
      })
      .filter((message): message is string => message !== null && message.trim() !== "");
    if (messages.length > 0) {
      return messages.join(" ");
    }
  }

  if (typeof record.error === "string" && record.error.trim() !== "") {
    return record.error;
  }

  return null;
}

function readCode(payload: unknown): string | null {
  const record = asRecord(payload);
  if (record !== null && typeof record.code === "string" && record.code.trim() !== "") {
    return record.code;
  }
  return null;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;
  readonly detail: string;

  constructor(status: number, detail: string, code: string | null = null) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

export function buildApiError(status: number, payload: unknown): ApiError {
  const detail = readDetail(payload) ?? `No se pudo completar la solicitud (HTTP ${status}).`;
  return new ApiError(status, detail, readCode(payload));
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export type PublicErrorKind =
  | "validacion"
  | "no_encontrado"
  | "conflicto"
  | "no_procesable"
  | "rate_limit"
  | "red"
  | "formato"
  | "servidor"
  | "inesperado";

const KIND_POR_STATUS: Record<number, PublicErrorKind> = {
  400: "validacion",
  404: "no_encontrado",
  409: "conflicto",
  422: "no_procesable",
  429: "rate_limit",
};

export const MENSAJE_POR_KIND: Record<PublicErrorKind, string> = {
  validacion: "Revisá los datos ingresados e intentá de nuevo.",
  no_encontrado: "No encontramos lo que buscabas. Verificá el enlace o los datos.",
  conflicto: "El horario ya no está disponible. Elegí otro turno.",
  no_procesable: "No pudimos procesar la solicitud con esos datos. Revisalos e intentá de nuevo.",
  rate_limit: "Demasiadas solicitudes. Esperá un momento y volvé a intentar.",
  red: "No pudimos conectarnos con el consultorio. Revisá tu conexión y reintentá.",
  formato: "El servidor devolvió una respuesta inesperada. Reintentá en unos instantes.",
  servidor: "El consultorio tuvo un problema. Reintentá en unos instantes.",
  inesperado: "Ocurrió un error inesperado. Volvé a intentar.",
};

export class PublicApiError extends Error {
  readonly kind: PublicErrorKind;
  readonly status: number | null;
  readonly code: string | null;
  readonly mensaje: string;
  readonly detail: string | null;

  constructor(
    kind: PublicErrorKind,
    mensaje: string = MENSAJE_POR_KIND[kind],
    status: number | null = null,
    code: string | null = null,
    detail: string | null = null,
  ) {
    super(mensaje);
    this.name = "PublicApiError";
    this.kind = kind;
    this.status = status;
    this.code = code;
    this.mensaje = mensaje;
    this.detail = detail;
  }
}

export function mapPublicError(error: unknown): PublicApiError {
  if (error instanceof PublicApiError) {
    return error;
  }
  if (error instanceof ApiError) {
    const kind = KIND_POR_STATUS[error.status] ?? (error.status >= 500 ? "servidor" : "inesperado");
    return new PublicApiError(kind, MENSAJE_POR_KIND[kind], error.status, error.code, error.detail);
  }
  if (error instanceof TypeError) {
    return new PublicApiError("red");
  }
  return new PublicApiError("inesperado");
}

export function toPublicErrorMessage(error: unknown): string {
  if (error instanceof PublicApiError) {
    return error.mensaje;
  }
  return toErrorMessage(error);
}

export function toErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.code !== null ? `${error.detail} (${error.code})` : error.detail;
  }
  if (error instanceof Error && error.message !== "") {
    return error.message;
  }
  return "Ocurrió un error inesperado. Volvé a intentar.";
}
