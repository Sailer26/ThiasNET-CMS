import { useState } from "react";
import type { Catalog } from "../../../api/catalog";
import { ed } from "../../../text/editor";
import { FormDialog } from "../../../ui/FormDialog";
import { Dialog } from "../../../ui/Dialog";
import { hasRoom, zonesFor, type BlockDoc, type PageDocument, type Path } from "../model/document";
import { SchemaForm } from "../schema/SchemaForm";
import { VariantPicker } from "../page/VariantPicker";
import { BlockIcon } from "./BlockIcon";
import { summary } from "./summary";

export interface ZoneActions {
  select: (uid: string | null) => void;
  add: (zone: string, type: string) => void;
  shift: (uid: string, delta: -1 | 1) => void;
  moveTo: (uid: string, zone: string) => void;
  duplicate: (uid: string) => void;
  remove: (uid: string) => void;
  setVariant: (uid: string, variant: string) => void;
  editField: (uid: string, path: Path, value: unknown) => void;
}

interface Props {
  doc: PageDocument;
  catalog: Catalog;
  selected: string | null;
  /** Problemi per blocco: errori del server e campi non salvati, per percorso del campo. */
  errors: ReadonlyMap<string, ReadonlyMap<string, string>>;
  unsaved: ReadonlyMap<string, ReadonlyMap<string, string>>;
  pages: string[];
  actions: ZoneActions;
}

const EMPTY = new Map<string, string>();

function AddBlockDialog({ zone, types, catalog, onAdd, onClose }: { zone: string; types: string[]; catalog: Catalog; onAdd: (type: string) => void; onClose: () => void }) {
  return (
    <Dialog title={ed.zones.addTitle(zone)} onClose={onClose}>
      <div className="block-catalog">
        {types.map((type) => (
          <button key={type} type="button" className="block-card" onClick={() => onAdd(type)}>
            <BlockIcon type={type} />
            <span className="block-card__name">{catalog.types[type]?.label ?? type}</span>
            <span className="block-card__text">{ed.blocks[type] ?? ""}</span>
          </button>
        ))}
      </div>
      <div className="form__actions">
        <button type="button" className="button" onClick={onClose}>
          {ed.zones.close}
        </button>
      </div>
    </Dialog>
  );
}

function MoveDialog({ label, zones, catalog, layout, onMove, onClose }: { label: string; zones: string[]; catalog: Catalog; layout: string; onMove: (zone: string) => void; onClose: () => void }) {
  const [zone, setZone] = useState(zones[0] ?? "");
  return (
    <FormDialog
      title={ed.zones.moveTitle(label)}
      submitLabel={ed.zones.moveSubmit}
      canSubmit={zones.length > 0}
      onClose={onClose}
      onSubmit={async () => onMove(zone)}
    >
      {zones.length === 0 ? (
        <p>{ed.zones.noTarget}</p>
      ) : (
        <label className="field">
          <span>{ed.zones.moveTarget}</span>
          <select value={zone} onChange={(event) => setZone(event.target.value)}>
            {zones.map((name) => (
              <option key={name} value={name}>
                {catalog.layouts[layout]?.zones[name]?.label ?? name}
              </option>
            ))}
          </select>
        </label>
      )}
    </FormDialog>
  );
}

function BlockRow({ block, index, count, props }: { block: BlockDoc; index: number; count: number; props: Props }) {
  const { catalog, selected, actions, doc } = props;
  const label = catalog.types[block.type]?.label ?? block.type;
  const open = selected === block.uid;
  const errors = props.errors.get(block.uid) ?? EMPTY;
  const unsaved = props.unsaved.get(block.uid) ?? EMPTY;
  const [moving, setMoving] = useState(false);
  const schema = catalog.types[block.type]?.schema ?? {};
  return (
    <li className={`block-row${open ? " block-row--open" : ""}`} data-uid={block.uid}>
      <div className="block-row__head">
        <button
          type="button"
          className="block-row__title"
          aria-expanded={open}
          onClick={() => actions.select(open ? null : block.uid)}
        >
          <BlockIcon type={block.type} />
          <span>
            <strong>{label}</strong> <span className="hint">{summary(block)}</span>
          </span>
          {(errors.size > 0 || unsaved.size > 0) && <span className="badge badge--error">{ed.zones.hasErrors}</span>}
        </button>
        <div className="block-row__actions" role="group" aria-label={ed.zones.blockActions(label)}>
          <button type="button" className="button button--small" disabled={index === 0} onClick={() => actions.shift(block.uid, -1)}>
            {ed.zones.up}
          </button>
          <button type="button" className="button button--small" disabled={index === count - 1} onClick={() => actions.shift(block.uid, 1)}>
            {ed.zones.down}
          </button>
          <button type="button" className="button button--small" onClick={() => setMoving(true)}>
            {ed.zones.moveTo}
          </button>
          <button type="button" className="button button--small" onClick={() => actions.duplicate(block.uid)}>
            {ed.zones.duplicate}
          </button>
          <button type="button" className="button button--small button--danger" onClick={() => actions.remove(block.uid)}>
            {ed.zones.remove}
          </button>
        </div>
      </div>
      {open && (
        <div className="block-row__body">
          <VariantPicker
            variants={catalog.variants[block.type]}
            value={block.variant}
            error={errors.get("variant")}
            onChange={(variant) => actions.setVariant(block.uid, variant)}
          />
          <SchemaForm
            schema={schema}
            data={block.data}
            idPrefix={`f-${block.uid}`}
            errors={errors}
            unsaved={unsaved}
            pages={props.pages}
            onChange={(path, value) => actions.editField(block.uid, path, value)}
          />
        </div>
      )}
      {moving && (
        <MoveDialog
          label={label}
          zones={zonesFor(doc, catalog, block.type, Object.entries(doc.zones).find(([, b]) => b.includes(block))?.[0])}
          catalog={catalog}
          layout={doc.layout}
          onClose={() => setMoving(false)}
          onMove={(zone) => {
            setMoving(false);
            actions.moveTo(block.uid, zone);
          }}
        />
      )}
    </li>
  );
}

export function ZoneList(props: Props) {
  const { doc, catalog, actions } = props;
  const [adding, setAdding] = useState<string | null>(null);
  const layout = catalog.layouts[doc.layout];
  if (!layout) return null;
  return (
    <div className="zones">
      {Object.entries(layout.zones).map(([name, zone]) => {
        const blocks = doc.zones[name] ?? [];
        const room = hasRoom(doc, catalog, name);
        return (
          <section key={name} className="zone" aria-labelledby={`zone-${name}`}>
            <h2 id={`zone-${name}`} className="zone__title">
              {zone.label}
            </h2>
            {props.errors.get(`zone:${name}`) && (
              <p className="form__error">{[...props.errors.get(`zone:${name}`)!.values()].join(" ")}</p>
            )}
            {blocks.length === 0 && <p className="hint">{ed.zones.empty}</p>}
            <ul className="zone__blocks">
              {blocks.map((block, index) => (
                <BlockRow key={block.uid} block={block} index={index} count={blocks.length} props={props} />
              ))}
            </ul>
            <button type="button" className="button" disabled={!room} onClick={() => setAdding(name)}>
              {ed.zones.add}
            </button>
            {!room && <p className="hint">{ed.zones.full}</p>}
          </section>
        );
      })}
      {adding && (
        <AddBlockDialog
          zone={layout.zones[adding]?.label ?? adding}
          types={layout.zones[adding]?.blocks ?? []}
          catalog={catalog}
          onClose={() => setAdding(null)}
          onAdd={(type) => {
            actions.add(adding, type);
            setAdding(null);
          }}
        />
      )}
    </div>
  );
}
