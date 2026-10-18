---
description: Crea un nuovo tipo di blocco (schema + template tema + editor + test)
argument-hint: <nome_blocco> <descrizione dei campi>
---
Crea il blocco **$ARGUMENTS** seguendo `docs/ARCHITETTURA.md > Blocchi`:

1. `app/blocks/<nome>.schema.json` — JSON Schema stretto (`additionalProperties: false`, lunghezze massime, media come `media_id` intero, URL validati), con `title` (etichetta italiana) per ogni campo, `description` dove serve un aiuto e `x-enum-titles` per ogni `enum` (D-106: senza, l'app non parte). Solo parole chiave già note al pannello (`PANEL_KEYWORDS` in `tests/unit/test_blocks_registry.py`).
2. Registra il blocco nel registry.
3. `themes/default/blocks/<nome>.html` — **chiedimi conferma prima di scrivere in `themes/`**: è codice del tema.
4. Il modulo del pannello si genera dallo schema (D-112); aggiungi la frase del blocco in `admin/src/text/editor.ts` (`blocks`) e il disegno in `admin/src/features/editor/zones/BlockIcon.tsx` (D-115). Un aiuto dedicato solo se il modulo generato non basta.
5. Test: validazione valida/invalida, XSS nei campi testo, rendering, rifiuto in zone non ammesse.
6. Aggiorna `theme.json` solo se ti dico in quali layout/zone ammetterlo.
