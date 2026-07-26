import { Navigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

export function AuthCallbackPage() {
  // Google's callback set the refresh cookie server-side and AuthProvider's
  // bootstrap exchanges it for an access token, so this page only has to wait
  // for that to resolve. There is no longer a token in the URL to parse, and
  // therefore no effect, no ref guard, and no manual navigation.
  const { status } = useAuth();

  if (status === "loading") {
    return <p className="p-6 font-mono text-sm text-ink-muted">Entrando...</p>;
  }

  return <Navigate to={status === "authenticated" ? "/" : "/login"} replace />;
}
