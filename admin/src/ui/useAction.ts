import { useCallback, useState } from "react";
import { errorMessage } from "../api/client";

/** Stato di un'azione asincrona di un modulo: in corso, errore da mostrare accanto ai pulsanti. */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = useCallback(async (action: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }, []);
  return { busy, error, run };
}
