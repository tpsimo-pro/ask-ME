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
    <div>
      <CodeInput
        code={code}
        language={language}
        onCodeChange={setCode}
        onLanguageChange={setLanguage}
      />
      <button type="button" onClick={handleAnalyze} disabled={isLoading || code.trim().length === 0}>
        {isLoading ? "Analisando..." : "Analisar"}
      </button>
      {error && <p role="alert">{error}</p>}
      <AnalysisResult result={result} />
    </div>
  );
}
