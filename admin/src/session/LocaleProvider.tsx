import { useCallback, useMemo, useState, type ReactNode } from "react";
import { useSession } from "./context";
import { LocaleContext, type PanelLocale } from "./localeContext";

export const LOCALE_STORAGE_KEY = "thiasnet.panel-locale";

function remembered(): string | null {
  try {
    return window.localStorage.getItem(LOCALE_STORAGE_KEY);
  } catch {
    return null; // memoria del browser bloccata: si parte dalla lingua principale
  }
}

function remember(locale: string): void {
  try {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  } catch {
    // senza memoria del browser la scelta vale fino a quando si ricarica
  }
}

/** La lingua scelta in alto, ricordata su questo computer (D-159). Una lingua che il tema
 * non ha più si ignora: si torna alla principale. */
export function LocaleProvider({ children }: { children: ReactNode }) {
  const { site } = useSession();
  const [chosen, setChosen] = useState<string | null>(remembered);
  const locale = chosen !== null && site.locales.includes(chosen) ? chosen : site.default_locale;
  const setLocale = useCallback(
    (next: string) => {
      if (!site.locales.includes(next)) return;
      remember(next);
      setChosen(next);
    },
    [site.locales],
  );
  const value = useMemo<PanelLocale>(() => ({ locale, locales: site.locales, setLocale }), [locale, site.locales, setLocale]);
  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}
