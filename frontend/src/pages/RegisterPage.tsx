import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { register } from "../api/auth";
import { ApiError } from "../api/client";
import { AuthLayout } from "../components/AuthLayout";
import { FormError } from "../components/FormError";
import { SubmitButton } from "../components/SubmitButton";
import { TextField } from "../components/TextField";
import { useAuth } from "../context/AuthContext";

export function RegisterPage() {
  const { setToken } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    if (password.length < 8) {
      setError("A senha precisa ter ao menos 8 caracteres.");
      return;
    }

    setSubmitting(true);
    try {
      const { access_token } = await register(name, email, password);
      setToken(access_token);
      navigate("/", { replace: true });
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Não foi possível criar a conta. Tente novamente."
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout title="Criar conta" subtitle="Histórico de análises salvo na sua conta.">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <TextField
          id="name"
          label="Nome"
          type="text"
          value={name}
          onChange={setName}
          autoComplete="name"
        />
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
          label="Senha (mín. 8 caracteres)"
          type="password"
          value={password}
          onChange={setPassword}
          autoComplete="new-password"
        />

        {error && <FormError message={error} />}

        <SubmitButton submitting={submitting} submittingLabel="Criando...">
          Criar conta
        </SubmitButton>
      </form>

      <p className="mt-6 text-center font-mono text-xs uppercase tracking-wider text-ink-muted">
        Já tem conta?{" "}
        <Link to="/login" className="text-signal transition-colors hover:text-ink">
          Entrar
        </Link>
      </p>
    </AuthLayout>
  );
}
