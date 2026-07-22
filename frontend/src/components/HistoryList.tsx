interface HistoryItem {
  id: string;
  language: string;
  code_snippet: string;
  created_at: string;
}

interface HistoryListProps {
  items: HistoryItem[];
  onSelect: (id: string) => void;
}

export function HistoryList({ items, onSelect }: HistoryListProps) {
  if (items.length === 0) {
    return <p className="text-sm text-slate-500">Nenhuma análise ainda.</p>;
  }

  return (
    <ul className="flex flex-col gap-2">
      {items.map((item) => (
        <li key={item.id}>
          <button
            type="button"
            onClick={() => onSelect(item.id)}
            className="w-full rounded-md border border-slate-200 px-4 py-2.5 text-left text-sm hover:border-indigo-400 hover:bg-indigo-50"
          >
            <span className="mr-2 rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-600">
              {item.language}
            </span>
            <span className="text-slate-500">{new Date(item.created_at).toLocaleString()}</span>
            <span className="ml-2 font-mono text-slate-700">
              {item.code_snippet.slice(0, 60)}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
