from __future__ import annotations

import pytest

from app.config import ConfigError, build_config


def test_testing_config_flags() -> None:
    config = build_config("testing", environ={})
    assert config["TESTING"] is True
    assert config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"


def test_testing_config_ignores_environment_database() -> None:
    config = build_config("testing", environ={"DATABASE_URL": "sqlite:///prod.db"})
    assert config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"


def test_development_config_debug() -> None:
    config = build_config("development", environ={})
    assert config["DEBUG"] is True
    assert config["ACTIVE_THEME"] == "default"


def test_environment_overrides_paths_and_theme() -> None:
    config = build_config(
        "development",
        environ={
            "ACTIVE_THEME": "cliente",
            "THEMES_DIR": "/srv/themes",
            "DATABASE_URL": "sqlite:///x.db",
        },
    )
    assert config["ACTIVE_THEME"] == "cliente"
    assert str(config["THEMES_DIR"]).replace("\\", "/").endswith("/srv/themes")
    assert config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///x.db"


def test_production_requires_secret_key() -> None:
    with pytest.raises(ConfigError, match="SECRET_KEY"):
        build_config("production", environ={"DATABASE_URL": "sqlite:///x.db"})


def test_production_rejects_example_secret_key() -> None:
    with pytest.raises(ConfigError, match="SECRET_KEY"):
        build_config(
            "production",
            environ={"SECRET_KEY": "cambia-questa-chiave", "DATABASE_URL": "sqlite:///x.db"},
        )


def test_production_requires_database_url() -> None:
    with pytest.raises(ConfigError, match="DATABASE_URL"):
        build_config("production", environ={"SECRET_KEY": "x" * 40})


def test_production_config_ok() -> None:
    config = build_config(
        "production", environ={"SECRET_KEY": "x" * 40, "DATABASE_URL": "sqlite:///x.db"}
    )
    assert config["DEBUG"] is False
    assert config["SESSION_COOKIE_SECURE"] is True


def test_unknown_config_name_raises() -> None:
    with pytest.raises(ConfigError, match="staging"):
        build_config("staging", environ={})
