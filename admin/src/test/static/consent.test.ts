import { describe, expect, it as test } from "vitest";
import { pageWith } from "./loadScript";

const BANNER = `
  <div class="cms-consent" hidden>
    <button data-cms-consent="all">Accetta tutto</button>
    <button data-cms-consent="necessary">Solo necessari</button>
    <button data-cms-consent="choose" aria-expanded="false">Scegli</button>
    <div class="cms-consent__choices" hidden>
      <input type="checkbox" name="embeds"><input type="checkbox" name="stats">
    </div>
    <button data-cms-consent="save" hidden>Salva</button>
  </div>
  <div data-cms-embed="video" data-cms-embed-src="https://www.youtube-nocookie.com/embed/abc" data-cms-embed-title="Video">
    <button class="cms-embed__load">Carica</button>
  </div>
  <div data-cms-embed="map" data-cms-embed-src="https://evil.example/map" data-cms-embed-title="Mappa">
    <button class="cms-embed__load">Carica</button>
  </div>
  <div data-cms-embed="map" data-cms-embed-src="javascript:alert(1)"><button class="cms-embed__load">x</button></div>
  <footer><button data-cms-consent-open>Cookie</button></footer>`;

const MATOMO = { "data-matomo-url": "https://stats.example.ch", "data-matomo-site": "3" };

function site(cookie?: string, attributes: Record<string, string> = MATOMO) {
  return pageWith({ body: BANNER, script: "consent.js", attributes, ...(cookie ? { cookie } : {}) });
}

function click(page: ReturnType<typeof site>, selector: string) {
  page.document.querySelector<HTMLElement>(selector)!.click();
}

const banner = (page: ReturnType<typeof site>) => page.document.querySelector<HTMLElement>("div.cms-consent")!;
const iframes = (page: ReturnType<typeof site>) => page.document.querySelectorAll("iframe");
const matomo = (page: ReturnType<typeof site>) =>
  page.document.querySelector('script[src="https://stats.example.ch/matomo.js"]');

describe("consent.js (banner e contenuti esterni)", () => {
  test("senza scelta mostra il banner e non carica nulla", () => {
    const page = site();
    expect(banner(page).hidden).toBe(false);
    expect(iframes(page)).toHaveLength(0);
    expect(matomo(page)).toBeNull();
  });

  test("Accetta tutto: video ammessi e statistiche; mai host non ammessi", () => {
    const page = site();
    click(page, '[data-cms-consent="all"]');
    expect(banner(page).hidden).toBe(true);
    expect(page.document.cookie).toContain("cms_consent=v1.e1.s1");
    expect([...iframes(page)].map((f) => f.src)).toEqual(["https://www.youtube-nocookie.com/embed/abc"]);
    expect(iframes(page)[0]!.getAttribute("sandbox")).toContain("allow-scripts");
    expect(matomo(page)).not.toBeNull();
  });

  test("Solo necessari: niente contenuti esterni e niente statistiche", () => {
    const page = site();
    click(page, '[data-cms-consent="necessary"]');
    expect(page.document.cookie).toContain("cms_consent=v1.e0.s0");
    expect(iframes(page)).toHaveLength(0);
    expect(matomo(page)).toBeNull();
  });

  test("Scegli: caselle e Salva con le sole statistiche", () => {
    const page = site();
    const choose = page.document.querySelector<HTMLElement>('[data-cms-consent="choose"]')!;
    choose.click();
    expect(choose.getAttribute("aria-expanded")).toBe("true");
    expect(page.document.querySelector<HTMLElement>(".cms-consent__choices")!.hidden).toBe(false);
    page.document.querySelector<HTMLInputElement>('input[name="stats"]')!.checked = true;
    click(page, '[data-cms-consent="save"]');
    expect(page.document.cookie).toContain("cms_consent=v1.e0.s1");
    expect(iframes(page)).toHaveLength(0);
    expect(matomo(page)).not.toBeNull();
  });

  test("un clic su Carica vale per quel solo contenuto ammesso", () => {
    const page = site("cms_consent=v1.e0.s0");
    expect(banner(page).hidden).toBe(true);
    const loads = page.document.querySelectorAll<HTMLElement>(".cms-embed__load");
    loads[1]!.click();
    loads[2]!.click();
    expect(iframes(page)).toHaveLength(0);
    loads[0]!.click();
    expect(iframes(page)).toHaveLength(1);
  });

  test("scelta già fatta: si applica; il link Cookie riapre il banner con le caselle", () => {
    const page = site("cms_consent=v1.e1.s0");
    expect(iframes(page)).toHaveLength(1);
    expect(matomo(page)).toBeNull();
    click(page, "[data-cms-consent-open]");
    expect(banner(page).hidden).toBe(false);
    expect(page.document.querySelector<HTMLInputElement>('input[name="embeds"]')!.checked).toBe(true);
    expect(page.document.activeElement?.textContent).toBe("Accetta tutto");
  });

  test("statistiche solo verso un Matomo https con un id numerico", () => {
    const variants: Record<string, string>[] = [
      { "data-matomo-url": "http://stats.example.ch", "data-matomo-site": "3" },
      { "data-matomo-url": "https://stats.example.ch", "data-matomo-site": "3x" },
      {},
    ];
    for (const attributes of variants) {
      const page = site("cms_consent=v1.e0.s1", attributes);
      expect(page.document.querySelectorAll("script[src]")).toHaveLength(0);
    }
  });

  test("un cookie malformato vale come nessuna scelta", () => {
    const page = site("cms_consent=tutto");
    expect(banner(page).hidden).toBe(false);
  });
});
