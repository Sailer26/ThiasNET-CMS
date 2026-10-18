import { describe, expect, it as test, vi } from "vitest";
import { ApiError } from "../../../api/client";
import { Autosave, type Clock, type SaveState } from "./autosave";
import type { PageDocument } from "./document";

const page = (title: string): PageDocument => ({ title, layout: "page", seo: {}, zones: {} });

function manualClock() {
  const timers: { run: () => void; ms: number }[] = [];
  const clock: Clock = {
    schedule: (run, ms) => {
      const timer = { run, ms };
      timers.push(timer);
      return timer;
    },
    cancel: (handle) => {
      const index = timers.indexOf(handle as never);
      if (index >= 0) timers.splice(index, 1);
    },
    now: () => new Date("2026-10-18T10:42:00+02:00"),
  };
  const fire = async () => {
    const pending = timers.splice(0);
    pending.forEach((timer) => timer.run());
    await new Promise((resolve) => setTimeout(resolve, 0));
  };
  return { clock, timers, fire };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((ok, ko) => {
    resolve = ok;
    reject = ko;
  });
  return { promise, resolve, reject };
}

const conflict = () =>
  new ApiError(409, "version_conflict", "Conflitto", { updated_by_name: "luca@example.ch", updated_at: null });

describe("salvataggio automatico", () => {
  test("salva dopo la pausa, con la versione che cresce; niente timer senza modifiche", async () => {
    const { clock, timers, fire } = manualClock();
    const save = vi.fn(async (_doc: PageDocument, version: number) => version + 1);
    const auto = new Autosave(save, 3, page("a"), clock);
    const states: SaveState["kind"][] = [];
    auto.subscribe((state) => states.push(state.kind));
    expect(timers).toHaveLength(0);
    auto.change(page("a")); // uguale al salvato: nulla
    expect(timers).toHaveLength(0);
    auto.change(page("ab"));
    auto.change(page("abc"));
    expect(timers).toHaveLength(1);
    expect(timers[0]!.ms).toBe(1500);
    await fire();
    expect(save).toHaveBeenCalledTimes(1);
    expect(save).toHaveBeenCalledWith(page("abc"), 3);
    expect(auto.draftVersion).toBe(4);
    expect(auto.current).toEqual({ kind: "saved", at: new Date("2026-10-18T10:42:00+02:00") });
    expect(states).toEqual(["pending", "saving", "saved"]);
  });

  test("una richiesta alla volta; le modifiche durante il salvataggio partono dopo", async () => {
    const { clock } = manualClock();
    const first = deferred<number>();
    const save = vi.fn().mockReturnValueOnce(first.promise).mockResolvedValueOnce(6);
    const auto = new Autosave(save, 4, page("a"), clock);
    auto.change(page("b"));
    const flushing = auto.flush();
    auto.change(page("c"));
    const second = auto.flush();
    first.resolve(5);
    await Promise.all([flushing, second]);
    expect(save.mock.calls.map(([doc, version]) => [(doc as PageDocument).title, version])).toEqual([
      ["b", 4],
      ["c", 5],
    ]);
    expect(auto.dirty).toBe(false);
  });

  test("409: si ferma finché non si sceglie; Tieni la mia salva sopra la versione attuale", async () => {
    const { clock } = manualClock();
    const save = vi.fn().mockRejectedValueOnce(conflict()).mockResolvedValueOnce(9);
    const auto = new Autosave(save, 2, page("a"), clock);
    auto.change(page("mio"));
    expect(await auto.flush()).toBe(false);
    expect(auto.current.kind).toBe("conflict");
    auto.change(page("mio 2"));
    expect(await auto.flush()).toBe(false);
    expect(save).toHaveBeenCalledTimes(1);
    expect(await auto.keepMine(8)).toBe(true);
    expect(save).toHaveBeenLastCalledWith(page("mio 2"), 8);
  });

  test("Carica la sua: nuova base, nulla da salvare", async () => {
    const { clock } = manualClock();
    const save = vi.fn().mockRejectedValueOnce(conflict());
    const auto = new Autosave(save, 2, page("a"), clock);
    auto.change(page("mio"));
    await auto.flush();
    auto.reset(7, page("suo"));
    expect(auto.current.kind).toBe("saved");
    expect(auto.dirty).toBe(false);
    auto.change(page("suo"));
    expect(await auto.flush()).toBe(true);
    expect(save).toHaveBeenCalledTimes(1);
  });

  test("sessione scaduta e rete assente: le modifiche restano e si riprova", async () => {
    const { clock } = manualClock();
    const save = vi
      .fn()
      .mockRejectedValueOnce(new ApiError(401, "unauthorized", "Accesso richiesto"))
      .mockRejectedValueOnce(new ApiError(0, "network", "Connessione non disponibile"))
      .mockResolvedValueOnce(3);
    const auto = new Autosave(save, 2, page("a"), clock);
    auto.change(page("b"));
    await auto.flush();
    expect(auto.current.kind).toBe("expired");
    await auto.retry();
    expect(auto.current).toEqual({ kind: "error", message: "Connessione non disponibile" });
    expect(await auto.retry()).toBe(true);
    expect(auto.draftVersion).toBe(3);
  });

  test("tornare al testo salvato annulla l'attesa; dispose ferma il timer", () => {
    const { clock, timers } = manualClock();
    const auto = new Autosave(vi.fn(), 1, page("a"), clock);
    auto.change(page("b"));
    auto.change(page("a"));
    expect(auto.current.kind).toBe("saved");
    auto.change(page("c"));
    auto.dispose();
    expect(timers).toHaveLength(0);
  });
});
