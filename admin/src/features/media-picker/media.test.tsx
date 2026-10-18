import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it as test } from "vitest";
import { setCsrfToken } from "../../api/client";
import type { Media } from "../../api/media";
import { fakeApi, type FakeApi } from "../../test/fakeApi";
import { MediaChoice } from "./MediaChoice";
import { MediaProvider, mediaIdsIn } from "./MediaContext";
import { MediaPicker } from "./MediaPicker";

function media(id: number, extra: Partial<Media> = {}): Media {
  return {
    id,
    kind: "image",
    name: `foto-${id}.jpg`,
    ext: "jpg",
    alt: `Foto ${id}`,
    width: 800,
    height: 600,
    version: 1,
    url: `/media/k${id}/r1-master.jpg`,
    thumbnail_url: `/media/k${id}/r1-_panel-400.webp`,
    ...extra,
  };
}

function Choice({ initial }: { initial?: number }) {
  const [value, setValue] = useState<number | undefined>(initial);
  return (
    <MediaProvider ids={value ? [value] : []}>
      <MediaChoice id="m" kind="image" value={value} onChange={setValue} />
      <output data-testid="value">{String(value)}</output>
    </MediaProvider>
  );
}

describe("media nell'editor (D-111)", () => {
  let api: FakeApi;
  beforeEach(() => {
    setCsrfToken("tok");
    api = fakeApi();
  });

  test("trova gli id dei media in un documento", () => {
    expect(mediaIdsIn({ seo: { og_image_media_id: 9 }, zones: { main: [{ data: { media_id: 3, items: [{ media_id: 4 }] } }] } })).toEqual(
      new Set([9, 3, 4]),
    );
  });

  test("il media scelto si legge con una richiesta per id; senza alt un avviso e la correzione", async () => {
    api.on("GET", "/media", { data: [media(5, { alt: "" })] });
    api.on("PATCH", "/media/5", { data: media(5, { alt: "Lago al tramonto", version: 2 }) });
    const user = userEvent.setup();
    render(<Choice initial={5} />);
    expect(await screen.findByText("foto-5.jpg")).toBeInTheDocument();
    expect(api.calls[0]!.path).toBe("/media?ids=5");
    expect(screen.getByText(/Manca il testo alternativo/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Testo alternativo…" }));
    const dialog = screen.getByRole("dialog");
    await user.type(within(dialog).getByLabelText("Testo alternativo"), "Lago al tramonto");
    await user.click(within(dialog).getByRole("button", { name: "Salva" }));
    expect(await screen.findByText("Testo alternativo: Lago al tramonto")).toBeInTheDocument();
    expect(api.callsTo("PATCH", "/media/5")[0]!.body).toEqual({ version: 1, alt: "Lago al tramonto" });
    await user.click(screen.getByRole("button", { name: "Togli" }));
    expect(screen.getByTestId("value")).toHaveTextContent("undefined");
  });

  test("libreria: cerca, mostra altri, sceglie", async () => {
    api.on("GET", "/media", (call) => {
      if (call.path.includes("page=2")) return { data: [media(30)], meta: { total: 25 } };
      if (call.path.includes("q=lago")) return { data: [media(7, { name: "lago.jpg" })], meta: { total: 1 } };
      return { data: Array.from({ length: 24 }, (_, i) => media(i + 1, i === 0 ? { alt: "" } : {})), meta: { total: 25 } };
    });
    const user = userEvent.setup();
    render(<Choice />);
    await user.click(screen.getByRole("button", { name: "Scegli immagine" }));
    expect(await screen.findByText("foto-24.jpg")).toBeInTheDocument();
    expect(screen.getByText("1 immagine non ha il testo alternativo.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Mostra altri 1" }));
    expect(await screen.findByText("foto-30.jpg")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Cerca per nome o testo alternativo"), "lago");
    await user.click(await screen.findByRole("button", { name: /lago\.jpg/ }));
    expect(screen.getByTestId("value")).toHaveTextContent("7");
    expect(api.callsTo("GET", "/media").some((c) => c.path.includes("kind=image"))).toBe(true);
  });

  test("carica un file con il testo alternativo; un doppione si riusa", async () => {
    api.on("GET", "/media", { data: [], meta: { total: 0 } });
    api.on(
      "POST",
      "/media",
      { status: 201, data: media(40, { name: "nuova.png" }) },
      { data: media(41, { name: "vecchia.png" }), meta: { duplicate: true } },
    );
    const user = userEvent.setup();
    render(<Choice />);
    await user.click(screen.getByRole("button", { name: "Scegli immagine" }));
    await user.click(screen.getByRole("button", { name: "Carica un file nuovo" }));
    const file = new File(["x"], "nuova.png", { type: "image/png" });
    await user.upload(screen.getByLabelText(/Immagine \(JPG/), file);
    await user.type(screen.getByLabelText("Testo alternativo"), "Municipio");
    await user.click(screen.getByRole("button", { name: "Carica" }));
    await waitFor(() => expect(screen.getByTestId("value")).toHaveTextContent("40"));
    const sent = api.callsTo("POST", "/media")[0]!.body as FormData;
    expect(sent.get("alt")).toBe("Municipio");
    expect((sent.get("file") as File).name).toBe("nuova.png");

    await user.click(screen.getByRole("button", { name: "Cambia" }));
    await user.click(screen.getByRole("button", { name: "Carica un file nuovo" }));
    await user.upload(screen.getByLabelText(/Immagine \(JPG/), file);
    await user.click(screen.getByRole("button", { name: "Carica" }));
    expect(await screen.findByText(/Questo file c'è già nella libreria/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Usa quello già caricato" }));
    expect(screen.getByTestId("value")).toHaveTextContent("41");
  });

  test("galleria: scelta multipla", async () => {
    api.on("GET", "/media", { data: [media(1), media(2), media(3)], meta: { total: 3 } });
    const chosen: number[][] = [];
    const user = userEvent.setup();
    render(
      <MediaProvider ids={[]}>
        <MediaPicker kind="image" multiple onClose={() => undefined} onChoose={(list) => chosen.push(list.map((m) => m.id))} />
      </MediaProvider>,
    );
    await user.click(await screen.findByRole("button", { name: /foto-1\.jpg/ }));
    await user.click(screen.getByRole("button", { name: /foto-3\.jpg/ }));
    expect(screen.getByRole("button", { name: /foto-3\.jpg/ })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "Aggiungi 2 immagini" }));
    expect(chosen).toEqual([[1, 3]]);
  });
});
