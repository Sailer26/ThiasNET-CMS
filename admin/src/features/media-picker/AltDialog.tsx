import { useId, useState } from "react";
import { updateAlt, type Media } from "../../api/media";
import { ed } from "../../text/editor";
import { FormDialog } from "../../ui/FormDialog";
import { useMedia } from "./MediaContext";

/** Testo alternativo dall'editor: senza, la pagina non si pubblica (D-77, D-111). */
export function AltDialog({ media, onClose }: { media: Media; onClose: () => void }) {
  const [alt, setAlt] = useState(media.alt);
  const { remember } = useMedia();
  const altId = useId();
  return (
    <FormDialog
      title={ed.media.altTitle(media.name)}
      submitLabel={ed.media.altSave}
      canSubmit={alt.trim() !== media.alt.trim()}
      onClose={onClose}
      onSubmit={async () => {
        remember(await updateAlt(media.id, media.version, alt.trim()));
        onClose();
      }}
    >
      {media.thumbnail_url && (
        <img className="alt-preview" src={media.thumbnail_url} alt="" width={240} height={160} />
      )}
      <div className="field">
        <label htmlFor={altId}>{ed.media.alt}</label>
        <input
          id={altId}
          value={alt}
          maxLength={250}
          aria-describedby={`${altId}-help`}
          onChange={(event) => setAlt(event.target.value)}
        />
        <span id={`${altId}-help`} className="hint">
          {ed.media.altHelp}
        </span>
      </div>
    </FormDialog>
  );
}
