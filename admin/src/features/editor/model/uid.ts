// uid dei blocchi creati dal pannello (D-39, D-103): 32 caratteri esadecimali.
// crypto.getRandomValues funziona anche fuori da https (randomUUID no).
const BYTES = 16;

export const UID_RE = /^[0-9a-f]{32}$/;

export function newUid(taken: ReadonlySet<string> = new Set()): string {
  for (;;) {
    const bytes = crypto.getRandomValues(new Uint8Array(BYTES));
    const uid = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
    if (!taken.has(uid)) return uid;
  }
}
