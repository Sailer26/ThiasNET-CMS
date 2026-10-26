import { createContext, useContext } from "react";

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
