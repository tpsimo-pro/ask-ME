const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export function LoginPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 px-4">
      <div className="text-center">
        <h1 className="font-mono text-2xl font-semibold text-slate-900">ask-ME</h1>
        <p className="mt-2 text-sm text-slate-500">
          Analisador de código com IA — sugestões, testes e riscos de segurança.
        </p>
      </div>
      <a href={`${API_BASE_URL}/auth/google/login`}>
        <button
          type="button"
          className="rounded-md bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-indigo-500"
        >
          Entrar com Google
        </button>
      </a>
    </div>
  );
}
