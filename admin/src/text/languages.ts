// Nomi delle lingue del tema (D-158), come li scrive chi le parla.
const NAMES: Record<string, string> = { it: "Italiano", de: "Deutsch", rm: "Rumantsch", en: "English" };

export function languageName(locale: string): string {
  return NAMES[locale] ?? locale;
}
