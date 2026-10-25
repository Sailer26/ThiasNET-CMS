// Modulo di un blocco generato dal suo schema (D-106, D-112).
import { useState } from "react";
import type { FieldSchema } from "../../../api/catalog";
import { MediaPicker } from "../../media-picker/MediaPicker";
import { ed } from "../../../text/editor";
import type { Data, Path } from "../model/document";
import { RichTextField } from "../richtext/RichText";
import { BooleanField, ChoiceField, DateField, DateTimeField, MediaField, NumberField, TextField } from "./fields";
import { effectiveField } from "./validate";

export interface FormProps {
  schema: FieldSchema;
  data: Data;
  idPrefix: string;
  /** Errori del server e campi non salvati, per percorso ("items/0/caption"). */
  errors: ReadonlyMap<string, string>;
  unsaved: ReadonlyMap<string, string>;
  pages: string[];
  onChange: (path: Path, value: unknown) => void;
}

export function fieldId(prefix: string, path: Path): string {
  return `${prefix}-${path.join("-")}`;
}

function Field({ name, spec, required, path, props }: { name: string; spec: FieldSchema; required: boolean; path: Path; props: FormProps }) {
  const key = path.join("/");
  const common = {
    id: fieldId(props.idPrefix, path),
    spec,
    required,
    error: props.errors.get(key),
    unsaved: props.unsaved.get(key),
    pages: props.pages,
  };
  const value = path.reduce<unknown>((node, part) => (node as Record<string | number, unknown> | undefined)?.[part], props.data);
  const set = (next: unknown) => props.onChange(path, next);
  if (spec["x-media"]) return <MediaField {...common} value={value as number | undefined} onChange={set} />;
  if (spec["x-richtext"]) return <RichTextField {...common} value={value as string | undefined} onChange={set} />;
  if (spec["x-date"]) return <DateField {...common} value={value as string | undefined} onChange={set} />;
  if (spec["x-datetime"]) return <DateTimeField {...common} value={value as string | undefined} onChange={set} />;
  if (spec.enum) return <ChoiceField {...common} value={value as string | number | undefined} onChange={set} />;
  if (spec.type === "boolean") return <BooleanField {...common} value={value as boolean | undefined} onChange={set} />;
  if (spec.type === "integer" || spec.type === "number") {
    return <NumberField {...common} value={value as number | undefined} onChange={set} />;
  }
  if (spec.type === "array") return <ItemsField name={name} spec={spec} path={path} props={props} value={value} />;
  return <TextField {...common} value={value as string | undefined} onChange={set} />;
}

let keySeq = 0;
const nextKey = () => `item-${++keySeq}`;

/** Chiave stabile di ogni elemento (D-128): tenuta solo qui, mai salvata nel documento.
 * Se il numero cambia da fuori (annulla) gli elementi in più usano la posizione. */
function keyAt(keys: string[], index: number): string {
  return keys[index] ?? `pos-${index}`;
}

function ItemsField({ spec, path, props, value }: { name: string; spec: FieldSchema; path: Path; props: FormProps; value: unknown }) {
  const items = Array.isArray(value) ? (value as Data[]) : [];
  const [keys, setKeys] = useState<string[]>(() => items.map(() => nextKey()));
  const itemSpec = spec.items ?? {};
  const label = itemSpec.title ?? spec.title ?? "";
  const full = spec.maxItems !== undefined && items.length >= spec.maxItems;
  // Galleria e file: "Aggiungi immagini/documenti" sceglie più file in una volta (D-111).
  const mediaKey = Object.entries(itemSpec.properties ?? {}).find(([, field]) => field["x-media"])?.[0];
  const mediaKind = itemSpec.properties?.[mediaKey ?? ""]?.["x-media"] === "file" ? "document" : "image";
  const [picking, setPicking] = useState(false);
  const room = spec.maxItems === undefined ? Infinity : spec.maxItems - items.length;
  const update = (next: Data[]) => props.onChange(path, next.length ? next : undefined);
  const swap = (from: number, to: number) => {
    const next = [...items];
    [next[from], next[to]] = [next[to]!, next[from]!];
    const nextKeys = items.map((_, i) => keyAt(keys, i));
    [nextKeys[from], nextKeys[to]] = [nextKeys[to]!, nextKeys[from]!];
    setKeys(nextKeys);
    update(next);
  };
  const removeAt = (index: number) => {
    setKeys(items.map((_, i) => keyAt(keys, i)).filter((_, i) => i !== index));
    update(items.filter((_, i) => i !== index));
  };
  const append = (added: Data[]) => {
    setKeys([...items.map((_, i) => keyAt(keys, i)), ...added.map(() => nextKey())]);
    update([...items, ...added]);
  };
  return (
    <fieldset className="field items">
      <legend>{spec.title}</legend>
      {spec.description && <p className="hint">{spec.description}</p>}
      {items.map((item, index) => (
        <fieldset key={keyAt(keys, index)} className="items__item">
          <legend>{ed.fields.items.item(label, index + 1)}</legend>
          <FieldsOf schema={itemSpec} data={item} prefix={[...path, index]} props={props} />
          <div className="items__actions">
            <button type="button" className="button button--small" disabled={index === 0} onClick={() => swap(index, index - 1)}>
              {ed.fields.items.up}
            </button>
            <button type="button" className="button button--small" disabled={index === items.length - 1} onClick={() => swap(index, index + 1)}>
              {ed.fields.items.down}
            </button>
            <button type="button" className="button button--small button--danger" onClick={() => removeAt(index)}>
              {ed.fields.items.remove}
            </button>
          </div>
        </fieldset>
      ))}
      {mediaKey && (
        <button type="button" className="button button--small" disabled={full} onClick={() => setPicking(true)}>
          {mediaKind === "image" ? ed.media.addImages : ed.media.addFiles}
        </button>
      )}
      {picking && mediaKey && (
        <MediaPicker
          kind={mediaKind}
          multiple
          {...(room !== Infinity ? { limit: room } : {})}
          onClose={() => setPicking(false)}
          onChoose={(chosen) => {
            setPicking(false);
            append(chosen.map((media) => ({ [mediaKey]: media.id })));
          }}
        />
      )}
      <button type="button" className="button button--small" disabled={full} onClick={() => append([{}])}>
        {ed.fields.items.add}
      </button>
    </fieldset>
  );
}

function FieldsOf({ schema, data, prefix, props }: { schema: FieldSchema; data: Data; prefix: Path; props: FormProps }) {
  const required = new Set(schema.required ?? []);
  return (
    <>
      {Object.keys(schema.properties ?? {}).map((name) => (
        <Field
          key={name}
          name={name}
          spec={effectiveField(schema, data, name)}
          required={required.has(name)}
          path={[...prefix, name]}
          props={props}
        />
      ))}
    </>
  );
}

export function SchemaForm(props: FormProps) {
  if (Object.keys(props.schema.properties ?? {}).length === 0) {
    return <p className="hint">{ed.zones.noSettings}</p>;
  }
  return (
    <div className="schema-form">
      <FieldsOf schema={props.schema} data={props.data} prefix={[]} props={props} />
    </div>
  );
}
