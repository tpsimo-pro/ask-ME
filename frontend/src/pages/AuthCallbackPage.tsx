import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

export function AuthCallbackPage() {
  const { setToken } = useAuth();
  const navigate = useNavigate();
  const hasProcessed = useRef(false);

  useEffect(() => {
    // Guards against StrictMode's dev-only double-invoke on mount; safe because
    // this route is only ever reached via a fresh page load (the OAuth
    // redirect), never a client-side route change onto an already-mounted instance.
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const match = window.location.hash.match(/token=([^&]+)/);
    if (match) {
      setToken(decodeURIComponent(match[1]));
      navigate("/", { replace: true });
    } else {
      navigate("/login", { replace: true });
    }
  }, [setToken, navigate]);

  return <p>Entrando...</p>;
}
