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
    <div>
      <section>
        <h3>Sugestoes</h3>
        <ul>
          {result.sugestoes.map((item, index) => (
            <li key={index}>{item}</li>
          ))}
        </ul>
      </section>
      <section>
        <h3>Testes Gerados</h3>
        <pre>{result.testes_gerados}</pre>
      </section>
      <section>
        <h3>Riscos de Seguranca</h3>
        <ul>
          {result.riscos_seguranca.map((item, index) => (
            <li key={index}>{item}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
