import { useState } from "react";

import { ApiError, apiFetch } from "../api/client";
import { AnalysisResult } from "../components/AnalysisResult";
import { CodeInput } from "../components/CodeInput";
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

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 px-6 py-8">
      <h1 className="text-lg font-semibold text-slate-900">Analisar código</h1>
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
        className="self-start rounded-md bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        {isLoading ? "Analisando..." : "Analisar"}
      </button>
      {error && (
        <p role="alert" className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
      <AnalysisResult result={result} />
    </div>
  );
}
