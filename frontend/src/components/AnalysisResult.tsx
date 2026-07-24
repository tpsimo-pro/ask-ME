import { PrismLight as SyntaxHighlighter } from "react-syntax-highlighter";
import cpp from "react-syntax-highlighter/dist/esm/languages/prism/cpp";
import csharp from "react-syntax-highlighter/dist/esm/languages/prism/csharp";
import go from "react-syntax-highlighter/dist/esm/languages/prism/go";
import java from "react-syntax-highlighter/dist/esm/languages/prism/java";
import javascript from "react-syntax-highlighter/dist/esm/languages/prism/javascript";
import php from "react-syntax-highlighter/dist/esm/languages/prism/php";
import python from "react-syntax-highlighter/dist/esm/languages/prism/python";
import ruby from "react-syntax-highlighter/dist/esm/languages/prism/ruby";
import typescript from "react-syntax-highlighter/dist/esm/languages/prism/typescript";
import { oneDark, oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";

import { useTheme } from "../context/ThemeContext";

SyntaxHighlighter.registerLanguage("javascript", javascript);
SyntaxHighlighter.registerLanguage("typescript", typescript);
SyntaxHighlighter.registerLanguage("python", python);
SyntaxHighlighter.registerLanguage("java", java);
SyntaxHighlighter.registerLanguage("go", go);
SyntaxHighlighter.registerLanguage("csharp", csharp);
SyntaxHighlighter.registerLanguage("cpp", cpp);
SyntaxHighlighter.registerLanguage("ruby", ruby);
SyntaxHighlighter.registerLanguage("php", php);

interface AnalysisResultData {
  sugestoes: string[];
  testes_gerados: string;
  riscos_seguranca: string[];
}

interface AnalysisResultProps {
  result: AnalysisResultData | null;
  language?: string;
}

export function AnalysisResult({ result, language }: AnalysisResultProps) {
  const { theme } = useTheme();
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
        <div className="max-h-96 overflow-y-auto rounded-sm border border-line text-sm">
          <SyntaxHighlighter
            language={language ?? "text"}
            style={theme === "dark" ? oneDark : oneLight}
            wrapLongLines
            customStyle={{
              margin: 0,
              padding: "1rem",
              borderRadius: 0,
              fontSize: "0.875rem",
            }}
            codeTagProps={{ style: { fontFamily: "inherit" } }}
          >
            {result.testes_gerados}
          </SyntaxHighlighter>
        </div>
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
