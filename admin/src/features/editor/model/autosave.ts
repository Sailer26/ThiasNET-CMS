// Salvataggio automatico (D-104), senza React: una richiesta alla volta, attesa dopo l'ultima
// modifica, nessun timer senza modifiche (D-90). L'orologio si sostituisce nei test.
import { ApiError, errorMessage, isConflict } from "../../../api/client";
import type { PageDocument } from "./document";

export const SAVE_DELAY_MS = 1500;

export type SaveState =
  | { kind: "saved"; at: Date | null }
  | { kind: "pending" }
  | { kind: "saving" }
  | { kind: "error"; message: string }
  | { kind: "expired" }
  | { kind: "conflict"; error: ApiError };

export interface Clock {
  schedule: (run: () => void, ms: number) => unknown;
  cancel: (handle: unknown) => void;
  now: () => Date;
}

export const realClock: Clock = {
  schedule: (run, ms) => setTimeout(run, ms),
  cancel: (handle) => clearTimeout(handle as ReturnType<typeof setTimeout>),
  now: () => new Date(),
};

type Save = (doc: PageDocument, version: number) => Promise<number>;

export class Autosave {
  private version: number;
  private latest: PageDocument | null = null;
  private savedJson: string;
  private timer: unknown = null;
  private running: Promise<void> | null = null;
  private blocked = false;
  private state: SaveState;
  private readonly listeners = new Set<(state: SaveState) => void>();

  constructor(
    private readonly save: Save,
    version: number,
    saved: PageDocument,
    private readonly clock: Clock = realClock,
    private readonly delay = SAVE_DELAY_MS,
  ) {
    this.version = version;
    this.savedJson = JSON.stringify(saved);
    this.state = { kind: "saved", at: null };
  }

  get current(): SaveState {
    return this.state;
  }

  get draftVersion(): number {
    return this.version;
  }

  get dirty(): boolean {
    return this.latest !== null && JSON.stringify(this.latest) !== this.savedJson;
  }

  subscribe(listener: (state: SaveState) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private set(state: SaveState): void {
    this.state = state;
    this.listeners.forEach((listener) => listener(state));
  }

  /** Il documento è cambiato: si salva dopo una pausa. */
  change(doc: PageDocument): void {
    this.latest = doc;
    if (!this.dirty) {
      if (this.state.kind === "pending") this.set({ kind: "saved", at: null });
      return;
    }
    if (this.blocked) return;
    if (this.state.kind !== "saving" && this.state.kind !== "pending") this.set({ kind: "pending" });
    this.restartTimer();
  }

  private restartTimer(): void {
    if (this.timer !== null) this.clock.cancel(this.timer);
    this.timer = this.clock.schedule(() => {
      this.timer = null;
      void this.flush();
    }, this.delay);
  }

  /** Salva subito ciò che manca. true se alla fine tutto è salvato. */
  async flush(): Promise<boolean> {
    if (this.timer !== null) {
      this.clock.cancel(this.timer);
      this.timer = null;
    }
    while (this.running) await this.running;
    if (this.blocked) return false;
    if (!this.dirty) return this.state.kind === "saved";
    this.running = this.run();
    try {
      await this.running;
    } finally {
      this.running = null;
    }
    return !this.dirty && this.state.kind === "saved";
  }

  private async run(): Promise<void> {
    while (this.dirty && !this.blocked) {
      const doc = this.latest!;
      const json = JSON.stringify(doc);
      this.set({ kind: "saving" });
      try {
        this.version = await this.save(doc, this.version);
        this.savedJson = json;
        this.set({ kind: "saved", at: this.clock.now() });
      } catch (error) {
        this.fail(error);
        return;
      }
    }
  }

  private fail(error: unknown): void {
    if (isConflict(error)) {
      this.blocked = true; // mai salvare sopra a qualcun altro senza una scelta (D-92)
      this.set({ kind: "conflict", error: error as ApiError });
    } else if (error instanceof ApiError && error.status === 401) {
      this.set({ kind: "expired" }); // dopo il nuovo accesso: retry()
    } else {
      this.set({ kind: "error", message: errorMessage(error) });
    }
  }

  retry(): Promise<boolean> {
    return this.flush();
  }

  /** "Tieni la mia": si riparte dalla versione attuale del server e si salva sopra. */
  keepMine(serverVersion: number): Promise<boolean> {
    this.version = serverVersion;
    this.blocked = false;
    this.savedJson = "";
    return this.flush();
  }

  /** "Carica la sua" (o pagina ricaricata): nuova base, nulla da salvare. */
  reset(version: number, doc: PageDocument): void {
    if (this.timer !== null) this.clock.cancel(this.timer);
    this.timer = null;
    this.version = version;
    this.latest = null;
    this.blocked = false;
    this.savedJson = JSON.stringify(doc);
    this.set({ kind: "saved", at: null });
  }

  dispose(): void {
    if (this.timer !== null) this.clock.cancel(this.timer);
    this.timer = null;
    this.listeners.clear();
  }
}
