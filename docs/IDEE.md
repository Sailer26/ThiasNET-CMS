# Idee — fuori dall'MVP

Ogni idea nuova finisce qui, non nel codice (PREMORTEM #1). Si rivaluta dopo la Fase 8.

- **Assistente AI nel pannello** (D-13): "scrivimi un testo per questa pagina", riformulazione, traduzione automatica it↔de/rm/en, suggerimento alt text. Il pannello va progettato con un punto d'aggancio per azioni contestuali sui campi testo.
- **Multi-tenant**: rivalutare se si superano 15–20 clienti (PREMORTEM, decisione finale).
- **Svuotare il cestino delle pagine** / eliminazione definitiva da parte dell'admin (D-43: in Fase 2 il cestino è solo recuperabile).
- **"Salva versione" manuale**: revisione con un nome scelto dal cliente, oltre a quelle automatiche (D-40).
- **Link di anteprima condivisibile** per chi non ha un account (es. il sindaco), valido qualche giorno (D-68: per ora no).
- **Dati strutturati** (schema.org) per organizzazione, eventi e notizie.
- **Altri formati di immagine**: HEIC (foto iPhone) e AVIF con `pillow-heif` (D-70: per ora solo JPG, PNG, WebP, GIF).
- **Immagini decorative** con `alt=""` dichiarato esplicitamente dal cliente (D-77: oggi l'alt è obbligatorio).
- **Indirizzi dei PDF col nome leggibile** (es. `/media/regolamento-2026.pdf`) e anteprima della prima pagina.
- **Nome visualizzato degli utenti** (D-93: oggi il pannello mostra l'email).
- **Pannello in tedesco** per i clienti dei Grigioni e della Svizzera tedesca; **tema scuro** del pannello.
- **Trascinamento nell'albero delle pagine** (D-95: oggi pulsanti Su/Giù/Sposta in…).
- **QR code per attivare il TOTP**, altre scorciatoie da tastiera, notifiche "nuovo messaggio dal sito".
- **Lightbox** per la galleria (ingrandimento al clic), nel tema e compatibile con la CSP.
