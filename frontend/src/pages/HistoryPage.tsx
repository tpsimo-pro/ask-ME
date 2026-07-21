import { useEffect, useState } from "react";

import { apiFetch } from "../api/client";
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

  useEffect(() => {
    apiFetch<HistoryItem[]>("/history", token).then(setItems);
  }, [token]);

  async function handleSelect(id: string) {
    const detail = await apiFetch<AnalyzeResponse>(`/history/${id}`, token);
    setSelected(detail);
  }

  return (
    <div>
      <HistoryList items={items} onSelect={handleSelect} />
      <AnalysisResult result={selected} />
    </div>
  );
}
