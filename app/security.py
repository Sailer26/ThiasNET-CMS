"""Sessione utente, CSRF e proxy: collegati all'app in create_app()."""

from __future__ import annotations

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app.api import unauthorized
from app.extensions import csrf, login_manager
from app.services.auth import load_user


def init_security(app: Flask) -> None:
    csrf.init_app(app)
    login_manager.init_app(app)
    # "basic" e non "strong": "strong" scollegherebbe i tablet che cambiano rete (D-26).
    login_manager.session_protection = "basic"
    login_manager.user_loader(load_user)
    login_manager.unauthorized_handler(unauthorized)

    proxies = int(app.config["TRUSTED_PROXY_COUNT"])
    if proxies:
        # Dietro Caddy l'IP vero è in X-Forwarded-For; senza proxy fidati l'header è ignorato,
        # altrimenti chiunque potrebbe falsificare l'IP e aggirare il rate limit (D-34).
        app.wsgi_app = ProxyFix(  # type: ignore[method-assign]
            app.wsgi_app, x_for=proxies, x_proto=proxies, x_host=proxies
        )
