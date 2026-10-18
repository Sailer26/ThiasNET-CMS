// Pesi e date all'uso svizzero italiano.
const UNITS = ["byte", "kB", "MB", "GB"] as const;
const STEP = 1024;

export function formatBytes(bytes: number): string {
  let value = bytes;
  let unit = 0;
  while (value >= STEP && unit < UNITS.length - 1) {
    value /= STEP;
    unit += 1;
  }
  const digits = unit === 0 || value >= 10 ? 0 : 1;
  // Virgola decimale come sul sito (render_media.size_label), uguale in ogni browser.
  return `${value.toFixed(digits).replace(".", ",")} ${UNITS[unit]}`;
}

/** Percentuale intera dello spazio usato (mai sopra 100). */
export function usedPercent(used: number, quota: number): number {
  return quota > 0 ? Math.min(100, Math.round((used / quota) * 100)) : 0;
}
