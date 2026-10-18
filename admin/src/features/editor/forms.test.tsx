import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it as test } from "vitest";
import { catalog } from "../../test/catalog";
import { setPath, type Data, type Path } from "./model/document";
import type { SaveState } from "./model/autosave";
import { VariantPicker } from "./page/VariantPicker";
import { SaveIndicator } from "./SaveIndicator";
import { SchemaForm } from "./schema/SchemaForm";

const NONE = new Map<string, string>();

function Form({ type, initial = {}, errors = NONE }: { type: string; initial?: Data; errors?: Map<string, string> }) {
  const [data, setData] = useState<Data>(initial);
  return (
    <>
      <SchemaForm
        schema={catalog().types[type]!.schema}
        data={data}
        idPrefix="t"
        errors={errors}
        unsaved={NONE}
        pages={["/contatti"]}
        onChange={(path: Path, value: unknown) => setData((current) => setPath(current, path, value) as Data)}
      />
      <output data-testid="data">{JSON.stringify(data)}</output>
    </>
  );
}

const data = () => JSON.parse(screen.getByTestId("data").textContent ?? "{}") as Data;

describe("moduli generati dagli schemi", () => {
  test.each(Object.keys(catalog().types))("il blocco %s ha un modulo con etichette", (type) => {
    render(<Form type={type} />);
    const schema = catalog().types[type]!.schema;
    const first = Object.values(schema.properties ?? {})[0];
    if (first) expect(screen.getAllByText(first.title!, { exact: false }).length).toBeGreaterThan(0);
    else expect(screen.getByText("Questo blocco non ha impostazioni.")).toBeInTheDocument();
  });

  test("numeri, caselle, campi obbligatori ed errori del server", async () => {
    const user = userEvent.setup();
    render(<Form type="map" errors={new Map([["lat", "Campo obbligatorio"]])} />);
    expect(screen.getByLabelText(/Latitudine/)).toHaveAccessibleDescription(/Campo obbligatorio/);
    expect(screen.getAllByText("(obbligatorio)")).toHaveLength(2);
    await user.type(screen.getByLabelText(/Latitudine/), "46.5");
    await user.clear(screen.getByLabelText(/Ingrandimento/));
    expect(data()).toEqual({ lat: 46.5 });
  });

  test("casella del modulo contatti", async () => {
    const user = userEvent.setup();
    render(<Form type="contacts" />);
    await user.click(screen.getByLabelText("Mostra il modulo di contatto"));
    expect(data()).toEqual({ show_form: true });
    await user.click(screen.getByLabelText("Mostra il modulo di contatto"));
    expect(data()).toEqual({});
    expect(screen.getByLabelText(/Telefono/)).toHaveAttribute("type", "tel");
    expect(screen.getByLabelText(/Email/)).toHaveAttribute("type", "email");
  });

  test("elenchi: aggiungi, su, giù, togli; media in sola lettura", async () => {
    const user = userEvent.setup();
    render(<Form type="files" initial={{ items: [{ media_id: 3, label: "A" }, { media_id: 4, label: "B" }] }} />);
    expect(screen.getByText("File scelto (n. 3)")).toBeInTheDocument();
    const second = screen.getByRole("group", { name: "File n. 2" });
    await user.click(within(second).getByRole("button", { name: "Su" }));
    expect((data().items as Data[]).map((i) => i.label)).toEqual(["B", "A"]);
    await user.click(within(screen.getByRole("group", { name: "File n. 1" })).getByRole("button", { name: "Togli" }));
    expect((data().items as Data[]).map((i) => i.label)).toEqual(["A"]);
    await user.click(within(screen.getByRole("group", { name: "File n. 1" })).getByRole("button", { name: "Togli" }));
    expect(data()).toEqual({});
    await user.click(screen.getByRole("button", { name: "Aggiungi" }));
    expect(screen.getByText("Nessun file scelto")).toBeInTheDocument();
  });

  test("contatore vicino al limite", async () => {
    const user = userEvent.setup();
    render(<Form type="cta" />);
    await user.type(screen.getByLabelText(/Testo del pulsante/), "x".repeat(33));
    expect(screen.getByText("33 / 40")).toBeInTheDocument();
  });

  test("testo formattato: barra degli strumenti e campo etichettato", async () => {
    render(<Form type="text" initial={{ body: "<p>Ciao</p>" }} />);
    expect(screen.getByRole("toolbar", { name: "Formattazione" })).toBeInTheDocument();
    const box = screen.getByRole("textbox", { name: /Testo/ });
    expect(box).toHaveTextContent("Ciao");
    expect(screen.getByRole("button", { name: "Grassetto" })).toHaveAttribute("aria-pressed", "false");
    // Senza testo selezionato il pulsante Link non c'è: un link vuoto non servirebbe.
    expect(screen.queryByRole("button", { name: "Link" })).not.toBeInTheDocument();
    await act(async () => {
      screen.getByRole("button", { name: "Titolo 1" }).click();
    });
    expect(data()).toEqual({ body: "<h2>Ciao</h2>" });
  });
});

describe("varianti e stato del salvataggio", () => {
  test("varianti da miniature", async () => {
    const user = userEvent.setup();
    const chosen: string[] = [];
    render(<VariantPicker variants={catalog().variants.text_image} value={null} error="Variante non disponibile" onChange={(v) => chosen.push(v)} />);
    expect(screen.getByRole("radio", { name: "Immagine a sinistra" })).toBeChecked();
    await user.click(screen.getByRole("radio", { name: "Immagine a destra" }));
    expect(chosen).toEqual(["image_right"]);
    expect(screen.getByText("Variante non disponibile")).toBeInTheDocument();
    const { container } = render(<VariantPicker variants={undefined} value={null} onChange={() => undefined} />);
    expect(container).toBeEmptyDOMElement();
  });

  test.each<[SaveState, string]>([
    [{ kind: "saved", at: null }, "Tutto salvato"],
    [{ kind: "saving" }, "Sto salvando…"],
    [{ kind: "expired" }, "Non salvato: accedi di nuovo"],
    [{ kind: "error", message: "Rete assente" }, "Non salvato: Rete assente"],
  ])("indicatore %#", (state, text) => {
    render(<SaveIndicator state={state} onRetry={() => undefined} />);
    expect(screen.getByRole("status")).toHaveTextContent(text);
  });
});
