# Piano Fase 6 — Widget, menu, impostazioni (2026-10-19)

Decisioni D-139 … D-143. Piano di `ecc:planner`, risposte di Thias tutte sulle proposte.

## Risposte di Thias
1. **Menu e widget:** online subito al salvataggio, con conferma e versioni; li cambia chi può pubblicare. → D-140
2. **Menu principale:** automatico finché il cliente non lo modifica; poi a mano con "Torna automatico". → D-141
3. **Widget:** banner avviso, testo, contatti, orari, social, invito all'azione. → D-142
4. **Dati del sito:** nome, logo, contatti, social, destinatario dei messaggi; Matomo e favicon solo Thias. → D-143

## Punti trovati prima di iniziare
- `widget_area` oggi è `lambda _name: ()` (`render.py`); il tema default non ha `widgets/` né chiama `widget_area()`.
- `menu()` risponde solo per `main`, piatto (senza figli); `max_depth` di `main` è 2.
- `header_style` è dichiarato in `theme.json` ma nessun template lo usa.
- `media_refs` conosce solo le pagine come "Usato in".
- Due test di `tests/security/test_template_lock.py` sono saltati in attesa delle impostazioni.

## Divisione (D-139)
- **6a — Impostazioni:** tabelle `settings` ed `entity_revisions` (migrazione `0010`), validazione tipizzata dei
  settings del tema (colori dalla palette, select, booleani, testi, media, url), `GET /settings`,
  `PUT /settings/site`, `PUT /settings/appearance` con versione (409), audit, revisioni, cache; logo e contatti nel
  tema; "Usato in" generalizzato; schermata "Impostazioni" nel pannello; test di sicurezza attivati.
- **6b — Menu:** `menus` + `menu_items` (migrazione `0011`), albero intero salvato con versione (niente
  `parent_id` dal client: niente cicli), profondità da `theme.json`, pagine risolte al render; pannello con
  trascinamento e pulsanti; "Torna automatico".
- **6c — Widget:** `widget_areas` + `widgets` (migrazione `0012`), schemi in `app/widgets/`, template
  `widgets/*.html` nel tema, visibilità per pagina (tutte / solo / tranne), banner con "fino al", azione rapida dal
  telefono (D-97), test della regola d'oro con CRUD completo.

## Rischi
- Regola d'oro: chiavi sconosciute → 422; i valori sono solo dati (i colori arrivano al sito solo da
  `css_variables`); le rotte si chiamano `appearance`, mai `theme`.
- Cache: ogni scrittura chiama `mark_changed()` nella stessa transazione; banner a scadenza dal cron e a richiesta.
- XSS nei widget: niente HTML libero, testo formattato con l'allowlist, url con `clean_url`, social con elenco fisso.
- Valori vecchi dopo un cambio di tema: si torna al predefinito in lettura, mai un errore.
