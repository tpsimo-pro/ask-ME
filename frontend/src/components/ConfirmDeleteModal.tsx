import { useEffect, useRef } from "react";

interface ConfirmDeleteModalProps {
  isOpen: boolean;
  title?: string;
  description?: string;
  isDeleting?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Reusable destructive-action confirmation modal, styled with the app's
 * design-system tokens so it follows light/dark automatically (no
 * hardcoded black/white). Replaces `window.confirm` for the history
 * delete flow, but is generic enough to reuse for any other destructive
 * action.
 */
export function ConfirmDeleteModal({
  isOpen,
  title = "Confirmar Exclusão?",
  description = "Esta ação não pode ser desfeita.",
  isDeleting = false,
  onConfirm,
  onCancel,
}: ConfirmDeleteModalProps) {
  const cancelButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isOpen) return;

    const previouslyFocused = document.activeElement as HTMLElement | null;
    cancelButtonRef.current?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onCancel();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      previouslyFocused?.focus();
    };
  }, [isOpen, onCancel]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4"
      onClick={onCancel}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-delete-title"
        onClick={(event) => event.stopPropagation()}
        className="w-full max-w-sm rounded-sm border border-line bg-paper-raised px-6 py-6 shadow-lg"
      >
        <h2
          id="confirm-delete-title"
          className="font-display text-2xl font-semibold text-ink sm:text-3xl"
        >
          {title}
        </h2>
        <p className="mt-3 text-base text-ink-muted">{description}</p>

        <div className="mt-8 flex items-center justify-between">
          <button
            ref={cancelButtonRef}
            type="button"
            disabled={isDeleting}
            onClick={onCancel}
            className="font-mono text-sm uppercase tracking-wide text-ink transition-colors duration-150 ease-out hover:text-ink-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal/60 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Cancelar
          </button>
          <button
            type="button"
            disabled={isDeleting}
            onClick={onConfirm}
            className="rounded-sm border border-crimson/40 bg-crimson/10 px-4 py-2 font-mono text-sm uppercase tracking-wide text-crimson transition-colors duration-150 ease-out hover:bg-crimson/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-crimson/60 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isDeleting ? "Apagando…" : "Confirmar"}
          </button>
        </div>
      </div>
    </div>
  );
}
