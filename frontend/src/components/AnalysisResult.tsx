interface AnalysisResultData {
  sugestoes: string[];
  testes_gerados: string;
  riscos_seguranca: string[];
}

interface AnalysisResultProps {
  result: AnalysisResultData | null;
}

export function AnalysisResult({ result }: AnalysisResultProps) {
  if (!result) return null;

  return (
    <div className="flex flex-col gap-4">
      <section className="rounded-md border border-slate-200 p-4">
        <h3 className="mb-2 text-sm font-semibold text-slate-900">Sugestões</h3>
        <ul className="list-inside list-disc space-y-1 text-sm text-slate-700">
          {result.sugestoes.map((item, index) => (
            <li key={index}>{item}</li>
          ))}
        </ul>
      </section>
      <section className="rounded-md border border-slate-200 p-4">
        <h3 className="mb-2 text-sm font-semibold text-slate-900">Testes Gerados</h3>
        <pre className="overflow-x-auto rounded-md bg-slate-50 p-3 font-mono text-sm text-slate-800">
          {result.testes_gerados}
        </pre>
      </section>
      <section className="rounded-md border border-slate-200 p-4">
        <h3 className="mb-2 text-sm font-semibold text-slate-900">Riscos de Segurança</h3>
        <ul className="list-inside list-disc space-y-1 text-sm text-slate-700">
          {result.riscos_seguranca.map((item, index) => (
            <li key={index}>{item}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
