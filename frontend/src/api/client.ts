const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "";

interface RequestOptions {
  method: string;
  body?: string;
}

export async function apiFetch<T>(path: string, options?: RequestOptions): Promise<T> {
  const response: Response = await fetch(`${API_BASE_URL}${path}`, {
    method: options?.method ?? "GET",
    headers: { "Content-Type": "application/json" },
    body: options?.body,
  });
  if (!response.ok) {
    throw new Error(`API error ${response.status} on ${path}`);
  }
  const data: T = (await response.json()) as T;
  return data;
}

export interface HealthResponse {
  status: string;
  service: string;
}

export function fetchHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/api/health");
}
