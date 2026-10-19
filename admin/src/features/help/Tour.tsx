import { useEffect, useState } from "react";
import { hp } from "../../text/help";
import { Dialog } from "../../ui/Dialog";

const HIGHLIGHT = "tour-target";

interface Props {
  onDone: () => void;
}

/** Tour di 5 passi (D-08, D-133): una finestra in un angolo; l'elemento di cui si parla
 * viene evidenziato con una classe (niente posizioni calcolate: la CSP non ammette stili). */
export function Tour({ onDone }: Props) {
  const [index, setIndex] = useState(0);
  const step = hp.steps[index]!;
  const last = index === hp.steps.length - 1;

  useEffect(() => {
    const target = step.target ? document.querySelector<HTMLElement>(step.target) : null;
    target?.classList.add(HIGHLIGHT);
    target?.scrollIntoView?.({ block: "nearest" });
    return () => target?.classList.remove(HIGHLIGHT);
  }, [step]);

  return (
    <Dialog key={index} title={step.title} onClose={onDone} corner>
      <p className="hint">{hp.tour.step(index + 1, hp.steps.length)}</p>
      <p>{step.text}</p>
      <div className="form__actions">
        {last ? (
          <button type="button" className="button button--primary" onClick={onDone} data-autofocus="">
            {hp.tour.done}
          </button>
        ) : (
          <button type="button" className="button button--primary" onClick={() => setIndex(index + 1)} data-autofocus="">
            {hp.tour.next}
          </button>
        )}
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
