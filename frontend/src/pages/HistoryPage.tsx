import { useEffect, useState } from "react";

import { ApiError, apiFetch } from "../api/client";
import { ConfirmDeleteModal } from "../components/ConfirmDeleteModal";
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
  const [error, setError] = useState<string | null>(null);

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detailsById, setDetailsById] = useState<Record<string, AnalyzeResponse>>({});
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [errorId, setErrorId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteErrorId, setDeleteErrorId] = useState<string | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<HistoryItem[]>("/history", token)
      .then(setItems)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Erro inesperado"));
  }, [token]);

  async function handleToggle(id: string) {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }

    setExpandedId(id);
    setErrorId((current) => (current === id ? null : current));

    if (detailsById[id]) return;

    setLoadingId(id);
    try {
      const detail = await apiFetch<AnalyzeResponse>(`/history/${id}`, token);
      setDetailsById((current) => ({ ...current, [id]: detail }));
    } catch {
      setErrorId(id);
    } finally {
      setLoadingId((current) => (current === id ? null : current));
    }
  }

  function handleRequestDelete(id: string) {
    setPendingDeleteId(id);
  }

  function handleCancelDelete() {
    setPendingDeleteId(null);
  }

  async function handleConfirmDelete() {
    const id = pendingDeleteId;
    if (!id) return;

    setDeleteErrorId((current) => (current === id ? null : current));
    setDeletingId(id);
    try {
      await apiFetch<void>(`/history/${id}`, token, { method: "DELETE" });
      setItems((current) => current.filter((item) => item.id !== id));
      setDetailsById((current) => {
        const { [id]: _removed, ...rest } = current;
        return rest;
      });
      setExpandedId((current) => (current === id ? null : current));
      setErrorId((current) => (current === id ? null : current));
      setPendingDeleteId(null);
    } catch {
      setDeleteErrorId(id);
      setPendingDeleteId(null);
    } finally {
      setDeletingId((current) => (current === id ? null : current));
    }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5 px-6 py-10">
      <header>
        <p className="font-mono text-sm uppercase tracking-[0.2em] text-signal">
          Registro de execuções
        </p>
        <h1 className="mt-1 font-display text-2xl font-semibold text-ink">Histórico</h1>
      </header>

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

      <HistoryList
        items={items}
        expandedId={expandedId}
        detailsById={detailsById}
        loadingId={loadingId}
        errorId={errorId}
        deletingId={deletingId}
        deleteErrorId={deleteErrorId}
        onToggle={handleToggle}
        onDelete={handleRequestDelete}
      />

      <ConfirmDeleteModal
        isOpen={pendingDeleteId !== null}
        description="Apagar esta análise do histórico? Esta ação não pode ser desfeita."
        isDeleting={deletingId !== null && deletingId === pendingDeleteId}
        onConfirm={handleConfirmDelete}
        onCancel={handleCancelDelete}
      />
    </div>
  );
}
