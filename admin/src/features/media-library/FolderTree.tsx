import { useState } from "react";
import type { Folder } from "../../api/media";
import { mt } from "../../text/media";
import { FormDialog } from "../../ui/FormDialog";

export type FolderChoice = "all" | "none" | number;
const MAX_FOLDER_DEPTH = 3; // D-82

interface Props {
  folders: Folder[];
  selected: FolderChoice;
  onSelect: (choice: FolderChoice) => void;
  onCreate: (name: string, parentId: number | null) => Promise<void>;
  onRename: (folder: Folder, name: string) => Promise<void>;
  onMove: (folder: Folder, parentId: number | null) => Promise<void>;
  onDelete: (folder: Folder) => Promise<void>;
}

interface Row {
  folder: Folder;
  depth: number;
}

export function flattenFolders(folders: Folder[], depth = 1): Row[] {
  return folders.flatMap((folder) => [{ folder, depth }, ...flattenFolders(folder.children, depth + 1)]);
}

function height(folder: Folder): number {
  return 1 + Math.max(0, ...folder.children.map(height));
}

function ownIds(folder: Folder): Set<number> {
  return new Set(flattenFolders([folder]).map((row) => row.folder.id));
}

function hasFiles(folder: Folder): boolean {
  return folder.count > 0 || folder.children.length > 0;
}

type Dialog = { kind: "create" } | { kind: "rename" | "move" | "delete"; folder: Folder };

export function FolderTree({ folders, selected, onSelect, onCreate, onRename, onMove, onDelete }: Props) {
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const [name, setName] = useState("");
  const [parent, setParent] = useState("");
  const rows = flattenFolders(folders);
  const current = typeof selected === "number" ? rows.find((r) => r.folder.id === selected)?.folder : undefined;

  function open(next: Dialog) {
    setName(next.kind === "rename" ? next.folder.name : "");
    setParent(
      next.kind === "create" && current
        ? String(current.id)
        : next.kind === "move"
          ? String(next.folder.parent_id ?? "")
          : "",
    );
    setDialog(next);
  }

  const item = (choice: FolderChoice, label: string, count: number | null, depth = 0) => (
    <li key={String(choice)}>
      <button
        type="button"
        className={`folders__item folders__item--d${depth}`}
        aria-current={selected === choice ? "true" : undefined}
        onClick={() => onSelect(choice)}
      >
        {label}
        {count !== null && (
          <>
            {" "}
            <span className="folders__count">{count}</span>
          </>
        )}
      </button>
    </li>
  );

  const parentOptions = (exclude?: Folder) => {
    const banned = exclude ? ownIds(exclude) : new Set<number>();
    const size = exclude ? height(exclude) : 1;
    return rows.filter((row) => !banned.has(row.folder.id) && row.depth + size <= MAX_FOLDER_DEPTH);
  };

  return (
    <nav className="folders" aria-label={mt.folders}>
      <ul>
        {item("all", mt.all, null)}
        {item("none", mt.noFolder, null)}
        {rows.map((row) => item(row.folder.id, row.folder.name, row.folder.count, row.depth))}
      </ul>
      <div className="folders__actions">
        <button type="button" className="button button--small" onClick={() => open({ kind: "create" })}>
          {mt.newFolder}
        </button>
        {current && (
          <>
            <button type="button" className="button button--small" onClick={() => open({ kind: "rename", folder: current })}>
              {mt.rename}
            </button>
            <button type="button" className="button button--small" onClick={() => open({ kind: "move", folder: current })}>
              {mt.moveFolder}
            </button>
            <button
              type="button"
              className="button button--small button--danger"
              aria-disabled={hasFiles(current)}
              onClick={() => (hasFiles(current) ? undefined : open({ kind: "delete", folder: current }))}
            >
              {mt.deleteFolder}
            </button>
            {hasFiles(current) && <p className="hint">{mt.folderNotEmpty}</p>}
          </>
        )}
      </div>
      {dialog?.kind === "create" && (
        <FormDialog
          title={mt.newFolder}
          submitLabel={mt.create}
          canSubmit={name.trim().length > 0}
          onClose={() => setDialog(null)}
          onSubmit={async () => {
            await onCreate(name.trim(), parent ? Number(parent) : null);
            setDialog(null);
          }}
        >
          <label className="field">
            <span>{mt.folderName}</span>
            <input value={name} maxLength={80} onChange={(event) => setName(event.target.value)} />
          </label>
          <label className="field">
            <span>{mt.where}</span>
            <select value={parent} onChange={(event) => setParent(event.target.value)}>
              <option value="">{mt.top}</option>
              {parentOptions().map((row) => (
                <option key={row.folder.id} value={row.folder.id}>
                  {"— ".repeat(row.depth - 1)}
                  {mt.inside(row.folder.name)}
                </option>
              ))}
            </select>
          </label>
        </FormDialog>
      )}
      {dialog?.kind === "rename" && (
        <FormDialog
          title={mt.rename}
          submitLabel={mt.save}
          canSubmit={name.trim().length > 0 && name.trim() !== dialog.folder.name}
          onClose={() => setDialog(null)}
          onSubmit={async () => {
            await onRename(dialog.folder, name.trim());
            setDialog(null);
          }}
        >
          <label className="field">
            <span>{mt.folderName}</span>
            <input value={name} maxLength={80} onChange={(event) => setName(event.target.value)} />
          </label>
        </FormDialog>
      )}
      {dialog?.kind === "move" && (
        <FormDialog
          title={mt.moveFolder}
          submitLabel={mt.save}
          canSubmit={parent !== String(dialog.folder.parent_id ?? "")}
          onClose={() => setDialog(null)}
          onSubmit={async () => {
            await onMove(dialog.folder, parent ? Number(parent) : null);
            setDialog(null);
          }}
        >
          <label className="field">
            <span>{mt.where}</span>
            <select value={parent} onChange={(event) => setParent(event.target.value)}>
              <option value="">{mt.top}</option>
              {parentOptions(dialog.folder).map((row) => (
                <option key={row.folder.id} value={row.folder.id}>
                  {"— ".repeat(row.depth - 1)}
                  {mt.inside(row.folder.name)}
                </option>
              ))}
            </select>
          </label>
        </FormDialog>
      )}
      {dialog?.kind === "delete" && (
        <FormDialog
          title={mt.deleteFolder}
          submitLabel={mt.deleteFolder}
          danger
          onClose={() => setDialog(null)}
          onSubmit={async () => {
            await onDelete(dialog.folder);
            setDialog(null);
          }}
        >
          <p>{mt.deleteFolderConfirm(dialog.folder.name)}</p>
        </FormDialog>
      )}
    </nav>
  );
}
