import { Editor, getSchema } from "@tiptap/core";
import { describe, expect, it as test } from "vitest";
import { richTextExtensions } from "./extensions";

function html(input: string): string {
  const editor = new Editor({ extensions: richTextExtensions(), content: input, injectCSS: false });
  const out = editor.getHTML();
  editor.destroy();
  return out;
}

describe("testo formattato: solo le voci di D-49 (D-108)", () => {
  test("lo schema ha esattamente i nodi e i segni ammessi", () => {
    const schema = getSchema(richTextExtensions());
    expect(Object.keys(schema.nodes).sort()).toEqual(
      ["blockquote", "bulletList", "doc", "hardBreak", "heading", "listItem", "orderedList", "paragraph", "text"].sort(),
    );
    expect(Object.keys(schema.marks).sort()).toEqual(["bold", "italic", "link"]);
  });

  test("ciò che non è ammesso sparisce, il testo resta", () => {
    const out = html(
      '<h1>Grande</h1><p style="color:red"><span class="x">Ciao</span> <u>sotto</u> <img src="x.png">' +
        '<a href="javascript:alert(1)">male</a> <a href="/contatti" target="_blank">bene</a></p><script>alert(1)</script>',
    );
    expect(out).not.toMatch(/<h1|style=|<span|<u>|<img|<script|javascript:|target=/);
    expect(out).toContain("Grande");
    expect(out).toContain('<a rel="noopener noreferrer" href="/contatti">bene</a>');
    expect(out).toContain("male");
  });

  test("titoli 2-4, grassetto, corsivo, elenchi, citazioni, a capo", () => {
    const out = html("<h2>A</h2><h4>B</h4><p><b>g</b> <i>c</i><br>x</p><ul><li><p>u</p></li></ul><ol><li><p>o</p></li></ol><blockquote><p>q</p></blockquote>");
    expect(out).toBe(
      "<h2>A</h2><h4>B</h4><p><strong>g</strong> <em>c</em><br>x</p><ul><li><p>u</p></li></ul><ol><li><p>o</p></li></ol><blockquote><p>q</p></blockquote>",
    );
  });

  test("un editor vuoto è vuoto", () => {
    const editor = new Editor({ extensions: richTextExtensions(), content: "", injectCSS: false });
    expect(editor.isEmpty).toBe(true);
    editor.destroy();
  });
});
