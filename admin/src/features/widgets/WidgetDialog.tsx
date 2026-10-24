import { useId, useState } from "react";
import type { VisibilityMode, WidgetItem, WidgetType } from "../../api/widgets";
import { wg } from "../../text/widgets";
import { FormDialog } from "../../ui/FormDialog";
import { setPath, type Data, type Path } from "../editor/model/document";
import { SchemaForm } from "../editor/schema/SchemaForm";
import { fieldProblem } from "../editor/schema/validate";
import type { PageOption } from "../menus/MenuEditor";
import { NOTICE } from "./model";
import { nextUntil, UntilFields, untilFields, type Until } from "./UntilFields";

const NONE: ReadonlyMap<string, string> = new Map();
const MODES: VisibilityMode[] = ["all", "only", "except"];

/** Campi obbligatori pieni e nessun valore fuori regola: il server ricontrolla comunque. */
function complete(type: WidgetType, data: Data): boolean {
  const required = new Set(type.schema.required ?? []);
  return Object.entries(type.schema.properties ?? {}).every(([name, spec]) => {
    const value = data[name];
    const empty = value === undefined || value === "" || (Array.isArray(value) && value.length === 0);
    return !(required.has(name) && empty) && fieldProblem(spec, value) === null;
  });
}

interface Props {
  type: WidgetType;
  item: WidgetItem;
  isNew: boolean;
  pages: PageOption[];
  onClose: () => void;
  onDone: (item: WidgetItem) => void;
}

/** Un widget: i suoi campi (dallo schema), dove si vede e, per il banner, fino a quando. */
export function WidgetDialog({ type, item, isNew, pages, onClose, onDone }: Props) {
  const [data, setData] = useState<Data>(item.data);
  const [mode, setMode] = useState<VisibilityMode>(item.visibility?.mode ?? "all");
  const [chosen, setChosen] = useState<Set<number>>(() => new Set(item.visibility?.pages ?? []));
  const [start] = useState<Until>(() => untilFields(item.until));
  const [until, setUntil] = useState<Until>(start);
  const id = useId();
  const known = pages.filter((page) => chosen.has(page.id));
  const placed = mode === "all" || known.length > 0;
  const toggle = (pageId: number) =>
    setChosen((current) => {
      const next = new Set(current);
      if (next.has(pageId)) next.delete(pageId);
      else next.add(pageId);
      return next;
    });
  return (
    <FormDialog
      title={isNew ? wg.addOf(type.label) : `${wg.edit}: ${type.label}`}
      submitLabel={wg.done}
      canSubmit={placed && complete(type, data)}
      onClose={onClose}
      onSubmit={async () => {
        const pagesKept = mode === "all" ? [] : known.map((page) => page.id);
        const ends = type.type === NOTICE ? nextUntil(until, start, item.until) : null;
        onDone({ uid: item.uid, type: type.type, data, visibility: { mode, pages: pagesKept }, until: ends });
      }}
    >
      <SchemaForm
        schema={type.schema}
        data={data}
        idPrefix={id}
        errors={NONE}
        unsaved={NONE}
        pages={pages.map((page) => page.path)}
        onChange={(path: Path, value: unknown) => setData((current) => setPath(current, path, value) as Data)}
      />
      {type.type === NOTICE && <UntilFields value={until} onChange={setUntil} />}
      <fieldset className="field">
        <legend>{wg.where}</legend>
        <div className="choice__options">
          {MODES.map((option) => (
            <label key={option} className="choice__option">
              <input type="radio" name={`${id}-mode`} value={option} checked={mode === option} onChange={() => setMode(option)} />
              {wg.modes[option]}
            </label>
          ))}
        </div>
      </fieldset>
      {mode !== "all" && (
        <fieldset className="field" aria-describedby={`${id}-pages`}>
          <legend>{wg.pagesLegend}</legend>
          <p id={`${id}-pages`} className="hint">
            {wg.pagesHelp}
          </p>
          <ul className="widget-pages">
            {pages.map((page) => (
              <li key={page.id} className={`widget-pages__item widget-pages__item--depth-${Math.min(page.depth, 4)}`}>
                <label className="choice__option">
                  <input type="checkbox" checked={chosen.has(page.id)} onChange={() => toggle(page.id)} />
                  {page.title}
                </label>
              </li>
            ))}
          </ul>
        </fieldset>
      )}
    </FormDialog>
  );
}
