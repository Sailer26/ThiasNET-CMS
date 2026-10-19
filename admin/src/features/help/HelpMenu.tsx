import { useEffect, useId, useRef, useState, type FocusEvent } from "react";
import { hp } from "../../text/help";

interface Props {
  onAsk: () => void;
  onTour: () => void;
}

/** Menu Aiuto nella testata (D-133, D-134): un pulsante che mostra due scelte (disclosure). */
export function HelpMenu({ onAsk, onTour }: Props) {
  const [open, setOpen] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const id = useId();

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      toggle.current?.focus();
      setOpen(false);
    };
    const onPointer = (event: MouseEvent) => {
      if (event.target instanceof Node && box.current?.contains(event.target)) return;
      setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onPointer);
    };
  }, [open]);

  // La finestra che si apre riporterà il focus su "Aiuto" quando si chiude.
  const choose = (action: () => void) => () => {
    toggle.current?.focus();
    setOpen(false);
    action();
  };

  // Con Tab si esce dal menu: si chiude.
  function leave(event: FocusEvent<HTMLDivElement>) {
    const next = event.relatedTarget;
    if (next instanceof Node && !event.currentTarget.contains(next)) setOpen(false);
  }

  return (
    <div className="help-menu" ref={box} data-tour="help" onBlur={leave}>
      <button
        ref={toggle}
        type="button"
        className="button button--ghost"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen(!open)}
      >
        {hp.menu}
      </button>
      <ul id={id} className="help-menu__list" hidden={!open}>
        <li>
          <button type="button" className="button button--ghost" onClick={choose(onAsk)}>
            {hp.ask}
          </button>
        </li>
        <li>
          <button type="button" className="button button--ghost" onClick={choose(onTour)}>
            {hp.retour}
          </button>
        </li>
      </ul>
    </div>
  );
}
