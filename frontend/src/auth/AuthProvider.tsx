import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { getMe, loginRequest, logoutRequest, refreshSession } from "../api/auth";
import { AUTH_UNAUTHORIZED_EVENT } from "../api/client";
import type { MeResponse } from "../api/types";
import { clearAccessToken, getAccessToken, setAccessToken } from "./store";

export type SessionStatus = "loading" | "anonymous" | "authenticated";

interface BootstrapResult {
  user: MeResponse;
}

interface AuthContextValue {
  status: SessionStatus;
  user: MeResponse | null;
  sessionExpired: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

async function bootstrapSession(): Promise<BootstrapResult | null> {
  try {
    if (getAccessToken() === null) {
      const refreshed = await refreshSession();
      setAccessToken(refreshed.access_token);
    }
    const user = await getMe();
    return { user };
  } catch {
    clearAccessToken();
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }): JSX.Element {
  const [status, setStatus] = useState<SessionStatus>("loading");
  const [user, setUser] = useState<MeResponse | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);
  const bootstrapRef = useRef<Promise<BootstrapResult | null> | null>(null);

  useEffect(() => {
    let active = true;

    if (bootstrapRef.current === null) {
      bootstrapRef.current = bootstrapSession();
    }

    void bootstrapRef.current.then((result: BootstrapResult | null) => {
      if (!active) {
        return;
      }
      if (result === null) {
        setUser(null);
        setStatus("anonymous");
        return;
      }
      setUser(result.user);
      setStatus("authenticated");
    });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    function handleUnauthorized(): void {
      clearAccessToken();
      setUser(null);
      setStatus("anonymous");
      setSessionExpired(true);
    }

    window.addEventListener(AUTH_UNAUTHORIZED_EVENT, handleUnauthorized);
    return () => window.removeEventListener(AUTH_UNAUTHORIZED_EVENT, handleUnauthorized);
  }, []);

  const login = useCallback(async (email: string, password: string): Promise<void> => {
    const response = await loginRequest({ email, password });
    setAccessToken(response.access_token);
    try {
      const me = await getMe();
      setUser(me);
      setStatus("authenticated");
      setSessionExpired(false);
    } catch (error) {
      clearAccessToken();
      setUser(null);
      setStatus("anonymous");
      throw error;
    }
  }, []);

  const logout = useCallback(async (): Promise<void> => {
    try {
      await logoutRequest();
    } catch {
      // La sesión local se limpia igual si el servidor no responde.
    } finally {
      clearAccessToken();
      setUser(null);
      setStatus("anonymous");
      setSessionExpired(false);
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ status, user, sessionExpired, login, logout }),
    [status, user, sessionExpired, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth debe usarse dentro de AuthProvider");
  }
  return context;
}
