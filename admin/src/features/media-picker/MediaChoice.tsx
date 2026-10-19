import { paths } from "../../router/router";
import { useRef, useState } from "react";
import type { MediaKind } from "../../api/media";
import { ed } from "../../text/editor";
import { AltDialog } from "./AltDialog";
import { useMedia } from "./MediaContext";
import { MediaPicker } from "./MediaPicker";

interface Props {
  id: string;
  kind: MediaKind;
  value: number | undefined;
  onChange: (id: number | undefined) => void;
  describedBy?: string | undefined;
  /** Id dell'etichetta del campo: il pulsante si annuncia come "Immagine, Scegli immagine". */
  labelledBy?: string | undefined;
}

/** Il media scelto in un campo: miniatura, nome, testo alternativo; Scegli/Cambia/Togli. */
export function MediaChoice({ id, kind, value, onChange, describedBy, labelledBy }: Props) {
  const { get } = useMedia();
  const [picking, setPicking] = useState(false);
  const [editingAlt, setEditingAlt] = useState(false);
  const chooseRef = useRef<HTMLButtonElement>(null);
  const media = value ? get(value) : undefined;
  const noAlt = media?.kind === "image" && !media.alt.trim();
  return (
    <div className="media-field">
      {value ? (
        <div className="media-field__chosen">
          {media?.thumbnail_url && <img src={media.thumbnail_url} alt="" width={96} height={72} />}
          <div>
            <strong>{media?.name ?? ed.fields.media.chosen(value)}</strong>
            {media?.kind === "image" && (
              <p className={noAlt ? "form__error" : "hint"}>
                {noAlt ? ed.media.altMissing : `${ed.media.alt}: ${media.alt}`}
              </p>
            )}
          </div>
        </div>
      ) : (
        <p className="hint">{ed.fields.media.none}</p>
      )}
      <div className="form__actions">
        <button
          ref={chooseRef}
          id={id}
          type="button"
          className="button button--small"
          aria-labelledby={labelledBy ? `${labelledBy} ${id}` : undefined}
          aria-describedby={describedBy}
          onClick={() => setPicking(true)}
        >
          {value ? ed.media.change : kind === "image" ? ed.media.chooseImage : ed.media.chooseDocument}
        </button>
        {media?.kind === "image" && (
          <button
            type="button"
            className={`button button--small${noAlt ? " button--primary" : ""}`}
            onClick={() => setEditingAlt(true)}
          >
            {ed.media.altButton}
          </button>
        )}
        {value !== undefined && (
          <a className="button button--small" href={`${paths.media}?apri=${value}`} target="_blank" rel="noopener noreferrer">
            {ed.media.openLibrary}
          </a>
        )}
        {value !== undefined && (
          <button
            type="button"
            className="button button--small button--danger"
            onClick={() => {
              onChange(undefined);
              chooseRef.current?.focus(); // il pulsante premuto sparisce: il focus non si perde
            }}
          >
            {ed.media.remove}
          </button>
        )}
      </div>
      {picking && (
        <MediaPicker
          kind={kind}
          onClose={() => setPicking(false)}
          onChoose={([chosen]) => {
            setPicking(false);
            if (chosen) onChange(chosen.id);
          }}
        />
      )}
      {editingAlt && media && <AltDialog media={media} onClose={() => setEditingAlt(false)} />}
    </div>
  );
}
