import {
  closestCenter,
  DndContext,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { SortableContext, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useEffect, useId, useRef, useState } from "react";
import { resetMenu, storeMenu, type MenuInfo } from "../../api/menus";
import { ApiError, errorMessage, isConflict } from "../../api/client";
import { mn } from "../../text/menus";
import { FormDialog } from "../../ui/FormDialog";
import { NoticeArea, type NoticeState } from "../../ui/Notice";
import { isFieldErrors } from "../editor/model/errorPaths";
import { isSafeUrl, normalizeUrl } from "../editor/schema/safeUrl";
import { announcements, instructions } from "../editor/zones/sortable";
import {
  canIndent,
  depthOf,
  findItem,
  indent,
  moveBy,
  neighbourAfterRemoval,
  newUid,
  outdent,
  parentUid,
  positionOf,
  removeItem,
  reorder,
  replaceItem,
  type MenuItem,
} from "./tree";

export interface PageOption {
  id: number;
  title: string;
  path: string;
  depth: number;
}

const POINTER_DISTANCE = 6;
const TOUCH_DELAY_MS = 250;
const TOUCH_TOLERANCE = 5;

type Editing = { kind: "page" } | { kind: "link" } | { kind: "edit"; uid: string } | null;
type Action = "up" | "down" | "indent" | "outdent" | "remove";
type ItemFields = Pick<MenuItem, "label" | "page_id" | "url">;

interface ItemProps {
  item: MenuItem;
  index: number;
  count: number;
  items: MenuItem[];
  maxDepth: number;
  titleOf: (item: MenuItem) => string;
  onAction: (action: Action, item: MenuItem) => void;
  onDrop: (next: MenuItem[]) => void;
  onEdit: (item: MenuItem) => void;
}

function ItemRow({ item, index, count, items, maxDepth, titleOf, onAction, onDrop, onEdit }: ItemProps) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: item.uid });
  const title = titleOf(item);
  const n = index + 1;
  const nested = depthOf(items, item.uid) > 1;
  const button = (action: Action, label: string, text: string, disabled = false, danger = false) => (
    <button
      type="button"
      className={`button button--small${danger ? " button--danger" : ""}`}
      aria-label={label}
      data-action={action}
      disabled={disabled}
      onClick={() => onAction(action, item)}
    >
      {text}
    </button>
  );
  return (
    <li ref={setNodeRef} style={{ transform: CSS.Transform.toString(transform), transition }} className="menu-item" data-uid={item.uid}>
      <div className="menu-item__row">
        <button type="button" className="block-row__handle" aria-label={mn.drag(title, n)} data-action="drag" {...attributes} {...listeners}>
          ⠿
        </button>
        <span className="menu-item__title">
          <strong>{title}</strong> <span className="hint">{item.url ?? mn.page}</span>
        </span>
        <span className="row-actions">
          {button("up", mn.up(title, n), "↑", index === 0)}
          {button("down", mn.down(title, n), "↓", index === count - 1)}
          {button("indent", mn.indent(title, n), "→", !canIndent(items, item.uid, maxDepth))}
          {button("outdent", mn.outdent(title, n), "←", !nested)}
          <button type="button" className="button button--small" aria-label={mn.editOf(title, n)} data-action="edit" onClick={() => onEdit(item)}>
            {mn.edit}
          </button>
          {button("remove", mn.remove(title, n), "✕", false, true)}
        </span>
      </div>
      {item.children.length > 0 && <ItemList list={item.children} {...{ items, maxDepth, titleOf, onAction, onDrop, onEdit }} />}
    </li>
  );
}

interface ListProps extends Omit<ItemProps, "item" | "index" | "count"> {
  list: MenuItem[];
}

function ItemList({ list, items, maxDepth, titleOf, onAction, onDrop, onEdit }: ListProps) {
  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: POINTER_DISTANCE } }),
    useSensor(TouchSensor, { activationConstraint: { delay: TOUCH_DELAY_MS, tolerance: TOUCH_TOLERANCE } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  const order = list.map((item) => item.uid);
  const label = (uid: string) => {
    const found = list.find((item) => item.uid === uid);
    return found ? titleOf(found) : "";
  };
  const end = ({ active, over }: DragEndEvent) => {
    if (over) onDrop(reorder(items, String(active.id), String(over.id)));
  };
  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={end}
      accessibility={{ announcements: announcements(label, (uid) => order.indexOf(uid) + 1), screenReaderInstructions: instructions }}
    >
      <SortableContext items={order} strategy={verticalListSortingStrategy}>
        <ul className="menu-tree">
          {list.map((item, index) => (
            <ItemRow key={item.uid} item={item} index={index} count={list.length} {...{ items, maxDepth, titleOf, onAction, onDrop, onEdit }} />
          ))}
        </ul>
      </SortableContext>
    </DndContext>
  );
}

interface EditProps {
  editing: Exclude<Editing, null>;
  current: MenuItem | null;
  pages: PageOption[];
  onClose: () => void;
  onDone: (uid: string, fields: ItemFields) => void;
}

function ItemDialog({ editing, current, pages, onClose, onDone }: EditProps) {
  const isPage = editing.kind === "page" || (current !== null && current.page_id !== undefined);
  const known = (id: number | undefined) => id !== undefined && pages.some((page) => page.id === id);
  const [label, setLabel] = useState(current?.label ?? "");
  const [url, setUrl] = useState(current?.url ?? "");
  // Una pagina che non c'è più non si sostituisce in silenzio: si chiede di sceglierne una.
  const [pageId, setPageId] = useState<number>(known(current?.page_id) ? current!.page_id! : editing.kind === "page" ? (pages[0]?.id ?? 0) : 0);
  const id = useId();
  const clean = normalizeUrl(url.trim());
  const validUrl = isSafeUrl(clean);
  const title = editing.kind === "page" ? mn.addPage : editing.kind === "link" ? mn.addLink : mn.edit;
  return (
    <FormDialog
      title={title}
      submitLabel={editing.kind === "edit" ? mn.save : mn.add}
      canSubmit={isPage ? known(pageId) : validUrl && label.trim().length > 0}
      onClose={onClose}
      onSubmit={async () => {
        const text = label.trim();
        const fields: ItemFields = isPage ? { page_id: pageId, ...(text ? { label: text } : {}) } : { url: clean, label: text };
        onDone(current?.uid ?? newUid(), fields);
      }}
    >
      {isPage && (
        <label className="field">
          <span>{mn.page}</span>
          <select value={pageId} onChange={(event) => setPageId(Number(event.target.value))}>
            {!known(pageId) && (
              <option value={0} disabled>
                {mn.choosePage}
              </option>
            )}
            {pages.map((page) => (
              <option key={page.id} value={page.id}>
                {"\u00a0\u00a0".repeat(page.depth) + page.title}
              </option>
            ))}
          </select>
        </label>
      )}
      <label className="field">
        <span>
          {mn.text}
          {!isPage && " *"}
        </span>
        <input value={label} maxLength={80} aria-describedby={isPage ? `${id}-text` : undefined} onChange={(event) => setLabel(event.target.value)} />
        {isPage && (
          <span id={`${id}-text`} className="hint">
            {mn.textPageHelp}
          </span>
        )}
      </label>
      {!isPage && (
        <label className="field">
          <span>{mn.url}</span>
          <input value={url} autoCapitalize="none" spellCheck={false} aria-describedby={`${id}-url`} onChange={(event) => setUrl(event.target.value)} />
          <span id={`${id}-url`} className="hint">
            {url && !validUrl ? mn.invalidUrl : mn.urlHelp}
          </span>
        </label>
      )}
    </FormDialog>
  );
}

interface Props {
  menu: MenuInfo;
  pages: PageOption[];
  onReload: () => void;
}

/** Un menu del tema (D-140, D-141): si modifica qui e si salva intero, con conferma.
 * Dopo ogni pulsante il focus resta sulla voce (o va alla vicina) e un messaggio dice cosa è
 * cambiato, per chi usa la tastiera o un lettore di schermo (WCAG 2.4.3, 4.1.3). */
export function MenuEditor({ menu, pages, onReload }: Props) {
  const [items, setItems] = useState<MenuItem[]>(menu.items);
  const [info, setInfo] = useState(menu);
  const [editing, setEditing] = useState<Editing>(null);
  const [confirm, setConfirm] = useState<"save" | "reset" | null>(null);
  const [removing, setRemoving] = useState<MenuItem | null>(null);
  const [problems, setProblems] = useState<string[]>([]);
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const [said, setSaid] = useState("");
  const pending = useRef<{ uid: string | null; action: string } | null>(null);
  const box = useRef<HTMLElement>(null);
  const titleId = `menu-${menu.location}`;
  const titles = new Map(pages.map((page) => [page.id, page.title]));
  const titleOf = (item: MenuItem) =>
    item.label || (item.page_id !== undefined ? (titles.get(item.page_id) ?? mn.pageMissing) : (item.url ?? ""));

  useEffect(() => {
    const target = pending.current;
    if (!target) return;
    pending.current = null;
    const row = target.uid ? box.current?.querySelector(`[data-uid="${target.uid}"]`) : null;
    const wanted = row?.querySelector<HTMLButtonElement>(`[data-action="${target.action}"]`);
    const fallback = row?.querySelector<HTMLButtonElement>('[data-action="edit"]') ?? box.current?.querySelector<HTMLButtonElement>('[data-action="add-page"]');
    (wanted && !wanted.disabled ? wanted : fallback)?.focus();
  }, [items]);

  function change(next: MenuItem[], focus: { uid: string | null; action: string }, message: string) {
    pending.current = focus;
    setItems(next);
    setSaid(message);
  }

  function remove(item: MenuItem) {
    change(removeItem(items, item.uid), { uid: neighbourAfterRemoval(items, item.uid), action: "edit" }, mn.removed(titleOf(item)));
  }

  function act(action: Action, item: MenuItem) {
    const title = titleOf(item);
    if (action === "remove") {
      if (item.children.length > 0) setRemoving(item);
      else remove(item);
      return;
    }
    if (action === "up" || action === "down") {
      const next = moveBy(items, item.uid, action === "up" ? -1 : 1);
      const { position, count } = positionOf(next, item.uid);
      change(next, { uid: item.uid, action }, mn.moved(title, position, count));
    } else if (action === "indent") {
      const next = indent(items, item.uid, menu.max_depth);
      const parent = findItem(next, parentUid(next, item.uid) ?? "");
      change(next, { uid: item.uid, action }, mn.indented(title, parent ? titleOf(parent) : ""));
    } else {
      change(outdent(items, item.uid), { uid: item.uid, action }, mn.outdented(title));
    }
  }

  function failed(error: unknown) {
    if (error instanceof ApiError && error.code === "invalid_content" && isFieldErrors(error.details)) {
      setProblems([...new Set(error.details.map((detail) => detail.message))]);
      setConfirm(null);
      return;
    }
    if (isConflict(error)) {
      setConfirm(null);
      setNotice({ kind: "error", text: errorMessage(error), action: { label: mn.reload, run: onReload } });
      return;
    }
    throw error;
  }

  async function save() {
    try {
      const saved = await storeMenu(menu.location, info.version, items);
      setInfo(saved);
      setItems(saved.items);
      setProblems([]);
      setConfirm(null);
      setNotice({ kind: "success", text: mn.saved });
    } catch (error) {
      failed(error);
    }
  }

  async function reset() {
    try {
      const fresh = await resetMenu(menu.location, info.version);
      setInfo(fresh);
      setItems(fresh.items);
      setProblems([]);
      setConfirm(null);
      setNotice({ kind: "success", text: mn.resetDone });
    } catch (error) {
      failed(error);
    }
  }

  const editingItem = editing?.kind === "edit" ? findItem(items, editing.uid) : null;
  return (
    <section className="card" aria-labelledby={titleId} ref={box}>
      <h2 id={titleId}>{menu.label}</h2>
      <p className="hint">{mn.depth(menu.max_depth)}</p>
      {info.automatic && !info.manual && <p className="notice notice--info">{mn.automatic}</p>}
      <NoticeArea notice={notice} onClose={() => setNotice(null)} />
      <p className="visually-hidden" role="status">
        {said}
      </p>
      {problems.length > 0 && (
        <section className="notice notice--error error-list" role="alert">
          <p>{mn.errorsTitle}</p>
          <ul>
            {problems.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        </section>
      )}
      {items.length === 0 ? (
        <p className="hint">{mn.empty}</p>
      ) : (
        <ItemList
          list={items}
          items={items}
          maxDepth={menu.max_depth}
          titleOf={titleOf}
          onAction={act}
          onDrop={setItems}
          onEdit={(item) => setEditing({ kind: "edit", uid: item.uid })}
        />
      )}
      <div className="form__actions">
        <button type="button" className="button" data-action="add-page" disabled={pages.length === 0} onClick={() => setEditing({ kind: "page" })}>
          {mn.addPage}
        </button>
        <button type="button" className="button" onClick={() => setEditing({ kind: "link" })}>
          {mn.addLink}
        </button>
        <button type="button" className="button button--primary" onClick={() => setConfirm("save")}>
          {mn.save}
        </button>
        {info.automatic && info.manual && (
          <button type="button" className="button button--danger" onClick={() => setConfirm("reset")}>
            {mn.reset}
          </button>
        )}
      </div>
      {editing && (editing.kind !== "edit" || editingItem) && (
        <ItemDialog
          editing={editing}
          current={editingItem}
          pages={pages}
          onClose={() => setEditing(null)}
          onDone={(uid, fields) => {
            // Si cambiano solo i campi del modulo: le sottovoci restano quelle di adesso.
            setItems((current) =>
              editing.kind === "edit"
                ? replaceItem(current, uid, (live) => ({ uid: live.uid, children: live.children, ...fields }))
                : [...current, { uid, children: [], ...fields }],
            );
            setEditing(null);
          }}
        />
      )}
      {removing && (
        <FormDialog
          title={mn.removeTitle}
          submitLabel={mn.removeConfirm}
          danger
          onClose={() => setRemoving(null)}
          onSubmit={async () => {
            setRemoving(null);
            remove(removing);
          }}
        >
          <p>{mn.removeText(titleOf(removing), removing.children.length)}</p>
        </FormDialog>
      )}
      {confirm === "save" && (
        <FormDialog title={mn.saveTitle} submitLabel={mn.save} onClose={() => setConfirm(null)} onSubmit={save}>
          <p>{mn.saveText}</p>
        </FormDialog>
      )}
      {confirm === "reset" && (
        <FormDialog title={mn.resetTitle} submitLabel={mn.reset} danger onClose={() => setConfirm(null)} onSubmit={reset}>
          <p>{mn.resetText}</p>
        </FormDialog>
      )}
    </section>
  );
}
