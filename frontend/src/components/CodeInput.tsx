import { ChangeEvent } from "react";

import { LanguageSelect } from "./LanguageSelect";

interface CodeInputProps {
  code: string;
  language: string;
  onCodeChange: (code: string) => void;
  onLanguageChange: (language: string) => void;
}

export function CodeInput({ code, language, onCodeChange, onLanguageChange }: CodeInputProps) {
  async function handleFileUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    onCodeChange(text);
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-4">
        <LanguageSelect value={language} onChange={onLanguageChange} />
        <label className="cursor-pointer text-sm text-indigo-600 hover:text-indigo-500">
          Carregar arquivo
          <input
            type="file"
            onChange={handleFileUpload}
            aria-label="Carregar arquivo de codigo"
            className="hidden"
          />
        </label>
      </div>
      <textarea
        value={code}
        onChange={(event) => onCodeChange(event.target.value)}
        placeholder="Cole seu codigo aqui"
        rows={20}
        aria-label="Codigo"
        className="w-full rounded-md border border-slate-300 bg-slate-50 p-4 font-mono text-sm text-slate-800 focus:border-indigo-500 focus:outline-none"
      />
    </div>
  );
}
