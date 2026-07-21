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
    <div>
      <LanguageSelect value={language} onChange={onLanguageChange} />
      <input type="file" onChange={handleFileUpload} aria-label="Carregar arquivo de codigo" />
      <textarea
        value={code}
        onChange={(event) => onCodeChange(event.target.value)}
        placeholder="Cole seu codigo aqui"
        rows={20}
        aria-label="Codigo"
      />
    </div>
  );
}
