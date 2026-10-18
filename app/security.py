"""Sessione utente, CSRF e proxy: collegati all'app in create_app()."""

from __future__ import annotations

from flask import Flask, Response, request
from flask.sessions import SecureCookieSessionInterface, SessionMixin
from werkzeug.middleware.proxy_fix import ProxyFix

from app.api import unauthorized
from app.extensions import csrf, login_manager
from app.services import passwords
from app.services.auth import load_user

MEDIA_PREFIX = "/media/"


class SessionInterface(SecureCookieSessionInterface):
    """I file della libreria sono pubblici e in cache (anche condivise): le loro risposte non
    portano mai il cookie di sessione di chi è nel pannello (review sicurezza Fase 4)."""

    def save_session(self, app: Flask, session: SessionMixin, response: Response) -> None:
        if request.path.startswith(MEDIA_PREFIX):
            return  # né Set-Cookie né Vary: Cookie
        super().save_session(app, session, response)


def init_security(app: Flask) -> None:
    app.session_interface = SessionInterface()
    csrf.init_app(app)
    login_manager.init_app(app)
    # "basic" e non "strong": "strong" scollegherebbe i tablet che cambiano rete (D-26).
    login_manager.session_protection = "basic"
    login_manager.user_loader(load_user)
    login_manager.unauthorized_handler(unauthorized)
    with app.app_context():
        passwords.warm_up()

    proxies = int(app.config["TRUSTED_PROXY_COUNT"])
    if proxies:
        # Dietro Caddy l'IP vero è in X-Forwarded-For; senza proxy fidati l'header è ignorato,
        # altrimenti chiunque potrebbe falsificare l'IP e aggirare il rate limit (D-34).
        # X-Forwarded-Host no: l'host servirà per canonical e sitemap (Fase 3).
        app.wsgi_app = ProxyFix(  # type: ignore[method-assign]
            app.wsgi_app, x_for=proxies, x_proto=proxies, x_host=0
        )
