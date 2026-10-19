import { useEffect, useRef, useState } from "react";
import { hp } from "../../text/help";
import { Dialog } from "../../ui/Dialog";

const HIGHLIGHT = "tour-target";

interface Props {
  onDone: () => void;
}

/** Evidenzia l'elemento del passo, anche se compare dopo (es. l'albero ancora in caricamento). */
function useHighlight(selector: string | null) {
  useEffect(() => {
    if (!selector) return;
    let target: HTMLElement | null = null;
    const apply = () => {
      const found = document.querySelector<HTMLElement>(selector);
      if (found !== target) {
        target?.classList.remove(HIGHLIGHT);
        target = found;
        target?.scrollIntoView?.({ block: "nearest" });
      }
      if (target && !target.classList.contains(HIGHLIGHT)) target.classList.add(HIGHLIGHT);
    };
    apply();
    // React può riscrivere la classe o rifare l'elemento: si rimette l'evidenza.
    const observer = new MutationObserver(apply);
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["class"] });
    return () => {
      observer.disconnect();
      target?.classList.remove(HIGHLIGHT);
    };
  }, [selector]);
}

/** Tour di 5 passi (D-08, D-133): una sola finestra in un angolo per tutto il giro (il focus
 * non torna alla pagina tra un passo e l'altro); l'elemento di cui si parla è evidenziato
 * con una classe (niente posizioni calcolate: la CSP non ammette stili). */
export function Tour({ onDone }: Props) {
  const [index, setIndex] = useState(0);
  const primary = useRef<HTMLButtonElement>(null);
  const step = hp.steps[index]!;
  const last = index === hp.steps.length - 1;
  useHighlight(step.target);

  useEffect(() => {
    primary.current?.focus(); // il pulsante principale del passo nuovo
  }, [index]);

  return (
    <Dialog title={step.title} onClose={onDone} corner>
      <div aria-live="polite">
        <p className="hint">{hp.tour.step(index + 1, hp.steps.length)}</p>
        <p>{step.text}</p>
      </div>
      <div className="form__actions">
        <button
          ref={primary}
          type="button"
          className="button button--primary"
          onClick={() => (last ? onDone() : setIndex(index + 1))}
          data-autofocus=""
        >
          {last ? hp.tour.done : hp.tour.next}
        </button>
        {index > 0 && (
          <button type="button" className="button" onClick={() => setIndex(index - 1)}>
            {hp.tour.back}
          </button>
        )}
        {!last && (
          <button type="button" className="button button--ghost" onClick={onDone}>
            {hp.tour.skip}
          </button>
        )}
      </div>
    </Dialog>
  );
}
