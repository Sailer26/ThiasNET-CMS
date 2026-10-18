// Campi dei moduli generati dagli schemi (D-106, D-112). Ogni campo riceve valore e onChange;
// `undefined` toglie la chiave dal documento.
import { useId, type ReactNode } from "react";
import type { FieldSchema } from "../../../api/catalog";
import { MediaChoice } from "../../media-picker/MediaChoice";
import { ed } from "../../../text/editor";
import { completeUrl } from "./safeUrl";
import { length } from "./validate";

export const TEXTAREA_FROM = 200;
const COUNTER_FROM = 0.8; // il contatore compare vicino al limite

export interface FieldProps<T> {
  id: string;
  spec: FieldSchema;
  value: T | undefined;
  onChange: (value: T | undefined) => void;
  required: boolean;
  error?: string | undefined;
  unsaved?: string | undefined;
  pages?: string[];
}

function describedBy(id: string, spec: FieldSchema, error?: string, unsaved?: string): string | undefined {
  const ids = [spec.description ? `${id}-help` : "", error || unsaved ? `${id}-problem` : ""].filter(Boolean);
  return ids.length ? ids.join(" ") : undefined;
}

export function FieldFrame({
  id,
  spec,
  required,
  error,
  unsaved,
  extra,
  children,
}: {
  id: string;
  spec: FieldSchema;
  required: boolean;
  error?: string | undefined;
  unsaved?: string | undefined;
  extra?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className={`field${error ? " field--error" : ""}`}>
      <label htmlFor={id} id={`${id}-label`}>
        {spec.title}
        {required && <span className="field__required"> ({ed.required})</span>}
      </label>
      {children}
      <div className="field__meta">
        {spec.description && (
          <p id={`${id}-help`} className="hint">
            {spec.description}
          </p>
        )}
        {extra}
      </div>
      {(error || unsaved) && (
        <p id={`${id}-problem`} className="form__error">
          {error ?? `${ed.save.unsavedField} (${unsaved})`}
        </p>
      )}
    </div>
  );
}

function Counter({ value, max }: { value: string; max: number | undefined }) {
  if (max === undefined || length(value) < max * COUNTER_FROM) return null;
  return <span className="field__counter">{ed.fields.counter(length(value), max)}</span>;
}

export function TextField({ id, spec, value, onChange, required, error, unsaved, pages }: FieldProps<string>) {
  const text = value ?? "";
  const isUrl = spec.format === "safe-url";
  const listId = useId();
  const common = {
    id,
    value: text,
    "aria-describedby": describedBy(id, spec, error, unsaved),
    "aria-invalid": error || unsaved ? true : undefined,
    onChange: (event: { target: { value: string } }) => onChange(event.target.value === "" ? undefined : event.target.value),
  };
  // Area di testo solo per testi lunghi liberi: link, email e telefono stanno su una riga.
  const long = !isUrl && !spec.pattern && (spec.maxLength ?? 0) > TEXTAREA_FROM;
  return (
    <FieldFrame
      id={id}
      spec={spec}
      required={required}
      error={error}
      unsaved={unsaved}
      extra={<Counter value={text} max={spec.maxLength} />}
    >
      {long ? (
        <textarea rows={3} {...common} />
      ) : (
        <input
          {...common}
          type={isUrl ? "text" : spec.pattern?.includes("@") ? "email" : spec.pattern?.startsWith("^\\+?") ? "tel" : "text"}
          inputMode={isUrl ? "url" : undefined}
          autoCapitalize={isUrl ? "none" : undefined}
          spellCheck={isUrl ? false : undefined}
          list={isUrl && pages?.length ? listId : undefined}
          onBlur={
            isUrl && text && completeUrl(text) !== text ? () => onChange(completeUrl(text)) : undefined
          }
        />
      )}
      {isUrl && pages?.length ? (
        <datalist id={listId}>
          {pages.map((path) => (
            <option key={path} value={path} />
          ))}
        </datalist>
      ) : null}
    </FieldFrame>
  );
}

export function NumberField({ id, spec, value, onChange, required, error, unsaved }: FieldProps<number>) {
  return (
    <FieldFrame id={id} spec={spec} required={required} error={error} unsaved={unsaved}>
      <input
        id={id}
        type="number"
        step={spec.type === "integer" ? 1 : "any"}
        min={spec.minimum}
        max={spec.maximum}
        value={value ?? ""}
        aria-describedby={describedBy(id, spec, error, unsaved)}
        onChange={(event) => {
          const raw = event.target.value;
          onChange(raw === "" || Number.isNaN(Number(raw)) ? undefined : Number(raw));
        }}
      />
    </FieldFrame>
  );
}

export function BooleanField({ id, spec, value, onChange, error }: FieldProps<boolean>) {
  return (
    <div className={`field field--check${error ? " field--error" : ""}`}>
      <label htmlFor={id}>
        <input
          id={id}
          type="checkbox"
          checked={value === true}
          aria-describedby={spec.description ? `${id}-help` : undefined}
          onChange={(event) => onChange(event.target.checked ? true : undefined)}
        />
        {spec.title}
      </label>
      {spec.description && (
        <p id={`${id}-help`} className="hint">
          {spec.description}
        </p>
      )}
      {error && (
        <p id={`${id}-problem`} className="form__error">
          {error}
        </p>
      )}
    </div>
  );
}

export function ChoiceField({ id, spec, value, onChange, required, error, unsaved }: FieldProps<string | number>) {
  const options = spec.enum ?? [];
  const titles = spec["x-enum-titles"] ?? options.map(String);
  return (
    <fieldset className={`field choice${error ? " field--error" : ""}`} aria-describedby={describedBy(id, spec, error, unsaved)}>
      <legend>
        {spec.title}
        {required && <span className="field__required"> ({ed.required})</span>}
      </legend>
      <div className="choice__options">
        {options.map((option, index) => (
          <label key={String(option)} className="choice__option">
            <input
              type="radio"
              id={index === 0 ? id : undefined} // "Vai al campo" porta alla prima scelta
              name={id}
              checked={value === option}
              onChange={() => onChange(option)}
            />
            {titles[index]}
          </label>
        ))}
      </div>
      {spec.description && (
        <p id={`${id}-help`} className="hint">
          {spec.description}
        </p>
      )}
      {(error || unsaved) && (
        <p id={`${id}-problem`} className="form__error">
          {error ?? `${ed.save.unsavedField} (${unsaved})`}
        </p>
      )}
    </fieldset>
  );
}

/** Immagine o documento dalla libreria (D-111); `x-media: "file"` = documento PDF. */
export function MediaField({ id, spec, value, onChange, required, error, unsaved }: FieldProps<number>) {
  return (
    <FieldFrame id={id} spec={spec} required={required} error={error} unsaved={unsaved}>
      <MediaChoice
        id={id}
        kind={spec["x-media"] === "file" ? "document" : "image"}
        value={value}
        onChange={onChange}
        describedBy={describedBy(id, spec, error, unsaved)}
      />
    </FieldFrame>
  );
}
