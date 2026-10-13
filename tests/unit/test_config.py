from __future__ import annotations

from datetime import timedelta

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


def test_development_without_secret_key_uses_random_key() -> None:
    first = build_config("development", environ={})["SECRET_KEY"]
    second = build_config("development", environ={})["SECRET_KEY"]
    assert first != second
    assert len(first) >= 32


@pytest.mark.parametrize("value", ["abc", "0", "-1", "1.5"])
def test_invalid_max_upload_raises(value: str) -> None:
    with pytest.raises(ConfigError, match="MAX_UPLOAD_MB"):
        build_config("development", environ={"MAX_UPLOAD_MB": value})


def test_max_upload_in_bytes() -> None:
    config = build_config("development", environ={"MAX_UPLOAD_MB": "2"})
    assert config["MAX_CONTENT_LENGTH"] == 2 * 1024 * 1024


PROD_ENV = {"SECRET_KEY": "x" * 40, "DATABASE_URL": "sqlite:///x.db"}


def test_production_session_cookies_hardened() -> None:
    config = build_config("production", environ=PROD_ENV)
    assert config["SESSION_COOKIE_NAME"] == "__Host-session"
    assert config["REMEMBER_COOKIE_NAME"] == "__Host-remember_token"
    assert config["REMEMBER_COOKIE_SECURE"] is True
    assert config["REMEMBER_COOKIE_HTTPONLY"] is True
    assert config["REMEMBER_COOKIE_SAMESITE"] == "Lax"
    assert config["TRUSTED_PROXY_COUNT"] == 1


def test_session_lifetime_12_hours_and_csrf_tied_to_session() -> None:
    config = build_config("development", environ={})
    assert config["PERMANENT_SESSION_LIFETIME"] == timedelta(hours=12)
    assert config["SESSION_REFRESH_EACH_REQUEST"] is True
    assert config["WTF_CSRF_TIME_LIMIT"] is None
    assert config["TRUSTED_PROXY_COUNT"] == 0


@pytest.mark.parametrize("value", ["x", "-1"])
def test_invalid_proxy_count_raises(value: str) -> None:
    with pytest.raises(ConfigError, match="TRUSTED_PROXY_COUNT"):
        build_config("development", environ={"TRUSTED_PROXY_COUNT": value})


def test_testing_uses_cheap_argon2() -> None:
    config = build_config("testing", environ={})
    assert config["ARGON2_TIME_COST"] == 1
    assert config["ARGON2_MEMORY_COST"] <= 1024


def test_unknown_config_name_raises() -> None:
    with pytest.raises(ConfigError, match="staging"):
        build_config("staging", environ={})
