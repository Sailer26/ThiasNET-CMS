import { useEffect, useRef, useState } from "react";
import { ApiError, errorMessage, isConflict } from "../../api/client";
import { storeWidgetArea, type WidgetAreaInfo, type WidgetItem } from "../../api/widgets";
import { wg } from "../../text/widgets";
import { FormDialog } from "../../ui/FormDialog";
import { NoticeArea, type NoticeState } from "../../ui/Notice";
import { isFieldErrors, type ServerFieldError } from "../editor/model/errorPaths";
import { formatZurich } from "../editor/schedule/siteTime";
import type { PageOption } from "../menus/MenuEditor";
import { blankWidget, moveBy, neighbourAfterRemoval, removeWidget, replaceWidget, summary } from "./model";
import { WidgetDialog } from "./WidgetDialog";

type Action = "up" | "down" | "remove";
type Editing = { item: WidgetItem; isNew: boolean } | null;
const ITEM_PATH = /^items\/(\d+)/;

function placement(item: WidgetItem): string | null {
  const pages = item.visibility?.pages.length ?? 0;
  if (item.visibility?.mode === "only") return wg.shownOn(pages);
  if (item.visibility?.mode === "except") return wg.hiddenOn(pages);
  return null;
}

function ending(item: WidgetItem, now: number): string | null {
  if (!item.until) return null;
  return new Date(item.until).getTime() <= now ? wg.expired : wg.untilShort(formatZurich(item.until));
}

interface Props {
  area: WidgetAreaInfo;
  pages: PageOption[];
  onReload: () => void;
}

/** Una parte del sito con i suoi widget (D-140, D-146): si cambia qui e si salva intera.
 * Come nei menu, dopo ogni pulsante il focus resta sul widget e un messaggio dice cosa è cambiato. */
export function AreaEditor({ area, pages, onReload }: Props) {
  const [items, setItems] = useState<WidgetItem[]>(area.items);
  const [version, setVersion] = useState(area.version);
  const [kind, setKind] = useState(area.types[0]?.type ?? "");
  const [editing, setEditing] = useState<Editing>(null);
  const [confirm, setConfirm] = useState(false);
  const [problems, setProblems] = useState<string[]>([]);
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const [said, setSaid] = useState("");
  const [now] = useState(() => Date.now());
  const pending = useRef<{ uid: string | null; action: string } | null>(null);
  const box = useRef<HTMLElement>(null);
  const titleId = `widgets-${area.area}`;
  const label = (item: WidgetItem) => summary(item, area.types);

  useEffect(() => {
    const target = pending.current;
    if (!target) return;
    pending.current = null;
    const row = target.uid ? box.current?.querySelector(`[data-uid="${target.uid}"]`) : null;
    const wanted = row?.querySelector<HTMLButtonElement>(`[data-action="${target.action}"]`);
    const fallback = row?.querySelector<HTMLButtonElement>('[data-action="edit"]') ?? box.current?.querySelector<HTMLButtonElement>('[data-action="add"]');
    (wanted && !wanted.disabled ? wanted : fallback)?.focus();
  }, [items]);

  function act(action: Action, item: WidgetItem) {
    const name = label(item);
    if (action === "remove") {
      pending.current = { uid: neighbourAfterRemoval(items, item.uid), action: "edit" };
      setItems(removeWidget(items, item.uid));
      setSaid(wg.removed(name));
      return;
    }
    const next = moveBy(items, item.uid, action === "up" ? -1 : 1);
    if (next === items) return; // già al bordo: niente focus in sospeso
    pending.current = { uid: item.uid, action };
    setItems(next);
    setSaid(wg.moved(name, next.indexOf(item) + 1, next.length));
  }

  /** Gli errori del server con il nome del widget: "Campo obbligatorio" da solo non dice dove. */
  function describe(details: ServerFieldError[], sent: WidgetItem[]): string[] {
    const lines = details.map((detail) => {
      const index = ITEM_PATH.exec(detail.path)?.[1];
      const item = index === undefined ? undefined : sent[Number(index)];
      return item ? `${label(item)}: ${detail.message}` : detail.message;
    });
    return [...new Set(lines)];
  }

  async function save() {
    const sent = items;
    try {
      const saved = await storeWidgetArea(area.area, version, sent, area.locale);
      setVersion(saved.version);
      setItems(saved.items);
      setProblems([]);
      setConfirm(false);
      setNotice({ kind: "success", text: wg.saved });
    } catch (error) {
      if (error instanceof ApiError && error.code === "invalid_content" && isFieldErrors(error.details)) {
        setConfirm(false);
        setProblems(describe(error.details, sent));
        return;
      }
      if (isConflict(error)) {
        setConfirm(false);
        setNotice({ kind: "error", text: errorMessage(error), action: { label: wg.reload, run: onReload } });
        return;
      }
      throw error;
    }
  }

  const editingType = editing ? area.types.find((type) => type.type === editing.item.type) : undefined;
  return (
    <section className="card" aria-labelledby={titleId} ref={box}>
      <h2 id={titleId}>{area.label}</h2>
      <NoticeArea notice={notice} onClose={() => setNotice(null)} />
      <p className="visually-hidden" role="status">
        {said}
      </p>
      {problems.length > 0 && (
        <section className="notice notice--error error-list" role="alert">
          <p>{wg.errorsTitle}</p>
          <ul>
            {problems.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        </section>
      )}
      {items.length === 0 ? (
        <p className="hint">{wg.empty}</p>
      ) : (
        <ol className="widget-list">
          {items.map((item, index) => {
            const name = label(item);
            const n = index + 1;
            const typeLabel = area.types.find((type) => type.type === item.type)?.label;
            const notes = [typeLabel ?? wg.unavailable, placement(item), ending(item, now)].filter(Boolean);
            return (
              <li key={item.uid} className="widget-list__item" data-uid={item.uid}>
                <span className="widget-list__title">
                  <strong>{name}</strong> <span className="hint">{notes.join(" · ")}</span>
                </span>
                <span className="row-actions">
                  <button type="button" className="button button--small" aria-label={wg.up(name, n)} data-action="up" disabled={index === 0} onClick={() => act("up", item)}>
                    ↑
                  </button>
                  <button
                    type="button"
                    className="button button--small"
                    aria-label={wg.down(name, n)}
                    data-action="down"
                    disabled={index === items.length - 1}
                    onClick={() => act("down", item)}
                  >
                    ↓
                  </button>
                  <button type="button" className="button button--small" aria-label={wg.editOf(name, n)} data-action="edit" disabled={!typeLabel} onClick={() => setEditing({ item, isNew: false })}>
                    {wg.edit}
                  </button>
                  <button type="button" className="button button--small button--danger" aria-label={wg.remove(name, n)} data-action="remove" onClick={() => act("remove", item)}>
                    ✕
                  </button>
                </span>
              </li>
            );
          })}
        </ol>
      )}
      <div className="form__actions">
        <label className="field widget-add">
          <span>{wg.chooseType}</span>
          <select value={kind} onChange={(event) => setKind(event.target.value)}>
            {area.types.map((type) => (
              <option key={type.type} value={type.type}>
                {type.label}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="button" data-action="add" disabled={!kind} onClick={() => setEditing({ item: blankWidget(kind), isNew: true })}>
          {wg.add}
        </button>
        <button type="button" className="button button--primary" onClick={() => setConfirm(true)}>
          {wg.save}
        </button>
      </div>
      {editing && editingType && (
        <WidgetDialog
          type={editingType}
          item={editing.item}
          isNew={editing.isNew}
          pages={pages}
          onClose={() => setEditing(null)}
          onDone={(next) => {
            pending.current = { uid: next.uid, action: "edit" };
            setItems((current) => replaceWidget(current, next));
            setEditing(null);
          }}
        />
      )}
      {confirm && (
        <FormDialog title={wg.saveTitle} submitLabel={wg.save} onClose={() => setConfirm(false)} onSubmit={save}>
          <p>{wg.saveText}</p>
        </FormDialog>
      )}
    </section>
  );
}
