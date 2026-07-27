interface FormErrorProps {
  message: string;
}

export function FormError({ message }: FormErrorProps) {
  return (
    <p role="alert" className="font-mono text-xs text-red-500">
      {message}
    </p>
  );
}
