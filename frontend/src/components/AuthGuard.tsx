import { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { Spinner } from "./Spinner";

export function AuthGuard({ children }: { children: ReactNode }) {
  const { status } = useAuth();

  // Redirecting while the cookie exchange is still in flight would flash the
  // login page on every reload for an already-signed-in user.
  if (status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper">
        <Spinner label="Carregando" />
      </div>
    );
  }

  if (status === "anonymous") {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
