import { useEffect, useState } from "react";

import { ApiError, apiFetch } from "../api/client";
import { AnalysisResult } from "../components/AnalysisResult";
import { HistoryList } from "../components/HistoryList";
import { useAuth } from "../context/AuthContext";

interface HistoryItem {
  id: string;
  language: string;
  code_snippet: string;
  created_at: string;
}

interface AnalyzeResponse {
  sugestoes: string[];
  testes_gerados: string;
  riscos_seguranca: string[];
}

export function HistoryPage() {
  const { token } = useAuth();
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [selected, setSelected] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<HistoryItem[]>("/history", token)
      .then(setItems)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Erro inesperado"));
  }, [token]);

  async function handleSelect(id: string) {
    try {
      const detail = await apiFetch<AnalyzeResponse>(`/history/${id}`, token);
      setSelected(detail);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro inesperado");
    }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 px-6 py-8">
      <h1 className="text-lg font-semibold text-slate-900">Histórico</h1>
      {error && (
        <p role="alert" className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
      <HistoryList items={items} onSelect={handleSelect} />
      <AnalysisResult result={selected} />
    </div>
  );
}
