import { useState } from "react";

import { ApiError, apiFetch } from "../api/client";
import { AnalysisResult } from "../components/AnalysisResult";
import { CodeInput } from "../components/CodeInput";
import { Spinner } from "../components/Spinner";
import { useAuth } from "../context/AuthContext";

interface AnalyzeResponse {
  sugestoes: string[];
  testes_gerados: string;
  riscos_seguranca: string[];
}

export function AnalyzePage() {
  const { token } = useAuth();
  const [code, setCode] = useState("");
  const [language, setLanguage] = useState("python");
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAnalyze() {
    setIsLoading(true);
    setError(null);
    try {
      const response = await apiFetch<AnalyzeResponse>("/analyze", token, {
        method: "POST",
        body: JSON.stringify({ codigo: code, linguagem: language }),
      });
      setResult(response);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro inesperado");
    } finally {
      setIsLoading(false);
    }
  }

  const showIdlePanel = !isLoading && !result && !error;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5 px-6 py-10">
      <header>
        <p className="font-mono text-sm uppercase tracking-[0.2em] text-signal">
          Novo diagnóstico
        </p>
        <h1 className="mt-1 font-display text-2xl font-semibold text-ink">
          Analisar código
        </h1>
      </header>

      <CodeInput
        code={code}
        language={language}
        onCodeChange={setCode}
        onLanguageChange={setLanguage}
      />

      <button
        type="button"
        onClick={handleAnalyze}
        disabled={isLoading || code.trim().length === 0}
        className="inline-flex cursor-pointer items-center gap-2.5 self-start rounded-[3px] bg-signal px-5 py-2.5 font-mono text-sm font-medium uppercase tracking-wide text-on-signal transition-colors hover:bg-signal-dark disabled:cursor-not-allowed disabled:bg-line disabled:text-ink-muted"
      >
        {isLoading && <Spinner />}
        {isLoading ? "Analisando" : "Analisar"}
      </button>

      {error && (
        <p
          role="alert"
          className="rounded-sm border border-line border-l-4 border-l-crimson bg-paper-raised px-4 py-3 text-base text-ink"
        >
          <span className="mr-2 font-mono text-xs uppercase tracking-wide text-crimson">
            Erro
          </span>
          {error}
        </p>
      )}

      {isLoading && (
        <div className="flex items-center gap-3 rounded-sm border border-dashed border-line px-5 py-8 text-center">
          <Spinner label="Executando análise com IA..." className="mx-auto" />
        </div>
      )}

      {showIdlePanel && (
        <div className="rounded-sm border border-dashed border-line px-6 py-10 text-center">
          <p className="font-mono text-xs uppercase tracking-wide text-ink-muted">
            Aguardando entrada
          </p>
          <p className="mt-2 text-base text-ink-muted">
            Cole um trecho de código ou carregue um arquivo, depois clique em
            Analisar.
          </p>
        </div>
      )}

      <AnalysisResult result={result} />
    </div>
  );
}
