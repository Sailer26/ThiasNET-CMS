// Media già noti all'editor (scelti nella pagina o appena caricati): miniature e testo
// alternativo senza una richiesta per ogni campo (D-111).
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { errorMessage } from "../../api/client";
import { mediaByIds, type Media } from "../../api/media";

interface MediaStore {
  get: (id: number) => Media | undefined;
  remember: (media: Media) => void;
  error: string | null;
}

const MediaContext = createContext<MediaStore | null>(null);

export function useMedia(): MediaStore {
  const store = useContext(MediaContext);
  if (!store) throw new Error("useMedia fuori da MediaProvider");
  return store;
}

/** Tutti gli id di media in un documento: campi "media_id" e immagine per i social. */
export function mediaIdsIn(value: unknown, found = new Set<number>()): Set<number> {
  if (Array.isArray(value)) value.forEach((item) => mediaIdsIn(item, found));
  else if (value && typeof value === "object") {
    for (const [key, inner] of Object.entries(value)) {
      if ((key === "media_id" || key === "og_image_media_id") && typeof inner === "number") found.add(inner);
      else mediaIdsIn(inner, found);
    }
  }
  return found;
}

export function MediaProvider({ ids, children }: { ids: number[]; children: ReactNode }) {
  const [known, setKnown] = useState<ReadonlyMap<number, Media>>(new Map());
  const [error, setError] = useState<string | null>(null);
  const missing = ids.filter((id) => !known.has(id)).sort((a, b) => a - b).join(",");

  useEffect(() => {
    if (!missing) return;
    let active = true;
    mediaByIds(missing.split(",").map(Number)).then(
      (found) => {
        if (!active) return;
        setKnown((current) => new Map([...found.map((m) => [m.id, m] as const), ...current]));
      },
      (failure: unknown) => {
        if (active) setError(errorMessage(failure));
      },
    );
    return () => {
      active = false;
    };
  }, [missing]);

  const remember = useCallback((media: Media) => {
    setKnown((current) => new Map(current).set(media.id, media));
  }, []);
  const store = useMemo<MediaStore>(() => ({ get: (id) => known.get(id), remember, error }), [known, remember, error]);
  return <MediaContext.Provider value={store}>{children}</MediaContext.Provider>;
}
