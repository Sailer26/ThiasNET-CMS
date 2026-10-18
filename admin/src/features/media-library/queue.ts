// Coda di caricamento (D-118): un file alla volta, stato per riga, stop con spazio esaurito.
import { ApiError, errorMessage } from "../../api/client";
import type { Media, Uploaded } from "../../api/media";

export type ItemState = "waiting" | "uploading" | "done" | "duplicate" | "error" | "skipped";

export interface QueueItem {
  key: string;
  file: File;
  state: ItemState;
  message?: string;
  media?: Media;
}

export const ALLOWED_EXT = new Set(["jpg", "jpeg", "png", "webp", "gif", "pdf"]);

export function extensionOf(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot < 0 ? "" : name.slice(dot + 1).toLowerCase();
}

/** Controllo indicativo prima dell'invio; decide sempre il server. */
export function precheck(file: File, maxBytes: number): string | null {
  if (!ALLOWED_EXT.has(extensionOf(file.name))) return "Tipo di file non ammesso: solo immagini (JPG, PNG, WebP, GIF) e PDF.";
  if (maxBytes > 0 && file.size > maxBytes) return "File troppo grande: al massimo 15 MB.";
  return null;
}

export function enqueue(files: File[], maxBytes: number, prefix = Date.now()): QueueItem[] {
  return files.map((file, index) => {
    const problem = precheck(file, maxBytes);
    return problem
      ? { key: `${prefix}-${index}`, file, state: "error", message: problem }
      : { key: `${prefix}-${index}`, file, state: "waiting" };
  });
}

type Upload = (file: File) => Promise<Uploaded>;
type Update = (items: QueueItem[]) => void;

/** Carica i file in attesa uno dopo l'altro. `stopped()` dice se l'utente ha interrotto. */
export async function runQueue(items: QueueItem[], upload: Upload, update: Update, stopped: () => boolean): Promise<QueueItem[]> {
  let current = items;
  const set = (key: string, patch: Partial<QueueItem>) => {
    current = current.map((item) => (item.key === key ? { ...item, ...patch } : item));
    update(current);
  };
  for (const item of items) {
    if (item.state !== "waiting") continue;
    if (stopped()) {
      set(item.key, { state: "skipped", message: "Interrotto" });
      continue;
    }
    set(item.key, { state: "uploading" });
    try {
      const result = await upload(item.file);
      set(item.key, { state: result.duplicate ? "duplicate" : "done", media: result.media });
    } catch (error) {
      set(item.key, { state: "error", message: errorMessage(error) });
      if (error instanceof ApiError && error.status === 507) {
        // Spazio esaurito: gli altri non entrerebbero comunque.
        for (const rest of current.filter((i) => i.state === "waiting")) set(rest.key, { state: "skipped", message: "Spazio esaurito" });
        break;
      }
    }
  }
  return current;
}
