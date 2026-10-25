// Motori di ricerca e social (D-135): lo stesso blocco per le pagine e le notizie (7b).
import { MediaChoice } from "../../media-picker/MediaChoice";
import { ed } from "../../../text/editor";
import type { Seo } from "../model/document";
import { length } from "../schema/validate";

const SEO_TITLE_MAX = 70;
const SEO_DESCRIPTION_MAX = 160;

interface Props {
  seo: Seo;
  /** Il titolo della pagina o della notizia: vale anche per Google se la SEO è vuota. */
  title: string;
  /** L'indirizzo completo mostrato nell'anteprima di Google. */
  url: string;
  errors: ReadonlyMap<string, string>;
  onSeo: <K extends keyof Seo>(key: K, value: Seo[K] | undefined) => void;
}

function Problem({ id, text }: { id: string; text: string | undefined }) {
  return text ? (
    <p id={id} className="form__error">
      {text}
    </p>
  ) : null;
}

export function SeoFields({ seo, title, url, errors, onSeo }: Props) {
  const seoTitle = seo.title ?? "";
  const description = seo.description ?? "";
  return (
    <details className="seo" open={errors.has("seo/title") || errors.has("seo/description") ? true : undefined}>
      <summary>{ed.page.seo}</summary>
      <div className="field">
        <label htmlFor="seo-title">{ed.page.seoTitle}</label>
        <input
          id="seo-title"
          maxLength={SEO_TITLE_MAX}
          value={seoTitle}
          placeholder={title}
          aria-describedby="seo-title-help"
          onChange={(event) => onSeo("title", event.target.value || undefined)}
        />
        <p id="seo-title-help" className="hint">
          {ed.page.seoTitleHelp} {ed.fields.counter(length(seoTitle), SEO_TITLE_MAX)}
        </p>
        <Problem id="seo-title-problem" text={errors.get("seo/title")} />
      </div>
      <div className="field">
        <label htmlFor="seo-description">{ed.page.seoDescription}</label>
        <textarea
          id="seo-description"
          rows={3}
          maxLength={SEO_DESCRIPTION_MAX}
          value={description}
          aria-describedby="seo-description-help"
          onChange={(event) => onSeo("description", event.target.value || undefined)}
        />
        <p id="seo-description-help" className="hint">
          {ed.page.seoDescriptionHelp} {ed.fields.counter(length(description), SEO_DESCRIPTION_MAX)}
        </p>
        <Problem id="seo-description-problem" text={errors.get("seo/description")} />
      </div>
      <div className="field field--check">
        <label>
          <input
            type="checkbox"
            checked={seo.noindex === true}
            onChange={(event) => onSeo("noindex", event.target.checked ? true : undefined)}
          />
          {ed.page.noindex}
        </label>
      </div>
      <div className="field">
        <span className="field__label" id="seo-og-label">
          {ed.media.ogImage}
        </span>
        <MediaChoice
          id="seo-og_image_media_id"
          kind="image"
          value={seo.og_image_media_id}
          onChange={(id) => onSeo("og_image_media_id", id)}
          describedBy="seo-og-help"
          labelledBy="seo-og-label"
        />
        <p id="seo-og-help" className="hint">
          {ed.media.ogImageHelp}
        </p>
        <Problem id="seo-og-problem" text={errors.get("seo/og_image_media_id")} />
      </div>
      <div className="google" aria-label={ed.page.googlePreview}>
        <p className="hint">{ed.page.googlePreview}</p>
        <p className="google__url">{url}</p>
        <p className="google__title">{seoTitle || title}</p>
        <p className="google__text">{description}</p>
      </div>
    </details>
  );
}
