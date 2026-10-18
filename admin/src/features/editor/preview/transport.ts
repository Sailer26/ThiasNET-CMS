// Invio del documento all'anteprima (D-107): un form nascosto con target sull'iframe.
// In un file a parte perché jsdom non sa inviare form verso un iframe (nei test si sostituisce).
export const transport = {
  submit(target: string, action: string, fields: Record<string, string>): void {
    const form = document.createElement("form");
    form.method = "post";
    form.action = action;
    form.target = target;
    form.hidden = true;
    for (const [name, value] of Object.entries(fields)) {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = name;
      input.value = value;
      form.appendChild(input);
    }
    document.body.appendChild(form);
    form.submit();
    form.remove();
  },
};
