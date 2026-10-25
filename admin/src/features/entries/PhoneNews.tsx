import { useEffect, useId, useState } from "react";
import { errorMessage } from "../../api/client";
import { createEntry, fetchCollections, fetchEntryChecks, publishEntry, saveEntryDraft, type CollectionInfo } from "../../api/entries";
import { uploadMedia } from "../../api/media";
import { Permission } from "../../session/can";
import { useSession } from "../../session/context";
import { en } from "../../text/entries";
import { FormDialog } from "../../ui/FormDialog";
import { zurichToday } from "../editor/schedule/siteTime";
import { firstField } from "./entryDocument";

const TEXT_MAX = 300;

interface Props {
  onClose: () => void;
  onDone: (text: string) => void;
}

function escapeHtml(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/** "Notizia" dal telefono (D-97, D-153, D-154): titolo, poche righe, una foto. Chi può
 * pubblicare la mette online con gli stessi controlli; gli altri la salvano in bozza. */
export function PhoneNews({ onClose, onDone }: Props) {
  const { site, can } = useSession();
  const key = site.collections[0]?.key ?? "";
  const [info, setInfo] = useState<CollectionInfo | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [alt, setAlt] = useState("");
  const id = useId();
  const publisher = can(Permission.publish);

  useEffect(() => {
    let active = true;
    fetchCollections().then(
      (found) => {
        if (active) setInfo(found.find((c) => c.key === key) ?? null);
      },
      (error: unknown) => {
        if (active) setFailure(errorMessage(error));
      },
    );
    return () => {
      active = false;
    };
  }, [key]);

  const schema = info?.schema;
  const textField = schema ? firstField(schema, (spec) => Boolean(spec["x-multiline"] || spec["x-richtext"])) : null;
  const photoField = schema ? firstField(schema, (spec) => spec["x-media"] === "image") : null;
  const dateField = schema ? firstField(schema, (spec) => Boolean(spec["x-date"])) : null;
  const richText = Boolean(textField && schema?.properties?.[textField]?.["x-richtext"]);

  async function submit() {
    const name = title.trim();
    // Prima la foto: se il caricamento non riesce non resta una notizia vuota.
    const photo = file && photoField ? (await uploadMedia(file, alt)).media.id : null;
    const created = await createEntry(key, name);
    const fields: Record<string, unknown> = {};
    if (dateField) fields[dateField] = zurichToday();
    if (textField && text.trim()) fields[textField] = richText ? `<p>${escapeHtml(text.trim())}</p>` : text.trim();
    if (photoField && photo !== null) fields[photoField] = photo;
    const version = await saveEntryDraft(created.id, 1, { title: name, fields, seo: {} });
    if (!publisher) {
      onDone(en.phone.saved(name));
      return;
    }
    const checks = await fetchEntryChecks(created.id).catch(() => null);
    if (checks && checks.blocking.length > 0) {
      onDone(en.phone.blocked(name));
      return;
    }
    await publishEntry(created.id, version);
    onDone(en.phone.published(name));
  }

  const ready = info !== null && title.trim().length > 0 && (!file || alt.trim().length > 0);
  return (
    <FormDialog
      title={en.phone.title}
      submitLabel={publisher ? en.phone.publish : en.phone.save}
      canSubmit={ready}
      onClose={onClose}
      onSubmit={submit}
    >
      {!info && !failure && <p role="status">{en.loading}</p>}
      {failure && <p role="alert">{failure}</p>}
      <div className="field">
        <label htmlFor={`${id}-title`}>{en.phone.headline}</label>
        <input id={`${id}-title`} maxLength={200} value={title} onChange={(event) => setTitle(event.target.value)} />
      </div>
      {textField && (
        <div className="field">
          <label htmlFor={`${id}-text`}>{en.phone.text}</label>
          <textarea
            id={`${id}-text`}
            rows={4}
            maxLength={TEXT_MAX}
            value={text}
            aria-describedby={`${id}-text-help`}
            onChange={(event) => setText(event.target.value)}
          />
          <p id={`${id}-text-help`} className="hint">
            {en.phone.textHelp}
          </p>
        </div>
      )}
      {photoField && (
        <div className="field">
          <label htmlFor={`${id}-photo`}>{en.phone.photo}</label>
          {/* D-153: niente "capture": il telefono chiede se scattare o scegliere dalla galleria */}
          <input
            id={`${id}-photo`}
            type="file"
            accept="image/*"
            aria-describedby={`${id}-photo-help`}
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
          <p id={`${id}-photo-help`} className="hint">
            {en.phone.photoHelp}
          </p>
        </div>
      )}
      {file && (
        <div className="field">
          <label htmlFor={`${id}-alt`}>{en.phone.alt} *</label>
          <input id={`${id}-alt`} maxLength={250} value={alt} aria-describedby={`${id}-alt-help`} onChange={(event) => setAlt(event.target.value)} />
          <p id={`${id}-alt-help`} className="hint">
            {en.phone.altHelp}
          </p>
        </div>
      )}
    </FormDialog>
  );
}
