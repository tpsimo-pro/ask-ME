import { useState } from "react";
import { Link } from "react-router-dom";

import { forgotPassword } from "../api/auth";
import { ApiError } from "../api/client";
import { AuthLayout } from "../components/AuthLayout";
import { FormError } from "../components/FormError";
import { SubmitButton } from "../components/SubmitButton";
import { TextField } from "../components/TextField";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await forgotPassword(email);
      setSent(true);
    } catch (caught) {
      // A 429 is the only error worth surfacing; the endpoint accepts every
      // other case with 202 so that unknown addresses are indistinguishable.
      setError(
        caught instanceof ApiError ? caught.message : "Não foi possível enviar o e-mail."
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (sent) {
    return (
      <AuthLayout
        title="Verifique seu e-mail"
        subtitle="Se existir uma conta com esse endereço, enviamos um link para redefinir a senha. O link expira em 60 minutos."
      >
        <Link
          to="/login"
          className="block text-center font-mono text-xs uppercase tracking-wider text-signal transition-colors hover:text-ink"
        >
          Voltar para entrar
        </Link>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Esqueci minha senha"
      subtitle="Informe seu e-mail e enviaremos um link para criar uma nova senha."
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

        {error && <FormError message={error} />}

        <SubmitButton submitting={submitting} submittingLabel="Enviando...">
          Enviar link
        </SubmitButton>

        <Link
          to="/login"
          className="text-center font-mono text-xs uppercase tracking-wider text-ink-muted transition-colors hover:text-ink"
        >
          Voltar
        </Link>
      </form>
    </AuthLayout>
  );
}
