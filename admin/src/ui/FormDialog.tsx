import type { FormEvent, ReactNode } from "react";
import { it } from "../text/it";
import { AUTOFOCUS, Dialog } from "./Dialog";
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

/** Finestra con un modulo: Annulla, conferma, errore del server accanto ai pulsanti.
 * Nelle conferme distruttive il focus parte da "Annulla": un Invio distratto non cancella nulla. */
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

  function close() {
    if (!busy) onClose(); // durante l'invio né Esc né Annulla: l'azione arriverebbe comunque
  }

  const cancelFocus = danger ? { [AUTOFOCUS]: "" } : {};

  return (
    <Dialog title={title} onClose={close}>
      <form className="form" onSubmit={submit} noValidate>
        {children}
        {error && (
          <p className="form__error" role="alert">
            {error}
          </p>
        )}
        <div className="form__actions">
          <button
            type="submit"
            className={`button ${danger ? "button--danger" : "button--primary"}`}
            disabled={busy || !canSubmit}
          >
            {submitLabel}
          </button>
          <button type="button" className="button" onClick={close} disabled={busy} {...cancelFocus}>
            {it.dialog.cancel}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
