import { useRef, useState, type KeyboardEvent, type MouseEvent } from "react";
import { mt } from "../../text/media";
import { focalFromClick, focalFromKey, focalText, type Focal } from "./focal";

interface Props {
  src: string;
  initial: Focal;
  busy: boolean;
  onSave: (focal: Focal) => void;
}

/** Punto focale (D-119): clic o tocco sulla foto, frecce sul segno, due esempi di taglio.
 * Le posizioni vanno al CSS via proprietà impostate da JS (CSSOM), ammesse dalla CSP. */
export function FocalPointPicker({ src, initial, busy, onSave }: Props) {
  const [focal, setFocal] = useState<Focal>(initial);
  const frame = useRef<HTMLDivElement>(null);
  const changed = focal.x !== initial.x || focal.y !== initial.y;
  const position = `${focal.x}% ${focal.y}%`;

  function click(event: MouseEvent<HTMLDivElement>) {
    if (!frame.current) return;
    setFocal(focalFromClick(event.clientX, event.clientY, frame.current.getBoundingClientRect()));
  }

  function key(event: KeyboardEvent<HTMLButtonElement>) {
    const next = focalFromKey(focal, event.key, event.shiftKey);
    if (!next) return;
    event.preventDefault();
    setFocal(next);
  }

  return (
    <div className="focal">
      <p className="hint">{mt.focalHelp}</p>
      <div className="focal__frame" ref={frame} onClick={click}>
        <img src={src} alt="" draggable={false} />
        <button
          type="button"
          className="focal__marker"
          role="slider"
          aria-label={mt.focalMarker}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={focal.x}
          aria-valuetext={focalText(focal)}
          style={{ left: `${focal.x}%`, top: `${focal.y}%` }}
          onKeyDown={key}
          onClick={(event) => event.stopPropagation()}
        />
      </div>
      <div className="focal__examples">
        <figure>
          <img src={src} alt="" className="focal__square" style={{ objectPosition: position }} />
          <figcaption>{mt.focalSquare}</figcaption>
        </figure>
        <figure>
          <img src={src} alt="" className="focal__wide" style={{ objectPosition: position }} />
          <figcaption>{mt.focalWide}</figcaption>
        </figure>
      </div>
      <div className="form__actions">
        <button type="button" className="button button--primary" disabled={!changed || busy} onClick={() => onSave(focal)}>
          {busy ? mt.preparing : mt.focalSave}
        </button>
        <button type="button" className="button" disabled={!changed || busy} onClick={() => setFocal(initial)}>
          {mt.focalReset}
        </button>
      </div>
    </div>
  );
}
