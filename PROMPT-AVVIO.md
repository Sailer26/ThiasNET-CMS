# Prompt di avvio per Claude Code

Copia il kit in una cartella vuota, poi:

```bash
git init && git add . && git commit -m "chore: kit iniziale ThiasCMS"
claude
```

Primo messaggio da incollare in Claude Code:

> Leggi CLAUDE.md e tutti i file in docs/. Poi riassumimi in 10 righe cosa stiamo costruendo e la regola d'oro sul template, e dimmi se vedi contraddizioni o lacune nei documenti prima di iniziare. Non scrivere codice.

Poi, una fase alla volta:

> /fase 0

Quando la fase è chiusa e committata, apri una **nuova sessione** (`/clear`) e passa alla successiva: il contesto resta pulito e CLAUDE.md fa da memoria.

Comandi utili durante il lavoro:
- `/check-template-lock` — prima di ogni merge
- `/nuovo-blocco faq "domanda, risposta, ripetibile"` — per aggiungere blocchi
- "usa l'agent security-reviewer sulle route di questa fase"
- "usa l'agent theme-builder per creare il tema <cliente>" — solo quando lavori tu sul tema
