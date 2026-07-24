import { Moon, Sun } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { Logo } from "./Logo";

const LINKS = [
  { to: "/", label: "Analisar" },
  { to: "/historico", label: "Histórico" },
];

export function NavBar() {
  const { setToken } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { pathname } = useLocation();
  const isDark = theme === "dark";

  return (
    <nav className="sticky top-0 z-10 border-b border-line bg-paper/95 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-6 px-6 py-3.5">
        <div className="flex items-center gap-8">
          <Link
            to="/"
            aria-label="ask-ME — página inicial"
            className="shrink-0"
          >
            <Logo />
          </Link>
          <div className="flex items-center gap-1">
            {LINKS.map((link) => {
              const active = pathname === link.to;
              return (
                <Link
                  key={link.to}
                  to={link.to}
                  aria-current={active ? "page" : undefined}
                  className={`rounded-[3px] px-3 py-1.5 font-mono text-sm uppercase tracking-wider transition-colors ${
                    active
                      ? "bg-ink text-paper"
                      : "text-ink-muted hover:text-ink"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
          </div>
        </div>
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={
              isDark ? "Alternar para modo claro" : "Alternar para modo escuro"
            }
            title={
              isDark ? "Alternar para modo claro" : "Alternar para modo escuro"
            }
            className="flex cursor-pointer h-7 w-7 items-center justify-center rounded-[3px] text-ink-muted transition-colors hover:border-signal/60 hover:text-ink"
          >
            {isDark ? (
              <Sun size={16} color="#F2B233" aria-hidden="true" />
            ) : (
              <Moon size={16} color="#000000" aria-hidden="true" />
            )}
          </button>
          <button
            type="button"
            onClick={() => setToken(null)}
            className="font-mono cursor-pointer text-sm uppercase tracking-wider text-ink-muted transition-colors hover:text-red-500"
          >
            Sair
          </button>
        </div>
      </div>
    </nav>
  );
}
