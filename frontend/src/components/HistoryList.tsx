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
    return <p>Nenhuma analise ainda.</p>;
  }

  return (
    <ul>
      {items.map((item) => (
        <li key={item.id}>
          <button type="button" onClick={() => onSelect(item.id)}>
            [{item.language}] {new Date(item.created_at).toLocaleString()} —{" "}
            {item.code_snippet.slice(0, 60)}
          </button>
        </li>
      ))}
    </ul>
  );
}
