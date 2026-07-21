import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

export function AuthCallbackPage() {
  const { setToken } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
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
