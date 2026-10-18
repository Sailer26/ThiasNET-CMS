import { useEffect, useId, useRef, type ReactNode } from "react";

interface Props {
  title: string;
  onClose: () => void;
  children: ReactNode;
}

/** Finestra modale nativa: focus intrappolato e Esc gestiti dal browser. */
export function Dialog({ title, onClose, children }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
    return () => {
      if (dialog?.open) dialog.close();
    };
  }, []);

  return (
    <dialog
      ref={ref}
      className="dialog"
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
