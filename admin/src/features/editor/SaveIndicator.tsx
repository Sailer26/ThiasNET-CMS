import { ed } from "../../text/editor";
import type { SaveState } from "./model/autosave";

function clock(date: Date): string {
  const two = (n: number) => String(n).padStart(2, "0");
  return `${two(date.getHours())}:${two(date.getMinutes())}`;
}

/** Scritta piccola in alto (D-104): salvato, sto salvando, o un avviso rosso. */
export function SaveIndicator({ state, onRetry }: { state: SaveState; onRetry: () => void }) {
  let text: string;
  let bad = false;
  switch (state.kind) {
    case "saved":
      text = state.at ? ed.save.savedAt(clock(state.at)) : ed.save.saved;
      break;
    case "pending":
    case "saving":
      text = ed.save.saving;
      break;
    case "error":
      text = ed.save.error(state.message);
      bad = true;
      break;
    case "expired":
      text = ed.save.expired;
      bad = true;
      break;
    case "conflict":
      text = ed.save.conflict;
      bad = true;
      break;
  }
  return (
    <span className={`save${bad ? " save--bad" : ""}`} role="status">
      {text}
      {state.kind === "error" && (
        <button type="button" className="button button--small" onClick={onRetry}>
          {ed.save.retry}
        </button>
      )}
    </span>
  );
}
