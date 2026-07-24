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
    <div className="flex flex-col gap-5">
      <section className="rounded-sm border border-line border-l-4 border-l-signal bg-paper-raised p-5">
        <header className="mb-3 flex items-baseline gap-2.5">
          <span className="font-mono text-xs uppercase tracking-[0.15em] text-signal">
            Sinal
          </span>
          <h3 className="font-display text-base font-semibold text-ink">Sugestões de melhoria</h3>
        </header>
        {result.sugestoes.length === 0 ? (
          <p className="text-base text-ink-muted">Nenhuma sugestão encontrada.</p>
        ) : (
          <ul className="space-y-2 text-base leading-relaxed text-ink">
            {result.sugestoes.map((item, index) => (
              <li key={index} className="flex gap-2.5">
                <span className="mt-0.5 font-mono text-sm text-signal/70">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-sm border border-line border-l-4 border-l-amber bg-paper-raised p-5">
        <header className="mb-3 flex items-baseline gap-2.5">
          <span className="font-mono text-xs uppercase tracking-[0.15em] text-amber">
            Artefato
          </span>
          <h3 className="font-display text-base font-semibold text-ink">Testes gerados</h3>
        </header>
        <pre className="overflow-x-auto rounded-sm border border-line bg-paper p-4 font-mono text-sm leading-relaxed text-ink">
          {result.testes_gerados}
        </pre>
      </section>

      <section className="rounded-sm border border-line border-l-4 border-l-crimson bg-paper-raised p-5">
        <header className="mb-3 flex items-baseline gap-2.5">
          <span className="font-mono text-xs uppercase tracking-[0.15em] text-crimson">
            Risco
          </span>
          <h3 className="font-display text-base font-semibold text-ink">Riscos de segurança</h3>
        </header>
        {result.riscos_seguranca.length === 0 ? (
          <p className="text-base text-ink-muted">Nenhum risco identificado.</p>
        ) : (
          <ul className="space-y-2 text-base leading-relaxed text-ink">
            {result.riscos_seguranca.map((item, index) => (
              <li key={index} className="flex gap-2.5">
                <span aria-hidden="true" className="mt-0.5 text-crimson">
                  !
                </span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
