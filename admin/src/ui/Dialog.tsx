import { useEffect, useId, useRef, type ReactNode } from "react";

interface Props {
  title: string;
  onClose: () => void;
  children: ReactNode;
  /** Sfondo coprente: quello che c'è dietro non si legge (sessione scaduta). */
  opaque?: boolean;
}

/** Elemento che riceve il focus all'apertura (es. "Annulla" nelle conferme distruttive). */
export const AUTOFOCUS = "data-autofocus";

function restoreFocus(previous: Element | null) {
  if (previous instanceof HTMLElement && previous.isConnected) {
    previous.focus();
    return;
  }
  // L'elemento di partenza non c'è più (es. riga cestinata): il titolo della schermata.
  document.querySelector<HTMLElement>("main h1")?.focus();
}

/** Finestra modale nativa: focus intrappolato dal browser, ritorno del focus da qui. */
export function Dialog({ title, onClose, children, opaque = false }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    const previous = document.activeElement;
    if (dialog && !dialog.open) dialog.showModal();
    dialog?.querySelector<HTMLElement>(`[${AUTOFOCUS}]`)?.focus();
    return () => {
      if (dialog?.open) dialog.close();
      restoreFocus(previous);
    };
  }, []);

  return (
    <dialog
      ref={ref}
      className={opaque ? "dialog dialog--opaque" : "dialog"}
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault(); // Esc: decide chi ha aperto la finestra
        onClose();
      }}
    >
      <h2 id={titleId} className="dialog__title">
        {title}
      </h2>
      {children}
    </dialog>
  );
}
