import { AnalysisResult } from "./AnalysisResult";

interface HistoryItem {
  id: string;
  language: string;
  code_snippet: string;
  created_at: string;
}

interface AnalysisResultData {
  sugestoes: string[];
  testes_gerados: string;
  riscos_seguranca: string[];
}

interface HistoryListProps {
  items: HistoryItem[];
  expandedId: string | null;
  detailsById: Record<string, AnalysisResultData>;
  loadingId: string | null;
  errorId: string | null;
  deletingId: string | null;
  deleteErrorId: string | null;
  onToggle: (id: string) => void;
  onDelete: (id: string) => void;
}

export function HistoryList({
  items,
  expandedId,
  detailsById,
  loadingId,
  errorId,
  deletingId,
  deleteErrorId,
  onToggle,
  onDelete,
}: HistoryListProps) {
  if (items.length === 0) {
    return (
      <div className="rounded-sm border border-dashed border-line px-6 py-12 text-center">
        <p className="font-mono text-xs uppercase tracking-wide text-ink-muted">
          Registro vazio
        </p>
        <p className="mt-2 text-base text-ink-muted">
          Nenhuma análise ainda. Suas execuções aparecerão aqui.
        </p>
      </div>
    );
  }

  return (
    <ul className="flex flex-col divide-y divide-line overflow-hidden rounded-sm border border-line bg-paper-raised">
      {items.map((item) => {
        const isExpanded = expandedId === item.id;
        const isLoading = isExpanded && loadingId === item.id;
        const hasError = isExpanded && errorId === item.id;
        const isDeleting = deletingId === item.id;
        const hasDeleteError = isExpanded && deleteErrorId === item.id;
        const detail = detailsById[item.id];

        return (
          <li key={item.id}>
            <button
              type="button"
              onClick={() => onToggle(item.id)}
              aria-expanded={isExpanded}
              className={`group flex w-full flex-wrap items-center gap-x-3 gap-y-1 border-l-4 px-4 py-3 text-left transition-all duration-150 ease-out focus-visible:bg-paper focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal/60 focus-visible:ring-inset ${
                isExpanded
                  ? "border-l-signal bg-paper shadow-[inset_0_0_0_9999px_rgba(0,0,0,0.015)]"
                  : "border-l-transparent hover:border-l-signal/70 hover:bg-paper hover:shadow-[inset_0_1px_0_0_rgba(0,0,0,0.03)]"
              }`}
            >
              <span
                className={`rounded-[3px] border border-line bg-paper px-1.5 py-0.5 font-mono text-xs uppercase text-signal transition-colors ${
                  isExpanded ? "border-signal/40" : ""
                }`}
              >
                {item.language}
              </span>
              <span className="font-mono text-sm text-ink-muted">
                {new Date(item.created_at).toLocaleString("pt-BR")}
              </span>
              <span className="w-full truncate font-mono text-sm text-ink-muted/80 sm:ml-auto sm:w-auto">
                {item.code_snippet.slice(0, 60)}
              </span>
              <span
                aria-hidden="true"
                className={`ml-auto hidden shrink-0 font-mono text-sm text-signal transition-transform duration-150 sm:inline-block ${
                  isExpanded ? "rotate-90" : "rotate-0"
                }`}
              >
                &gt;
              </span>
            </button>

            {isExpanded && (
              <div className="border-t border-line bg-paper px-4 py-5">
                {isLoading && (
                  <p className="font-mono text-xs uppercase tracking-wide text-ink-muted">
                    Carregando análise…
                  </p>
                )}
                {hasError && (
                  <p
                    role="alert"
                    className="rounded-sm border border-line border-l-4 border-l-crimson bg-paper-raised px-4 py-3 text-base text-ink"
                  >
                    <span className="mr-2 font-mono text-xs uppercase tracking-wide text-crimson">
                      Erro
                    </span>
                    Não foi possível carregar esta análise.
                  </p>
                )}
                {!isLoading && !hasError && detail && (
                  <AnalysisResult result={detail} />
                )}

                {!isLoading && (
                  <div className="mt-6">
                    {hasDeleteError && (
                      <p
                        role="alert"
                        className="mb-3 rounded-sm border border-line border-l-4 border-l-crimson bg-paper-raised px-4 py-3 text-base text-ink"
                      >
                        <span className="mr-2 font-mono text-xs uppercase tracking-wide text-crimson">
                          Erro
                        </span>
                        Não foi possível apagar esta análise.
                      </p>
                    )}
                    <button
                      type="button"
                      aria-label="Apagar esta análise"
                      disabled={isDeleting}
                      onClick={() => onDelete(item.id)}
                      className="group/delete relative inline-block cursor-pointer bg-transparent px-0 py-1 font-mono text-sm uppercase tracking-wide text-crimson transition-colors duration-150 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-crimson/60 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {isDeleting ? "Apagando…" : "Apagar esta análise"}
                      <span
                        aria-hidden="true"
                        className="absolute inset-x-0 bottom-0 h-[3px] origin-center scale-x-0 bg-crimson transition-transform duration-700 ease-out group-hover/delete:scale-x-100 group-focus-visible/delete:scale-x-100"
                      />
                    </button>
                  </div>
                )}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
