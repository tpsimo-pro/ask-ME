import { Link } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

export function NavBar() {
  const { setToken } = useAuth();

  return (
    <nav className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
      <div className="flex items-center gap-6">
        <span className="font-mono text-sm font-semibold text-slate-900">ask-ME</span>
        <Link to="/" className="text-sm text-slate-600 hover:text-indigo-600">
          Analisar
        </Link>
        <Link to="/historico" className="text-sm text-slate-600 hover:text-indigo-600">
          Histórico
        </Link>
      </div>
      <button
        type="button"
        onClick={() => setToken(null)}
        className="text-sm text-slate-500 hover:text-slate-900"
      >
        Sair
      </button>
    </nav>
  );
}
