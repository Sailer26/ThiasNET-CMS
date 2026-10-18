import { useId } from "react";
import type { Variants } from "../../../api/catalog";
import { ed } from "../../../text/editor";

interface Props {
  variants: Variants | undefined;
  value: string | null;
  error?: string | undefined;
  onChange: (variant: string) => void;
}

/** Varianti del tema scelte da miniature (D-03); le miniature sono file del tema, solo lette. */
export function VariantPicker({ variants, value, error, onChange }: Props) {
  const name = useId();
  if (!variants) return null;
  const current = value ?? variants.default;
  return (
    <fieldset className={`field variants${error ? " field--error" : ""}`}>
      <legend>{ed.zones.variant}</legend>
      <div className="variants__options">
        {Object.entries(variants.options).map(([key, option]) => (
          <label key={key} className={`variant${key === current ? " variant--active" : ""}`}>
            <input type="radio" name={name} checked={key === current} onChange={() => onChange(key)} />
            <img src={option.thumbnail_url} alt="" width={120} height={80} loading="lazy" />
            <span>{option.label}</span>
          </label>
        ))}
      </div>
      {error && <p className="form__error">{error}</p>}
    </fieldset>
  );
}
