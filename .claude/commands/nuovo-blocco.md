---
description: Crea un nuovo tipo di blocco (schema + template tema + editor + test)
argument-hint: <nome_blocco> <descrizione dei campi>
---
Crea il blocco **$ARGUMENTS** seguendo `docs/ARCHITETTURA.md > Blocchi`:

1. `app/blocks/<nome>.schema.json` — JSON Schema stretto (`additionalProperties: false`, lunghezze massime, media come `media_id` intero, URL validati).
2. Registra il blocco nel registry.
3. `themes/default/blocks/<nome>.html` — **chiedimi conferma prima di scrivere in `themes/`**: è codice del tema.
4. `admin/src/blocks/<nome>/Editor.tsx` — form con etichette in italiano.
5. Test: validazione valida/invalida, XSS nei campi testo, rendering, rifiuto in zone non ammesse.
6. Aggiorna `theme.json` solo se ti dico in quali layout/zone ammetterlo.
