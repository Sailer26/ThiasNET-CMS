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
import { useId, useState } from "react";
import { resetMenu, storeMenu, type MenuInfo } from "../../api/menus";
import { ApiError, errorMessage, isConflict } from "../../api/client";
import { mn } from "../../text/menus";
import { FormDialog } from "../../ui/FormDialog";
import { NoticeArea, type NoticeState } from "../../ui/Notice";
import { isFieldErrors } from "../editor/model/errorPaths";
import { isSafeUrl, normalizeUrl } from "../editor/schema/safeUrl";
import { announcements, instructions } from "../editor/zones/sortable";
import { canIndent, depthOf, indent, moveBy, newUid, outdent, removeItem, reorder, replaceItem, type MenuItem } from "./tree";

export interface PageOption {
  id: number;
  title: string;
  path: string;
  depth: number;
}

const POINTER_DISTANCE = 6;
const TOUCH_DELAY_MS = 250;
const TOUCH_TOLERANCE = 5;

type Editing = { kind: "page" } | { kind: "link" } | { kind: "edit"; item: MenuItem } | null;

interface ItemProps {
  item: MenuItem;
  index: number;
  count: number;
  items: MenuItem[];
  maxDepth: number;
  titleOf: (item: MenuItem) => string;
  onChange: (next: MenuItem[]) => void;
  onEdit: (item: MenuItem) => void;
}

function ItemRow({ item, index, count, items, maxDepth, titleOf, onChange, onEdit }: ItemProps) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: item.uid });
  const title = titleOf(item);
  const nested = depthOf(items, item.uid) > 1;
  return (
    <li ref={setNodeRef} style={{ transform: CSS.Transform.toString(transform), transition }} className="menu-item">
      <div className="menu-item__row">
        <button type="button" className="block-row__handle" aria-label={mn.drag(title)} {...attributes} {...listeners}>
          ⠿
        </button>
        <span className="menu-item__title">
          <strong>{title}</strong> <span className="hint">{item.url ?? mn.page}</span>
        </span>
        <span className="row-actions">
          <button type="button" className="button button--small" aria-label={mn.up(title)} disabled={index === 0} onClick={() => onChange(moveBy(items, item.uid, -1))}>
            ↑
          </button>
          <button type="button" className="button button--small" aria-label={mn.down(title)} disabled={index === count - 1} onClick={() => onChange(moveBy(items, item.uid, 1))}>
            ↓
          </button>
          <button type="button" className="button button--small" aria-label={mn.indent(title)} disabled={!canIndent(items, item.uid, maxDepth)} onClick={() => onChange(indent(items, item.uid, maxDepth))}>
            →
          </button>
          <button type="button" className="button button--small" aria-label={mn.outdent(title)} disabled={!nested} onClick={() => onChange(outdent(items, item.uid))}>
            ←
          </button>
          <button type="button" className="button button--small" aria-label={mn.editOf(title)} onClick={() => onEdit(item)}>
            {mn.edit}
          </button>
          <button type="button" className="button button--small button--danger" aria-label={mn.remove(title)} onClick={() => onChange(removeItem(items, item.uid))}>
            ✕
          </button>
        </span>
      </div>
      {item.children.length > 0 && <ItemList list={item.children} {...{ items, maxDepth, titleOf, onChange, onEdit }} />}
    </li>
  );
}

interface ListProps extends Omit<ItemProps, "item" | "index" | "count"> {
  list: MenuItem[];
}

function ItemList({ list, items, maxDepth, titleOf, onChange, onEdit }: ListProps) {
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
    if (over) onChange(reorder(items, String(active.id), String(over.id)));
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
            <ItemRow key={item.uid} item={item} index={index} count={list.length} {...{ items, maxDepth, titleOf, onChange, onEdit }} />
          ))}
        </ul>
      </SortableContext>
    </DndContext>
  );
}

interface EditProps {
  editing: Exclude<Editing, null>;
  pages: PageOption[];
  onClose: () => void;
  onDone: (item: MenuItem) => void;
}

function ItemDialog({ editing, pages, onClose, onDone }: EditProps) {
  const current = editing.kind === "edit" ? editing.item : null;
  const isPage = editing.kind === "page" || (current !== null && current.page_id !== undefined);
  const [label, setLabel] = useState(current?.label ?? "");
  const [url, setUrl] = useState(current?.url ?? "");
  const [pageId, setPageId] = useState<number>(current?.page_id ?? pages[0]?.id ?? 0);
  const id = useId();
  const clean = normalizeUrl(url.trim());
  const validUrl = isSafeUrl(clean);
  const title = editing.kind === "page" ? mn.addPage : editing.kind === "link" ? mn.addLink : mn.edit;
  return (
    <FormDialog
      title={title}
      submitLabel={editing.kind === "edit" ? mn.save : mn.add}
      canSubmit={isPage ? pageId > 0 : validUrl && label.trim().length > 0}
      onClose={onClose}
      onSubmit={async () => {
        const base = { uid: current?.uid ?? newUid(), children: current?.children ?? [] };
        const text = label.trim();
        onDone(isPage ? { ...base, page_id: pageId, ...(text ? { label: text } : {}) } : { ...base, url: clean, label: text });
      }}
    >
      {isPage && (
        <label className="field">
          <span>{mn.page}</span>
          <select value={pageId} onChange={(event) => setPageId(Number(event.target.value))}>
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

/** Un menu del tema (D-140, D-141): si modifica qui e si salva intero, con conferma. */
export function MenuEditor({ menu, pages, onReload }: Props) {
  const [items, setItems] = useState<MenuItem[]>(menu.items);
  const [info, setInfo] = useState(menu);
  const [editing, setEditing] = useState<Editing>(null);
  const [confirm, setConfirm] = useState<"save" | "reset" | null>(null);
  const [problems, setProblems] = useState<string[]>([]);
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const titleId = `menu-${menu.location}`;
  const titles = new Map(pages.map((page) => [page.id, page.title]));
  const titleOf = (item: MenuItem) =>
    item.label || (item.page_id !== undefined ? (titles.get(item.page_id) ?? mn.pageMissing) : (item.url ?? ""));

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

  return (
    <section className="card" aria-labelledby={titleId}>
      <h2 id={titleId}>{menu.label}</h2>
      <p className="hint">{mn.depth(menu.max_depth)}</p>
      {info.automatic && !info.manual && <p className="notice notice--info">{mn.automatic}</p>}
      <NoticeArea notice={notice} onClose={() => setNotice(null)} />
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
        <ItemList list={items} items={items} maxDepth={menu.max_depth} titleOf={titleOf} onChange={setItems} onEdit={(item) => setEditing({ kind: "edit", item })} />
      )}
      <div className="form__actions">
        <button type="button" className="button" disabled={pages.length === 0} onClick={() => setEditing({ kind: "page" })}>
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
      {editing && (
        <ItemDialog
          editing={editing}
          pages={pages}
          onClose={() => setEditing(null)}
          onDone={(item) => {
            setItems((current) => (editing.kind === "edit" ? replaceItem(current, item.uid, () => item) : [...current, item]));
            setEditing(null);
          }}
        />
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
