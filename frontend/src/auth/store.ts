export type UserRole = "paciente" | "odontologo" | "recepcionista" | "admin";

export interface AuthState {
  accessToken: string | null;
  role: UserRole | null;
  odontologoId: string | null;
}

const initialAuthState: AuthState = {
  accessToken: null,
  role: null,
  odontologoId: null,
};

let currentAuthState: AuthState = { ...initialAuthState };

export function getAuthState(): AuthState {
  return { ...currentAuthState };
}

export function setAuthState(next: AuthState): void {
  currentAuthState = { ...next };
}

export function clearAuthState(): void {
  currentAuthState = { ...initialAuthState };
}

export function isAuthenticated(): boolean {
  return currentAuthState.accessToken !== null;
}
