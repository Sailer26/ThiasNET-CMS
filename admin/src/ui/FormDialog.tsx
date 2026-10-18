import type { FormEvent, ReactNode } from "react";
import { it } from "../text/it";
import { Dialog } from "./Dialog";
import { useAction } from "./useAction";

interface Props {
  title: string;
  submitLabel: string;
  onSubmit: () => Promise<void>;
  onClose: () => void;
  canSubmit?: boolean;
  danger?: boolean;
  children?: ReactNode;
}

/** Finestra con un modulo: Annulla, conferma, errore del server accanto ai pulsanti. */
export function FormDialog({
  title,
  submitLabel,
  onSubmit,
  onClose,
  canSubmit = true,
  danger = false,
  children,
}: Props) {
  const { busy, error, run } = useAction();

  function submit(event: FormEvent) {
    event.preventDefault();
    void run(onSubmit);
  }

  return (
    <Dialog title={title} onClose={onClose}>
      <form className="form" onSubmit={submit} noValidate>
        {children}
        {error && <p className="form__error" role="alert">{error}</p>}
        <div className="form__actions">
          <button
            type="submit"
            className={`button ${danger ? "button--danger" : "button--primary"}`}
            disabled={busy || !canSubmit}
          >
            {submitLabel}
          </button>
          <button type="button" className="button" onClick={onClose} disabled={busy}>
            {it.dialog.cancel}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
