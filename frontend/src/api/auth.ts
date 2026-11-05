import { apiFetch } from "./client";
import { ApiError } from "./errors";
import {
  isLoginResponse,
  isLogoutResponse,
  isMeResponse,
  type LoginRequest,
  type LoginResponse,
  type LogoutResponse,
  type MeResponse,
} from "./types";

function invalidResponse(): ApiError {
  return new ApiError(502, "El servidor devolvió una respuesta de sesión inesperada.");
}

export async function loginRequest(body: LoginRequest): Promise<LoginResponse> {
  const data = await apiFetch<unknown>("/api/auth/login", {
    method: "POST",
    body,
    auth: false,
  });
  if (!isLoginResponse(data)) {
    throw invalidResponse();
  }
  return data;
}

export async function refreshSession(): Promise<LoginResponse> {
  const data = await apiFetch<unknown>("/api/auth/refresh", {
    method: "POST",
    auth: false,
  });
  if (!isLoginResponse(data)) {
    throw invalidResponse();
  }
  return data;
}

export async function getMe(signal?: AbortSignal): Promise<MeResponse> {
  const data = await apiFetch<unknown>("/api/auth/me", { signal });
  if (!isMeResponse(data)) {
    throw invalidResponse();
  }
  return data;
}

export async function logoutRequest(): Promise<LogoutResponse> {
  const data = await apiFetch<unknown>("/api/auth/logout", { method: "POST" });
  if (!isLogoutResponse(data)) {
    throw invalidResponse();
  }
  return data;
}
