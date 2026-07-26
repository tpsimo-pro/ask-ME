import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";

import { logout as logoutRequest } from "../api/auth";
import {
  refreshAccessToken,
  registerTokenRefreshHandler,
  registerUnauthorizedHandler,
} from "../api/client";

type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  token: string | null;
  status: AuthStatus;
  setToken: (token: string | null) => void;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  const setToken = useCallback((next: string | null) => {
    setTokenState(next);
    setStatus(next ? "authenticated" : "anonymous");
  }, []);

  useEffect(() => {
    registerUnauthorizedHandler(() => setToken(null));
    registerTokenRefreshHandler((next) => setToken(next));
  }, [setToken]);

  // Sessions live in an httpOnly cookie, so on every page load we must ask the
  // server whether one exists before deciding the user is anonymous. Until
  // this resolves, status stays "loading" and AuthGuard must not redirect.
  useEffect(() => {
    let cancelled = false;

    refreshAccessToken().then((next) => {
      if (cancelled) return;
      setToken(next ?? null);
    });

    return () => {
      cancelled = true;
    };
  }, [setToken]);

  const signOut = useCallback(async () => {
    try {
      await logoutRequest();
    } finally {
      setToken(null);
    }
  }, [setToken]);

  return (
    <AuthContext.Provider value={{ token, status, setToken, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
