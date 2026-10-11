---
description: Verifica che nulla permetta di modificare il template dal pannello
---
Esegui un controllo del lock del template:

1. `pytest tests/security/test_template_lock.py -v`
2. Cerca nel codice (`app/`, `admin/src/`) ogni scrittura su filesystem, `open(..., "w")`, `save(`, `shutil`, `os.rename`, `Path.write_*`, `render_template_string`, `from_string`, `Environment(` e verifica che nessuna tocchi `themes/` o usi input utente come template.
3. Elenca tutte le route `/api/admin/*` e per ognuna dimmi se accetta file, path o stringhe che finiscono in un template.
4. Controlla che le settings esposte siano solo quelle di `theme.json` e tutte tipizzate.
5. Report finale: ✅ / ⚠️ / ❌ per punto, con file e riga. Non correggere nulla senza chiedermelo.
