// Ora svizzera (D-122): data e ora scelte nel pannello → istante con il fuso, senza librerie.
// Il server non ha i fusi su Windows (niente tzdata): la conversione la fa il browser con Intl.
export const SITE_ZONE = "Europe/Zurich";
const MINUTE = 60_000;
const OFFSETS = [120, 60]; // estate (CEST), inverno (CET): nelle ore doppie vale la prima

const parts = new Intl.DateTimeFormat("en-US", {
  timeZone: SITE_ZONE,
  hourCycle: "h23",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

/** Differenza dall'UTC (minuti) a Zurigo in un dato istante. */
export function zurichOffset(utcMs: number): number {
  const values = Object.fromEntries(parts.formatToParts(new Date(utcMs)).map((p) => [p.type, p.value]));
  const wall = Date.UTC(Number(values.year), Number(values.month) - 1, Number(values.day), Number(values.hour), Number(values.minute));
  return Math.round((wall - Math.floor(utcMs / MINUTE) * MINUTE) / MINUTE);
}

export type Converted = { iso: string; utcMs: number } | { error: "invalid" | "missing_hour" };

/** "2026-11-01" + "08:00" (ora di Zurigo) → ISO con il fuso, es. "2026-11-01T08:00:00+01:00". */
export function zurichToIso(date: string, time: string): Converted {
  const d = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  const t = /^(\d{2}):(\d{2})$/.exec(time);
  if (!d || !t) return { error: "invalid" };
  const wall = Date.UTC(Number(d[1]), Number(d[2]) - 1, Number(d[3]), Number(t[1]), Number(t[2]));
  for (const offset of OFFSETS) {
    const utcMs = wall - offset * MINUTE;
    if (zurichOffset(utcMs) === offset) {
      const sign = `+0${offset / 60}:00`;
      return { iso: `${date}T${time}:00${sign}`, utcMs };
    }
  }
  return { error: "missing_hour" }; // l'ora saltata al passaggio all'ora legale
}

const longDate = new Intl.DateTimeFormat("it-CH", {
  timeZone: SITE_ZONE,
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
});
const clock = new Intl.DateTimeFormat("it-CH", { timeZone: SITE_ZONE, hour: "2-digit", minute: "2-digit", hourCycle: "h23" });

/** "domenica 1 novembre 2026 alle 08:00" nell'ora svizzera. */
export function formatZurich(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  // Dalle parti, non dal testo intero: senza la virgola che alcuni browser mettono dopo il giorno.
  const p = Object.fromEntries(longDate.formatToParts(date).map((part) => [part.type, part.value]));
  return `${p.weekday} ${p.day} ${p.month} ${p.year} alle ${clock.format(date)}`;
}

/** Oggi a Zurigo come "YYYY-MM-DD" (per i limiti del campo data). */
export function zurichToday(now = Date.now()): string {
  const values = Object.fromEntries(parts.formatToParts(new Date(now)).map((p) => [p.type, p.value]));
  return `${values.year}-${values.month}-${values.day}`;
}
