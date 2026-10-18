import { useState } from "react";
import type { PageNode } from "../../api/types";
import { it } from "../../text/it";
import { FormDialog } from "../../ui/FormDialog";
import {
  childPath,
  createTargets,
  findNode,
  moveTargets,
  placementLabel,
  type Placement,
} from "./tree";

const TITLE_MAX = 200;
const SLUG_MAX = 80;

function placementValue(placement: Placement): string {
  return placement.parentId === null ? "" : String(placement.parentId);
}

function parentFromValue(value: string): number | null {
  return value === "" ? null : Number(value);
}

interface CreateProps {
  roots: PageNode[];
  home: boolean;
  onCreate: (title: string, parentId: number | null) => Promise<void>;
  onClose: () => void;
}

export function CreatePageDialog({ roots, home, onCreate, onClose }: CreateProps) {
  const [title, setTitle] = useState(home ? it.create.homeDefault : "");
  const [parent, setParent] = useState("");
  const targets = createTargets(roots);
  return (
    <FormDialog
      title={home ? it.create.homeTitle : it.create.title}
      submitLabel={it.create.submit}
      canSubmit={title.trim().length > 0}
      onSubmit={() => onCreate(title.trim(), home ? null : parentFromValue(parent))}
      onClose={onClose}
    >
      <label className="field">
        <span>{it.create.pageTitle}</span>
        <input
          name="title"
          required
          maxLength={TITLE_MAX}
          value={title}
          onChange={(event) => setTitle(event.target.value)}
        />
      </label>
      {!home && (
        <label className="field">
          <span>{it.create.position}</span>
          <select name="parent" value={parent} onChange={(event) => setParent(event.target.value)}>
            {targets.map((target) => (
              <option key={placementValue(target)} value={placementValue(target)}>
                {placementLabel(target)}
              </option>
            ))}
          </select>
        </label>
      )}
    </FormDialog>
  );
}

interface MoveProps {
  roots: PageNode[];
  node: PageNode;
  onMove: (parentId: number | null) => Promise<void>;
  onClose: () => void;
}

export function MoveDialog({ roots, node, onMove, onClose }: MoveProps) {
  const targets = moveTargets(roots, node);
  const [choice, setChoice] = useState(targets[0] ? placementValue(targets[0]) : "");
  return (
    <FormDialog
      title={it.move.title(node.title)}
      submitLabel={it.move.submit}
      canSubmit={targets.length > 0}
      onSubmit={() => onMove(parentFromValue(choice))}
      onClose={onClose}
    >
      {targets.length === 0 ? (
        <p>{it.move.none}</p>
      ) : (
        <label className="field">
          <span>{it.move.target}</span>
          <select name="target" value={choice} onChange={(event) => setChoice(event.target.value)}>
            {targets.map((target) => (
              <option key={placementValue(target)} value={placementValue(target)}>
                {placementLabel(target)}
              </option>
            ))}
          </select>
        </label>
      )}
    </FormDialog>
  );
}

interface AddressProps {
  roots: PageNode[];
  node: PageNode;
  onSave: (slug: string) => Promise<void>;
  onClose: () => void;
}

export function AddressDialog({ roots, node, onSave, onClose }: AddressProps) {
  const [slug, setSlug] = useState(node.slug);
  const clean = slug.trim().toLowerCase();
  const parent = findNode(roots, node.parent_id);
  return (
    <FormDialog
      title={it.address.title(node.title)}
      submitLabel={it.address.submit}
      canSubmit={clean.length > 0 && clean !== node.slug}
      onSubmit={() => onSave(clean)}
      onClose={onClose}
    >
      <label className="field">
        <span>{it.address.label}</span>
        <input
          name="slug"
          required
          maxLength={SLUG_MAX}
          autoCapitalize="none"
          spellCheck={false}
          value={slug}
          onChange={(event) => setSlug(event.target.value)}
        />
      </label>
      <p className="hint">{it.address.help}</p>
      <p>
        {it.address.preview} <code>{childPath(parent, clean || "…")}</code>
      </p>
      <p className="hint">{it.address.redirect}</p>
    </FormDialog>
  );
}
