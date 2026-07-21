const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export function LoginPage() {
  return (
    <div>
      <h1>AI Code Analyzer</h1>
      <a href={`${API_BASE_URL}/auth/google/login`}>
        <button type="button">Entrar com Google</button>
      </a>
    </div>
  );
}
