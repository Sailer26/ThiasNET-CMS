"""Istanze delle estensioni Flask, inizializzate in create_app()."""

from __future__ import annotations

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from app.models import Base

db = SQLAlchemy(model_class=Base)
migrate = Migrate(render_as_batch=True)
