import { Link, useLocation } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { Logo } from "./Logo";

const LINKS = [
  { to: "/", label: "Analisar" },
  { to: "/historico", label: "Histórico" },
];

function SunIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      width="16"
      height="16"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="10" cy="10" r="3.5" fill="#F2B233" />
      <g stroke="#F2B233" strokeWidth="1.6" strokeLinecap="round">
        <line x1="10" y1="1.5" x2="10" y2="3.5" />
        <line x1="10" y1="16.5" x2="10" y2="18.5" />
        <line x1="1.5" y1="10" x2="3.5" y2="10" />
        <line x1="16.5" y1="10" x2="18.5" y2="10" />
        <line x1="4.2" y1="4.2" x2="5.6" y2="5.6" />
        <line x1="14.4" y1="14.4" x2="15.8" y2="15.8" />
        <line x1="4.2" y1="15.8" x2="5.6" y2="14.4" />
        <line x1="14.4" y1="5.6" x2="15.8" y2="4.2" />
      </g>
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      width="16"
      height="16"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M17 11.2A7.2 7.2 0 1 1 8.8 3a5.7 5.7 0 0 0 8.2 8.2Z"
        fill="#FFFFFF"
      />
    </svg>
  );
}

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
            {isDark ? <MoonIcon /> : <SunIcon />}
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
