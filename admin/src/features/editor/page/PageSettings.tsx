import { useState } from "react";
import type { Catalog } from "../../../api/catalog";
import type { Site } from "../../../api/types";
import { MediaChoice } from "../../media-picker/MediaChoice";
import { ed } from "../../../text/editor";
import { FormDialog } from "../../../ui/FormDialog";
import type { PageDocument, Seo } from "../model/document";
import { relayout } from "../model/relayout";
import { length } from "../schema/validate";

const TITLE_MAX = 200;
const SEO_TITLE_MAX = 70;
const SEO_DESCRIPTION_MAX = 160;

interface Props {
  doc: PageDocument;
  catalog: Catalog;
  site: Site;
  path: string;
  errors: ReadonlyMap<string, string>;
  onTitle: (title: string) => void;
  onLayout: (doc: PageDocument) => void;
  onSeo: <K extends keyof Seo>(key: K, value: Seo[K] | undefined) => void;
}

function Problem({ id, text }: { id: string; text: string | undefined }) {
  return text ? (
    <p id={id} className="form__error">
      {text}
    </p>
  ) : null;
}

export function PageSettings({ doc, catalog, site, path, errors, onTitle, onLayout, onSeo }: Props) {
  const [pending, setPending] = useState<ReturnType<typeof relayout> | null>(null);
  const seoTitle = doc.seo.title ?? "";
  const description = doc.seo.description ?? "";

  function chooseLayout(name: string) {
    const result = relayout(doc, catalog, name);
    if (result.dropped.length > 0) setPending(result);
    else onLayout(result.doc);
  }

  return (
    <section className="page-settings" aria-label={ed.page.settings}>
      <div className={`field${errors.get("title") ? " field--error" : ""}`}>
        <label htmlFor="page-title">{ed.page.title}</label>
        <input
          id="page-title"
          className="page-settings__title"
          maxLength={TITLE_MAX}
          value={doc.title}
          aria-describedby={errors.get("title") ? "page-title-problem" : undefined}
          onChange={(event) => onTitle(event.target.value)}
        />
        <Problem id="page-title-problem" text={errors.get("title")} />
      </div>
      <div className="field">
        <label htmlFor="page-layout">{ed.page.layout}</label>
        <select id="page-layout" value={doc.layout} onChange={(event) => chooseLayout(event.target.value)}>
          {Object.entries(catalog.layouts).map(([name, layout]) => (
            <option key={name} value={name}>
              {layout.label}
            </option>
          ))}
        </select>
        <Problem id="page-layout-problem" text={errors.get("layout")} />
      </div>
      <details className="seo" open={errors.has("seo/title") || errors.has("seo/description") ? true : undefined}>
        <summary>{ed.page.seo}</summary>
        <div className="field">
          <label htmlFor="seo-title">{ed.page.seoTitle}</label>
          <input
            id="seo-title"
            maxLength={SEO_TITLE_MAX}
            value={seoTitle}
            placeholder={doc.title}
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
              checked={doc.seo.noindex === true}
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
            value={doc.seo.og_image_media_id}
            onChange={(id) => onSeo("og_image_media_id", id)}
            describedBy="seo-og-help"
          />
          <p id="seo-og-help" className="hint">
            {ed.media.ogImageHelp}
          </p>
          <Problem id="seo-og-problem" text={errors.get("seo/og_image_media_id")} />
        </div>
        <div className="google" aria-label={ed.page.googlePreview}>
          <p className="hint">{ed.page.googlePreview}</p>
          <p className="google__url">{site.url + path}</p>
          <p className="google__title">{seoTitle || doc.title}</p>
          <p className="google__text">{description}</p>
        </div>
      </details>
      {pending && (
        <FormDialog
          title={ed.page.relayoutTitle}
          submitLabel={ed.page.relayoutConfirm}
          danger
          onClose={() => setPending(null)}
          onSubmit={async () => {
            onLayout(pending.doc);
            setPending(null);
          }}
        >
          <p>{ed.page.relayoutDropped}</p>
          <ul>
            {pending.dropped.map((block) => (
              <li key={block.uid}>{catalog.types[block.type]?.label ?? block.type}</li>
            ))}
          </ul>
        </FormDialog>
      )}
    </section>
  );
}
