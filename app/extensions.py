"""Istanze delle estensioni Flask, inizializzate in create_app()."""

from __future__ import annotations

from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

from app.models import Base

db = SQLAlchemy(model_class=Base)
# Passati da env.py a context.configure: batch per gli ALTER su SQLite, compare_type per
# far rilevare ad autogenerate anche i cambi di tipo delle colonne.
migrate = Migrate(render_as_batch=True, compare_type=True)
login_manager = LoginManager()
csrf = CSRFProtect()
