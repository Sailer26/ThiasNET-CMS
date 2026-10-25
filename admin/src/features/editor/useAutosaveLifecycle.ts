// Il salvataggio automatico dentro una schermata (D-104): ogni modifica arriva ad Autosave,
// all'uscita si finisce di salvare, dopo un nuovo accesso si riprova, e non si esce (o si
// chiude la scheda) con modifiche non salvate senza saperlo. Lo usano pagine e notizie.
import { useEffect, useRef } from "react";
import { setNavigationGuard } from "../../router/router";
import { useSession } from "../../session/context";
import { ed } from "../../text/editor";
import type { Autosave } from "./model/autosave";

export function useAutosaveLifecycle<D>(autosave: Autosave<D>, doc: D): void {
  const { reloadKey } = useSession();
  useEffect(() => autosave.change(doc), [autosave, doc]);

  // Uscita dall'editor: si finisce di salvare anche dopo che la schermata è sparita.
  useEffect(
    () => () => {
      void autosave.flush().finally(() => autosave.dispose());
    },
    [autosave],
  );

  // Dopo un nuovo accesso si risalva senza ricaricare (D-104).
  const firstKey = useRef(reloadKey);
  useEffect(() => {
    if (reloadKey !== firstKey.current) void autosave.retry();
  }, [reloadKey, autosave]);

  useEffect(() => {
    setNavigationGuard(async () => (await autosave.flush()) || window.confirm(ed.save.leave));
    function beforeUnload(event: BeforeUnloadEvent) {
      if (!autosave.dirty) return;
      event.preventDefault();
      event.returnValue = ""; // Safari e browser meno recenti
    }
    function hidden() {
      if (document.visibilityState === "hidden") void autosave.flush();
    }
    window.addEventListener("beforeunload", beforeUnload);
    document.addEventListener("visibilitychange", hidden);
    return () => {
      setNavigationGuard(null);
      window.removeEventListener("beforeunload", beforeUnload);
      document.removeEventListener("visibilitychange", hidden);
    };
  }, [autosave]);
}
