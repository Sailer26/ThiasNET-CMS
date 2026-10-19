import { useEffect, useId, useRef, useState } from "react";
import { hp } from "../../text/help";

interface Props {
  onAsk: () => void;
  onTour: () => void;
}

/** Menu Aiuto nella testata (D-133, D-134): un pulsante che apre due scelte. */
export function HelpMenu({ onAsk, onTour }: Props) {
  const [open, setOpen] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const id = useId();

  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent | MouseEvent) => {
      if (event instanceof KeyboardEvent) {
        if (event.key !== "Escape") return;
        toggle.current?.focus();
      } else if (box.current?.contains(event.target as Node)) return;
      setOpen(false);
    };
    document.addEventListener("keydown", close);
    document.addEventListener("mousedown", close);
    return () => {
      document.removeEventListener("keydown", close);
      document.removeEventListener("mousedown", close);
    };
  }, [open]);

  const choose = (action: () => void) => () => {
    setOpen(false);
    action();
  };

  return (
    <div className="help-menu" ref={box} data-tour="help">
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
      {open && (
        <ul id={id} className="help-menu__list">
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
      )}
    </div>
  );
}
