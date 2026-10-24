import { useEffect, useId, useState } from "react";
import { errorMessage, isConflict } from "../../api/client";
import { fetchWidgetArea, storeWidgetArea, type WidgetAreaInfo } from "../../api/widgets";
import { wg } from "../../text/widgets";
import { FormDialog } from "../../ui/FormDialog";
import { currentNotice, NOTICE, removeWidget, setNotice } from "./model";
import { nextUntil, NO_END, UntilFields, untilFields, type Until } from "./UntilFields";

export const NOTICE_AREA = "header_top";

type State = { kind: "loading" } | { kind: "failed"; message: string } | { kind: "ready"; area: WidgetAreaInfo };

interface Props {
  onClose: () => void;
  onDone: (text: string) => void;
}

/** Banner avviso dal telefono (D-97): testo, tipo e "fino al"; va online subito. */
export function PhoneNotice({ onClose, onDone }: Props) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [text, setText] = useState("");
  const [level, setLevel] = useState("info");
  const [until, setUntil] = useState<Until>(NO_END);
  const [start, setStart] = useState<Until>(NO_END);
  const [removing, setRemoving] = useState(false);
  const [attempt, setAttempt] = useState(0); // dopo un conflitto si rilegge l'area
  const id = useId();

  useEffect(() => {
    let active = true;
    fetchWidgetArea(NOTICE_AREA).then(
      (area) => {
        if (!active) return;
        const found = currentNotice(area.items);
        setText(typeof found?.data.text === "string" ? found.data.text : "");
        setLevel(typeof found?.data.level === "string" ? found.data.level : "info");
        const fields = untilFields(found?.until);
        setStart(fields);
        setUntil(fields);
        setState({ kind: "ready", area });
      },
      (error: unknown) => {
        if (active) setState({ kind: "failed", message: errorMessage(error) });
      },
    );
    return () => {
      active = false;
    };
  }, [attempt]);

  /** Qualcuno ha salvato nel frattempo: l'errore si vede e l'area si rilegge, così si può riprovare. */
  async function store(run: () => Promise<unknown>) {
    try {
      await run();
    } catch (error) {
      if (isConflict(error)) {
        setRemoving(false);
        setState({ kind: "loading" });
        setAttempt((n) => n + 1);
      }
      throw error;
    }
  }

  const area = state.kind === "ready" ? state.area : null;
  const schema = area?.types.find((type) => type.type === NOTICE)?.schema;
  const levels = (schema?.properties?.level?.enum ?? []).map(String);
  const levelTitles = schema?.properties?.level?.["x-enum-titles"] ?? [];
  const existing = area ? currentNotice(area.items) : null;

  if (removing && area && existing) {
    return (
      <FormDialog
        title={wg.phone.removeTitle}
        submitLabel={wg.phone.remove}
        danger
        onClose={() => setRemoving(false)}
        onSubmit={async () => {
          await store(() => storeWidgetArea(NOTICE_AREA, area.version, removeWidget(area.items, existing.uid)));
          onDone(wg.phone.removed);
        }}
      >
        <p>{wg.phone.removeText}</p>
      </FormDialog>
    );
  }
  return (
    <FormDialog
      title={wg.phone.title}
      submitLabel={wg.phone.save}
      canSubmit={Boolean(area && schema && text.trim())}
      onClose={onClose}
      onSubmit={async () => {
        if (!area) return;
        const data = { ...(existing?.data ?? {}), text: text.trim(), level };
        const ends = nextUntil(until, start, existing?.until);
        await store(() => storeWidgetArea(NOTICE_AREA, area.version, setNotice(area.items, data, ends)));
        onDone(wg.phone.saved);
      }}
    >
      {state.kind === "loading" && <p role="status">{wg.loading}</p>}
      {state.kind === "failed" && <p role="alert">{state.message}</p>}
      {area && !schema && <p>{wg.phone.unavailable}</p>}
      {area && schema && (
        <>
          <div className="field">
            <label htmlFor={`${id}-text`}>{wg.phone.text} *</label>
            <textarea id={`${id}-text`} value={text} maxLength={300} rows={3} aria-describedby={`${id}-help`} onChange={(event) => setText(event.target.value)} />
            <span id={`${id}-help`} className="hint">
              {wg.phone.textHelp}
            </span>
          </div>
          <div className="field">
            <label htmlFor={`${id}-level`}>{wg.phone.level}</label>
            <select id={`${id}-level`} value={level} onChange={(event) => setLevel(event.target.value)}>
              {!levels.includes(level) && <option value={level}>{level}</option>}
              {levels.map((option, index) => (
                <option key={option} value={option}>
                  {levelTitles[index] ?? option}
                </option>
              ))}
            </select>
          </div>
          <UntilFields value={until} onChange={setUntil} />
          {existing && (
            <button type="button" className="button button--danger" onClick={() => setRemoving(true)}>
              {wg.phone.remove}
            </button>
          )}
        </>
      )}
    </FormDialog>
  );
}
