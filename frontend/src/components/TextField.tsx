interface TextFieldProps {
  id: string;
  label: string;
  type: "text" | "email" | "password";
  value: string;
  onChange: (value: string) => void;
  autoComplete?: string;
  required?: boolean;
}

export function TextField({
  id,
  label,
  type,
  value,
  onChange,
  autoComplete,
  required = true,
}: TextFieldProps) {
  return (
    <label htmlFor={id} className="flex flex-col gap-1.5">
      <span className="font-mono text-xs uppercase tracking-wider text-ink-muted">{label}</span>
      <input
        id={id}
        type={type}
        value={value}
        required={required}
        autoComplete={autoComplete}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-[3px] border border-line bg-paper px-3 py-2 font-sans text-base text-ink outline-none transition-colors focus:border-ink"
      />
    </label>
  );
}
