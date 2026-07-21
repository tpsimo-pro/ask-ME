const LANGUAGES = [
  "javascript",
  "typescript",
  "python",
  "java",
  "go",
  "csharp",
  "cpp",
  "ruby",
  "php",
];

interface LanguageSelectProps {
  value: string;
  onChange: (value: string) => void;
}

export function LanguageSelect({ value, onChange }: LanguageSelectProps) {
  return (
    <select value={value} onChange={(event) => onChange(event.target.value)} aria-label="Linguagem">
      {LANGUAGES.map((language) => (
        <option key={language} value={language}>
          {language}
        </option>
      ))}
    </select>
  );
}
