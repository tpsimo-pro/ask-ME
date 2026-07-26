import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { login } from "../api/auth";
import { ApiError } from "../api/client";
import { AuthLayout } from "../components/AuthLayout";
import { FormError } from "../components/FormError";
import { SubmitButton } from "../components/SubmitButton";
import { TextField } from "../components/TextField";
import { useAuth } from "../context/AuthContext";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export function LoginPage() {
  const { setToken } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      const { access_token } = await login(email, password);
      setToken(access_token);
      navigate("/", { replace: true });
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "Não foi possível entrar. Tente novamente."
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Entrar"
      subtitle="Cole o código. Receba o diagnóstico."
      footer={<>Motor de análise: Groq · Llama 3.3 70B</>}
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <TextField
          id="email"
          label="E-mail"
          type="email"
          value={email}
          onChange={setEmail}
          autoComplete="email"
        />
        <TextField
          id="password"
          label="Senha"
          type="password"
          value={password}
          onChange={setPassword}
          autoComplete="current-password"
        />

        {error && <FormError message={error} />}

        <SubmitButton submitting={submitting} submittingLabel="Entrando...">
          Entrar
        </SubmitButton>

        <Link
          to="/forgot-password"
          className="text-center font-mono text-xs uppercase tracking-wider text-ink-muted transition-colors hover:text-ink"
        >
          Esqueci minha senha
        </Link>
      </form>

      <div className="my-6 flex items-center gap-3">
        <span className="h-px flex-1 bg-line" />
        <span className="font-mono text-xs uppercase tracking-wider text-ink-muted">ou</span>
        <span className="h-px flex-1 bg-line" />
      </div>

      <a href={`${API_BASE_URL}/auth/google/login`} className="group block">
        <button
          type="button"
          className="w-full cursor-pointer rounded-[3px] border border-ink bg-paper px-6 py-3 font-sans text-base font-medium text-ink transition-colors group-hover:bg-ink group-hover:text-paper"
        >
          Entrar com Google
        </button>
      </a>

      <p className="mt-6 text-center font-mono text-xs uppercase tracking-wider text-ink-muted">
        Não tem conta?{" "}
        <Link to="/register" className="text-signal transition-colors hover:text-ink">
          Criar conta
        </Link>
      </p>
    </AuthLayout>
  );
}
