import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { resetPassword } from "../api/auth";
import { ApiError } from "../api/client";
import { AuthLayout } from "../components/AuthLayout";
import { FormError } from "../components/FormError";
import { SubmitButton } from "../components/SubmitButton";
import { TextField } from "../components/TextField";

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    if (password.length < 8) {
      setError("A senha precisa ter ao menos 8 caracteres.");
      return;
    }
    if (password !== confirmation) {
      setError("As senhas não coincidem.");
      return;
    }

    setSubmitting(true);
    try {
      await resetPassword(token, password);
      navigate("/login", { replace: true });
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Não foi possível redefinir a senha. Tente novamente."
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (!token) {
    return (
      <AuthLayout
        title="Link inválido"
        subtitle="Este link de redefinição está incompleto. Solicite um novo."
      >
        <Link
          to="/forgot-password"
          className="block text-center font-mono text-xs uppercase tracking-wider text-signal transition-colors hover:text-ink"
        >
          Solicitar novo link
        </Link>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Nova senha" subtitle="Escolha uma senha de ao menos 8 caracteres.">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <TextField
          id="password"
          label="Nova senha"
          type="password"
          value={password}
          onChange={setPassword}
          autoComplete="new-password"
        />
        <TextField
          id="confirmation"
          label="Confirme a nova senha"
          type="password"
          value={confirmation}
          onChange={setConfirmation}
          autoComplete="new-password"
        />

        {error && <FormError message={error} />}

        <SubmitButton submitting={submitting} submittingLabel="Salvando...">
          Salvar nova senha
        </SubmitButton>
      </form>
    </AuthLayout>
  );
}
