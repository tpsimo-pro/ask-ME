import { ChangeEvent, UIEvent, useRef } from "react";

import { LanguageSelect } from "./LanguageSelect";

interface CodeInputProps {
  code: string;
  language: string;
  onCodeChange: (code: string) => void;
  onLanguageChange: (language: string) => void;
}

const MIN_LINES = 20;
const PANE_MAX_HEIGHT = "22rem";

export function CodeInput({
  code,
  language,
  onCodeChange,
  onLanguageChange,
}: CodeInputProps) {
  const gutterRef = useRef<HTMLDivElement>(null);
  const lineCount = Math.max(code.split("\n").length, MIN_LINES);

  async function handleFileUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    onCodeChange(text);
  }

  // Purely cosmetic: keeps the line-number gutter aligned with the
  // textarea's own scroll position.
  function handleScroll(event: UIEvent<HTMLTextAreaElement>) {
    if (gutterRef.current) {
      gutterRef.current.scrollTop = event.currentTarget.scrollTop;
    }
  }

  return (
    <div className="overflow-hidden rounded-sm border border-line bg-paper-raised focus-within:border-signal">
      <div className="flex items-center justify-between gap-4 border-b border-line bg-paper px-4 py-2.5">
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs uppercase tracking-wide text-ink-muted">
            Linguagem
          </span>
          <LanguageSelect value={language} onChange={onLanguageChange} />
        </div>
        <label className="relative cursor-pointer rounded-[3px] px-1 font-mono text-sm uppercase tracking-wide text-signal transition-colors hover:text-signal-dark  focus-within:outline-2 focus-within:outline-signal">
          Carregar arquivo
          <input
            type="file"
            onChange={handleFileUpload}
            aria-label="Carregar arquivo de codigo"
            className="sr-only"
          />
        </label>
      </div>
      <div className="flex">
        <div
          ref={gutterRef}
          aria-hidden="true"
          className="hidden select-none overflow-hidden bg-paper px-3 py-4 text-right font-mono text-base leading-7 text-ink-muted/50 sm:block"
          style={{ maxHeight: PANE_MAX_HEIGHT }}
        >
          {Array.from({ length: lineCount }, (_, index) => (
            <div key={index}>{index + 1}</div>
          ))}
        </div>
        <textarea
          value={code}
          onChange={(event) => onCodeChange(event.target.value)}
          onScroll={handleScroll}
          placeholder="Cole seu codigo aqui"
          rows={MIN_LINES}
          aria-label="Codigo"
          spellCheck={false}
          className="w-full resize-none overflow-y-auto border-0 bg-paper-raised p-4 font-mono text-base leading-7 text-ink outline-none placeholder:text-ink-muted/60"
          style={{ maxHeight: PANE_MAX_HEIGHT }}
        />
      </div>
    </div>
  );
}
