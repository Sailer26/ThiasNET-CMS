import { useId, useState } from "react";
import { ed } from "../../../text/editor";
import type { Data } from "../model/document";
import { placeFromLink, videoFromLink } from "./pasteLinks";

const HELPERS: Record<string, { label: string; help: string; read: (text: string) => Data | null }> = {
  video: { label: ed.paste.videoLabel, help: ed.paste.videoHelp, read: (text) => videoFromLink(text) as Data | null },
  map: { label: ed.paste.mapLabel, help: ed.paste.mapHelp, read: (text) => placeFromLink(text) as Data | null },
};

export function hasPasteHelper(type: string): boolean {
  return Object.hasOwn(HELPERS, type);
}

/** "Incolla il link": compila i campi tecnici del blocco (D-112). */
export function PasteHelper({ type, onApply }: { type: string; onApply: (patch: Data) => void }) {
  const helper = Object.hasOwn(HELPERS, type) ? HELPERS[type] : undefined;
  const id = useId();
  const [text, setText] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  if (!helper) return null;
  function apply() {
    const patch = helper!.read(text);
    if (!patch) {
      setProblem(ed.paste.invalid);
      setDone(false);
      return;
    }
    onApply(patch);
    setProblem(null);
    setDone(true);
    setText("");
  }
  return (
    <div className="paste-helper">
      <label htmlFor={id}>{helper.label}</label>
      <div className="paste-helper__row">
        <input
          id={id}
          value={text}
          autoCapitalize="none"
          spellCheck={false}
          aria-describedby={`${id}-help`}
          onChange={(event) => {
            setText(event.target.value);
            setDone(false);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              apply();
            }
          }}
        />
        <button type="button" className="button button--small" disabled={!text.trim()} onClick={apply}>
          {ed.paste.apply}
        </button>
      </div>
      <p id={`${id}-help`} className="hint">
        {helper.help}
      </p>
      {problem && (
        <p className="form__error" role="alert">
          {problem}
        </p>
      )}
      {done && <p role="status" className="hint">{ed.paste.done}</p>}
    </div>
  );
}
