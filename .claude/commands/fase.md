---
description: Avvia una fase della roadmap (piano → conferma → TDD → review)
argument-hint: <numero fase>
---
Lavoriamo sulla **Fase $ARGUMENTS** di `docs/ROADMAP.md`.

1. Rileggi `CLAUDE.md`, `docs/PRD.md`, `docs/ARCHITETTURA.md`, `docs/TEMPLATE-CONTRACT.md` e la sezione della fase.
2. Verifica che le fasi precedenti siano chiuse; se no, fermati e dimmelo.
3. Produci un piano (usa `/plan` di ECC): file da creare/modificare, test da scrivere, rischi. **Aspetta la mia conferma.**
4. Dopo conferma: TDD per ogni criterio (test che falliscono → implementazione → refactor).
5. Alla fine: `make test`, `make lint`, `/check-template-lock`, `/code-review`, poi lancia l'agent `security-reviewer` sulle route nuove.
6. Spunta i criteri in `docs/ROADMAP.md` e proponi i commit (formato `tipo(ambito): descrizione`, in italiano).
