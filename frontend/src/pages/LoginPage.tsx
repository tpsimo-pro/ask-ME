import { Logo } from "../components/Logo";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export function LoginPage() {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-paper px-4">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-[0.35] [background-image:linear-gradient(var(--color-line)_1px,transparent_1px),linear-gradient(90deg,var(--color-line)_1px,transparent_1px)] [background-size:36px_36px] [mask-image:radial-gradient(ellipse_60%_60%_at_50%_40%,black,transparent)]"
      />

      <div className="relative flex flex-col items-center gap-8 text-center">
        <Logo className="scale-125" />

        <div className="max-w-sm">
          <p className="font-mono text-sm uppercase tracking-[0.2em] text-signal">
            Revisão de código assistida por IA
          </p>
          <h1 className="mt-3 font-display text-3xl font-semibold text-ink sm:text-4xl">
            Cole o código.
            <br />
            Receba o diagnóstico.
          </h1>
          <p className="mt-4 text-base leading-relaxed text-ink-muted">
            Sugestões de melhoria, testes gerados e riscos de segurança — em segundos, com
            histórico salvo na sua conta.
          </p>
        </div>

        <a href={`${API_BASE_URL}/auth/google/login`} className="group">
          <button
            type="button"
            className="rounded-[3px] border border-ink bg-ink px-6 py-3 font-sans text-base font-medium text-paper transition-colors group-hover:bg-paper group-hover:text-ink"
          >
            Entrar com Google
          </button>
        </a>

        <p className="font-mono text-xs uppercase tracking-wide text-ink-muted/70">
          Motor de análise: Groq · Llama 3.3 70B
        </p>
      </div>
    </div>
  );
}
