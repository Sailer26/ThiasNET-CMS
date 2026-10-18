import { describe, expect, it as test } from "vitest";
import { ORIGIN, pageWith, panelWindow, tick } from "./loadScript";

const BLOCKS = `
  <section data-block-id="aaa"><a href="https://altrove.example" id="link">Link</a></section>
  <section data-block-id="bbb"><form id="modulo"><button>Invia</button></form></section>`;

function preview() {
  const panel = panelWindow();
  const page = pageWith({ body: BLOCKS, script: "preview.js", path: "/_preview/1", parent: panel.window });
  return { ...panel, ...page };
}

describe("preview.js (anteprima nel pannello)", () => {
  test("all'avvio dice al pannello che è pronta", async () => {
    const { messages, document } = preview();
    await tick();
    expect(messages).toContainEqual({ type: "cms:ready", uid: null });
    expect(document.documentElement.classList.contains("cms-preview")).toBe(true);
  });

  test("un clic su un blocco lo segnala; link e moduli non portano altrove", async () => {
    const { messages, document, window } = preview();
    const link = document.getElementById("link")!;
    const click = new window.MouseEvent("click", { bubbles: true, cancelable: true });
    link.dispatchEvent(click);
    expect(click.defaultPrevented).toBe(true);
    const submit = new window.Event("submit", { bubbles: true, cancelable: true });
    document.getElementById("modulo")!.dispatchEvent(submit);
    expect(submit.defaultPrevented).toBe(true);
    await tick();
    expect(messages).toContainEqual({ type: "cms:block-click", uid: "aaa" });
  });

  test("evidenzia solo su richiesta del pannello della stessa origine", async () => {
    const { window, document } = preview();
    const block = document.querySelector('[data-block-id="bbb"]')!;
    const scrolled: Element[] = [];
    window.HTMLElement.prototype.scrollIntoView = function scrollIntoView(this: Element) {
      scrolled.push(this);
    };
    const send = (data: unknown, origin: string, source: unknown) =>
      window.dispatchEvent(new window.MessageEvent("message", { data, origin, source: source as never }));

    send({ type: "cms:highlight", uid: "bbb" }, "https://altro.test", window.parent);
    expect(block.classList.contains("cms-preview-active")).toBe(false);
    send({ type: "cms:highlight", uid: "bbb" }, ORIGIN, window);
    expect(block.classList.contains("cms-preview-active")).toBe(false);

    send({ type: "cms:highlight", uid: "bbb", scroll: false }, ORIGIN, window.parent);
    expect(block.classList.contains("cms-preview-active")).toBe(true);
    expect(scrolled).toEqual([]);
    send({ type: "cms:highlight", uid: "aaa" }, ORIGIN, window.parent);
    expect(block.classList.contains("cms-preview-active")).toBe(false);
    expect(scrolled).toHaveLength(1);
  });

  test("ricorda lo scorrimento per l'anteprima successiva", async () => {
    const first = preview();
    first.window.scrollTo = (() => undefined) as never;
    Object.defineProperty(first.window, "scrollY", { value: 420, configurable: true });
    first.window.dispatchEvent(new first.window.Event("scroll"));
    await new Promise((resolve) => first.window.requestAnimationFrame(() => resolve(null)));
    expect(first.window.sessionStorage.getItem("cms-preview-scroll:/_preview/1")).toBe("420");
  });

  test("fuori dal pannello non manda messaggi", async () => {
    const page = pageWith({ body: BLOCKS, script: "preview.js", path: "/_preview/1" });
    const sent: unknown[] = [];
    page.window.addEventListener("message", (event) => sent.push(event.data));
    await tick();
    expect(sent).toEqual([]);
  });
});
