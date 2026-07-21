import { Link } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

export function NavBar() {
  const { setToken } = useAuth();

  return (
    <nav>
      <Link to="/">Analisar</Link>
      {" | "}
      <Link to="/historico">Histórico</Link>
      {" | "}
      <button type="button" onClick={() => setToken(null)}>
        Sair
      </button>
    </nav>
  );
}
