"""Testi che il CMS mostra sul sito pubblico (banner cookie, segnaposti, modulo contatti).

Il tema li usa con `cms_text("chiave")` nella lingua della pagina. Il romancio (rm) va fatto
rivedere da chi lo parla prima di un sito in Grigioni.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

LOCALES = ("it", "de", "rm", "en")
FALLBACK_LOCALE = "it"

_TEXTS: dict[str, dict[str, str]] = {
    "skip_to_content": {
        "it": "Vai al contenuto",
        "de": "Zum Inhalt springen",
        "rm": "Ir al cuntegn",
        "en": "Skip to content",
    },
    "menu_label": {
        "it": "Menu principale",
        "de": "Hauptmenü",
        "rm": "Menu principal",
        "en": "Main menu",
    },
    "menu_toggle": {"it": "Menu", "de": "Menü", "rm": "Menu", "en": "Menu"},
    "language_switcher_label": {"it": "Lingua", "de": "Sprache", "rm": "Lingua", "en": "Language"},
    "footer_menu_label": {
        "it": "Link utili",
        "de": "Nützliche Links",
        "rm": "Links utils",
        "en": "Useful links",
    },
    "listing_prev": {
        "it": "Più recenti",
        "de": "Neuere",
        "rm": "Pli novs",
        "en": "Newer",
    },
    "listing_next": {
        "it": "Meno recenti",
        "de": "Ältere",
        "rm": "Pli vegls",
        "en": "Older",
    },
    "listing_page": {
        "it": "Pagina",
        "de": "Seite",
        "rm": "Pagina",
        "en": "Page",
    },
    "listing_empty": {
        "it": "Ancora nessuna notizia.",
        "de": "Noch keine Beiträge.",
        "rm": "Anc naginas novitads.",
        "en": "No news yet.",
    },
    "breadcrumbs_label": {
        "it": "Percorso",
        "de": "Sie sind hier",
        "rm": "Vus essas qua",
        "en": "Breadcrumb",
    },
    "home": {"it": "Home", "de": "Startseite", "rm": "Pagina principala", "en": "Home"},
    "not_found_title": {
        "it": "Pagina non trovata",
        "de": "Seite nicht gefunden",
        "rm": "Pagina betg chattada",
        "en": "Page not found",
    },
    "not_found_text": {
        "it": "La pagina che cerchi non esiste o è stata spostata.",
        "de": "Die gesuchte Seite existiert nicht oder wurde verschoben.",
        "rm": "La pagina che Vus tschertgais n'exista betg u è vegnida spustada.",
        "en": "The page you are looking for does not exist or has been moved.",
    },
    "back_home": {
        "it": "Torna alla pagina iniziale",
        "de": "Zur Startseite",
        "rm": "Enavos a la pagina principala",
        "en": "Back to the home page",
    },
    "image_placeholder": {
        "it": "Immagine (disponibile con la libreria media)",
        "de": "Bild (verfügbar mit der Medienbibliothek)",
        "rm": "Maletg (disponibel cun la biblioteca da medias)",
        "en": "Image (available with the media library)",
    },
    "load_video": {
        "it": "Carica il video",
        "de": "Video laden",
        "rm": "Chargiar il video",
        "en": "Load video",
    },
    "load_map": {
        "it": "Carica la mappa",
        "de": "Karte laden",
        "rm": "Chargiar la charta",
        "en": "Load map",
    },
    "external_notice": {
        "it": "Caricando il contenuto accetti che il fornitore esterno riceva dati "
        "dal tuo browser.",
        "de": "Beim Laden erhält der externe Anbieter Daten von Ihrem Browser.",
        "rm": "Cun chargiar il cuntegn retschaiva il purschider extern datas da Voss navigatur.",
        "en": "Loading this content sends data from your browser to the external provider.",
    },
    "open_externally": {
        "it": "Apri sul sito del fornitore",
        "de": "Beim Anbieter öffnen",
        "rm": "Avrir sin la pagina dal purschider",
        "en": "Open on the provider's site",
    },
    "consent_title": {
        "it": "Cookie e contenuti esterni",
        "de": "Cookies und externe Inhalte",
        "rm": "Cookies e cuntegns externs",
        "en": "Cookies and external content",
    },
    "consent_text": {
        "it": "Usiamo solo i cookie necessari. Con il tuo consenso carichiamo anche video, mappe "
        "e statistiche anonime delle visite. Puoi cambiare idea in ogni momento dal link "
        "“Cookie” in fondo alla pagina.",
        "de": "Wir verwenden nur notwendige Cookies. Mit Ihrer Zustimmung laden wir auch Videos, "
        "Karten und anonyme Besuchsstatistiken. Sie können Ihre Wahl jederzeit über den Link "
        "„Cookies“ unten auf der Seite ändern.",
        "rm": "Nus duvrain mo ils cookies necessaris. Cun Voss consentiment chargiain nus er "
        "videos, chartas e statisticas anonimas da las visitas. Vus pudais midar Vossa "
        "tscherna da tut temp cun il link «Cookies» al fund da la pagina.",
        "en": "We only use necessary cookies. With your consent we also load videos, maps and "
        "anonymous visit statistics. You can change your choice at any time from the "
        "“Cookies” link at the bottom of the page.",
    },
    "consent_accept_all": {
        "it": "Accetta tutto",
        "de": "Alle akzeptieren",
        "rm": "Acceptar tut",
        "en": "Accept all",
    },
    "consent_necessary": {
        "it": "Solo necessari",
        "de": "Nur notwendige",
        "rm": "Mo necessaris",
        "en": "Necessary only",
    },
    "consent_choose": {"it": "Scegli", "de": "Auswählen", "rm": "Tscherner", "en": "Choose"},
    "consent_save": {
        "it": "Salva le scelte",
        "de": "Auswahl speichern",
        "rm": "Memorisar la tscherna",
        "en": "Save choices",
    },
    "consent_embeds": {
        "it": "Video e mappe",
        "de": "Videos und Karten",
        "rm": "Videos e chartas",
        "en": "Videos and maps",
    },
    "consent_stats": {
        "it": "Statistiche delle visite",
        "de": "Besuchsstatistiken",
        "rm": "Statisticas da las visitas",
        "en": "Visit statistics",
    },
    "consent_open": {"it": "Cookie", "de": "Cookies", "rm": "Cookies", "en": "Cookies"},
    "contact_name": {
        "it": "Nome e cognome",
        "de": "Vor- und Nachname",
        "rm": "Num e prenum",
        "en": "Full name",
    },
    "contact_email": {"it": "Email", "de": "E-Mail", "rm": "E-mail", "en": "Email"},
    "contact_phone": {
        "it": "Telefono (facoltativo)",
        "de": "Telefon (optional)",
        "rm": "Telefon (facultativ)",
        "en": "Phone (optional)",
    },
    "contact_message": {"it": "Messaggio", "de": "Nachricht", "rm": "Messadi", "en": "Message"},
    "contact_send": {"it": "Invia", "de": "Senden", "rm": "Trametter", "en": "Send"},
    "contact_sent": {
        "it": "Grazie, abbiamo ricevuto il tuo messaggio.",
        "de": "Vielen Dank, wir haben Ihre Nachricht erhalten.",
        "rm": "Grazia fitg, nus avain retschavì Voss messadi.",
        "en": "Thank you, we have received your message.",
    },
    "contact_errors": {
        "it": "Controlla i campi segnalati.",
        "de": "Bitte prüfen Sie die markierten Felder.",
        "rm": "Controllai ils champs marcads.",
        "en": "Please check the highlighted fields.",
    },
    "contact_preview": {
        "it": "Il modulo funziona solo sul sito pubblicato.",
        "de": "Das Formular funktioniert nur auf der veröffentlichten Website.",
        "rm": "Il formular funcziuna mo sin la pagina publitgada.",
        "en": "The form only works on the published site.",
    },
    "contact_honeypot": {
        "it": "Lascia vuoto questo campo",
        "de": "Dieses Feld leer lassen",
        "rm": "Laschai vid quest champ",
        "en": "Leave this field empty",
    },
    "contact_error_name": {
        "it": "Scrivi il tuo nome (massimo 120 caratteri).",
        "de": "Bitte geben Sie Ihren Namen ein (höchstens 120 Zeichen).",
        "rm": "Scrivai Voss num (maximalmain 120 caracters).",
        "en": "Please enter your name (up to 120 characters).",
    },
    "contact_error_email": {
        "it": "Indica un indirizzo email valido.",
        "de": "Bitte geben Sie eine gültige E-Mail-Adresse ein.",
        "rm": "Inditgai ina adressa dad e-mail valida.",
        "en": "Please enter a valid email address.",
    },
    "contact_error_phone": {
        "it": "Il numero di telefono non sembra valido.",
        "de": "Die Telefonnummer scheint ungültig zu sein.",
        "rm": "Il numer da telefon na para betg valid.",
        "en": "The phone number does not look valid.",
    },
    "contact_error_message": {
        "it": "Scrivi il messaggio (massimo 5000 caratteri).",
        "de": "Bitte schreiben Sie Ihre Nachricht (höchstens 5000 Zeichen).",
        "rm": "Scrivai il messadi (maximalmain 5000 caracters).",
        "en": "Please write your message (up to 5000 characters).",
    },
    "contact_expired": {
        "it": "Il modulo è scaduto: ricarica la pagina e invia di nuovo il messaggio.",
        "de": "Das Formular ist abgelaufen: Bitte laden Sie die Seite neu und senden Sie erneut.",
        "rm": "Il formular è scadì: chargiai danovamain la pagina e trametti puspè il messadi.",
        "en": "The form has expired: please reload the page and send your message again.",
    },
    "contact_too_many": {
        "it": "Hai inviato troppi messaggi: riprova più tardi.",
        "de": "Sie haben zu viele Nachrichten gesendet: Bitte versuchen Sie es später erneut.",
        "rm": "Vus avais tramess memia blers messadis: empruvai pli tard.",
        "en": "You have sent too many messages: please try again later.",
    },
    "required": {"it": "obbligatorio", "de": "Pflichtfeld", "rm": "obligatoric", "en": "required"},
    "download": {"it": "Scarica", "de": "Herunterladen", "rm": "Telechargiar", "en": "Download"},
}

TEXTS: Mapping[str, Mapping[str, str]] = MappingProxyType(
    {key: MappingProxyType(values) for key, values in _TEXTS.items()}
)


MONTHS: dict[str, tuple[str, ...]] = {
    "it": (
        "gennaio",
        "febbraio",
        "marzo",
        "aprile",
        "maggio",
        "giugno",
        "luglio",
        "agosto",
        "settembre",
        "ottobre",
        "novembre",
        "dicembre",
    ),
    "de": (
        "Januar",
        "Februar",
        "März",
        "April",
        "Mai",
        "Juni",
        "Juli",
        "August",
        "September",
        "Oktober",
        "November",
        "Dezember",
    ),
    "rm": (
        "schaner",
        "favrer",
        "mars",
        "avrigl",
        "matg",
        "zercladur",
        "fanadur",
        "avust",
        "settember",
        "october",
        "november",
        "december",
    ),
    "en": (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ),
}


def month(number: int, locale: str) -> str:
    names = MONTHS.get(locale) or MONTHS[FALLBACK_LOCALE]
    return names[number - 1]


def text(key: str, locale: str) -> str:
    """Testo nella lingua richiesta; chiave sconosciuta → la chiave stessa (si vede subito)."""
    translations = TEXTS.get(key)
    if translations is None:
        return key
    return translations.get(locale) or translations[FALLBACK_LOCALE]
