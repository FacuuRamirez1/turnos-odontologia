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

export function toErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.code !== null ? `${error.detail} (${error.code})` : error.detail;
  }
  if (error instanceof Error && error.message !== "") {
    return error.message;
  }
  return "Ocurrió un error inesperado. Volvé a intentar.";
}
