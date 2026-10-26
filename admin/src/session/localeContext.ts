import { createContext, useContext, useEffect } from "react";

/** Lingua del pannello (D-159): albero, menu, widget e notizie la seguono. */
export interface PanelLocale {
  locale: string;
  locales: string[];
  setLocale: (locale: string) => void;
}

export const LocaleContext = createContext<PanelLocale | null>(null);

export function usePanelLocale(): PanelLocale {
  const value = useContext(LocaleContext);
  if (!value) throw new Error("usePanelLocale fuori da LocaleProvider");
  return value;
}

/** Un editor lavora nella lingua della sua pagina (D-159): aperto da un segnalibro o da una
 * traduzione, porta il pannello in quella lingua, così tornando all'elenco si resta lì. */
export function useFollowLocale(locale: string): void {
  const { locale: current, setLocale } = usePanelLocale();
  useEffect(() => {
    if (locale !== current) setLocale(locale);
  }, [locale, current, setLocale]);
}
