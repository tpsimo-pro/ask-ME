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
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      aria-label="Linguagem"
      className="rounded-[3px] cursor-pointer border border-line bg-paper-raised px-2.5 py-1.5 font-mono text-sm text-ink focus-visible:border-signal focus-visible:outline-none"
    >
      {LANGUAGES.map((language) => (
        <option key={language} value={language}>
          {language}
        </option>
      ))}
    </select>
  );
}
