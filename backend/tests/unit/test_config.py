"""
Unit tests for application configuration (Settings).

Tests default values, property parsing, environment detection,
config sanitization, and validation rules.
"""

import pytest
from decimal import Decimal

from pydantic import ValidationError

from app.config import AppEnvironment, Settings


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------

class TestDefaultSettings:
    """Test that critical defaults are safe."""

    def test_live_trading_disabled_by_default(self):
        settings = Settings()
        assert settings.LIVE_TRADING_ENABLED is False

    def test_default_app_env_is_development(self):
        settings = Settings()
        assert settings.APP_ENV == AppEnvironment.DEVELOPMENT

    def test_default_log_level_is_info(self):
        settings = Settings()
        assert settings.LOG_LEVEL == "INFO"

    def test_default_binance_testnet_enabled(self):
        settings = Settings()
        assert settings.BINANCE_TESTNET is True


# ---------------------------------------------------------------------------
# symbol_whitelist_set
# ---------------------------------------------------------------------------

class TestSymbolWhitelistSet:
    """Test comma-separated symbol whitelist parsing."""

    def test_parses_comma_separated_string(self):
        settings = Settings(SYMBOL_WHITELIST="BTCUSDT,ETHUSDT,SOLUSDT")
        result = settings.symbol_whitelist_set
        assert result == {"BTCUSDT", "ETHUSDT", "SOLUSDT"}

    def test_empty_string_returns_empty_set(self):
        settings = Settings(SYMBOL_WHITELIST="")
        assert settings.symbol_whitelist_set == set()

    def test_strips_whitespace(self):
        settings = Settings(SYMBOL_WHITELIST=" BTCUSDT , ETHUSDT ")
        result = settings.symbol_whitelist_set
        assert result == {"BTCUSDT", "ETHUSDT"}

    def test_uppercases_values(self):
        settings = Settings(SYMBOL_WHITELIST="btcusdt,ethusdt")
        result = settings.symbol_whitelist_set
        assert result == {"BTCUSDT", "ETHUSDT"}

    def test_ignores_empty_segments(self):
        settings = Settings(SYMBOL_WHITELIST="BTCUSDT,,ETHUSDT,")
        result = settings.symbol_whitelist_set
        assert result == {"BTCUSDT", "ETHUSDT"}


# ---------------------------------------------------------------------------
# cors_origins_list
# ---------------------------------------------------------------------------

class TestCorsOriginsList:
    """Test CORS origins parsing."""

    def test_parses_comma_separated_origins(self):
        settings = Settings(CORS_ORIGINS="http://localhost:3000,http://localhost:5173")
        result = settings.cors_origins_list
        assert result == ["http://localhost:3000", "http://localhost:5173"]

    def test_strips_whitespace(self):
        settings = Settings(CORS_ORIGINS=" http://a.com , http://b.com ")
        result = settings.cors_origins_list
        assert result == ["http://a.com", "http://b.com"]

    def test_single_origin(self):
        settings = Settings(CORS_ORIGINS="http://localhost:3000")
        result = settings.cors_origins_list
        assert result == ["http://localhost:3000"]


# ---------------------------------------------------------------------------
# is_production
# ---------------------------------------------------------------------------

class TestIsProduction:
    """Test production environment detection."""

    def test_true_for_production(self):
        settings = Settings(APP_ENV=AppEnvironment.PRODUCTION)
        assert settings.is_production is True

    def test_false_for_development(self):
        settings = Settings(APP_ENV=AppEnvironment.DEVELOPMENT)
        assert settings.is_production is False

    def test_false_for_staging(self):
        settings = Settings(APP_ENV=AppEnvironment.STAGING)
        assert settings.is_production is False


# ---------------------------------------------------------------------------
# get_sanitized_config
# ---------------------------------------------------------------------------

class TestGetSanitizedConfig:
    """Test that get_sanitized_config redacts secrets and includes expected keys."""

    def test_contains_expected_keys(self):
        settings = Settings()
        config = settings.get_sanitized_config()
        expected_keys = {
            "app_name",
            "app_env",
            "log_level",
            "live_trading_enabled",
            "database_url",
            "redis_url",
            "binance_testnet",
            "binance_api_key_set",
            "max_order_notional",
            "max_daily_loss",
            "symbol_whitelist",
        }
        assert set(config.keys()) == expected_keys

    def test_database_url_is_redacted(self):
        settings = Settings(
            DATABASE_URL="postgresql+asyncpg://user:secret@db-host:5432/pensy"
        )
        config = settings.get_sanitized_config()
        # Should contain only the part after '@'
        assert "user" not in config["database_url"]
        assert "secret" not in config["database_url"]
        assert "db-host" in config["database_url"]

    def test_binance_api_key_not_exposed(self):
        settings = Settings()
        config = settings.get_sanitized_config()
        # Should be a boolean, not the actual key
        assert isinstance(config["binance_api_key_set"], bool)

    def test_live_trading_flag_included(self):
        settings = Settings(LIVE_TRADING_ENABLED=True)
        config = settings.get_sanitized_config()
        assert config["live_trading_enabled"] is True

    def test_app_env_is_string_value(self):
        settings = Settings(APP_ENV=AppEnvironment.STAGING)
        config = settings.get_sanitized_config()
        assert config["app_env"] == "staging"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidation:
    """Test configuration validation rules."""

    def test_invalid_log_level_raises_validation_error(self):
        with pytest.raises(ValidationError):
            Settings(LOG_LEVEL="INVALID_LEVEL")

    def test_valid_log_levels_accepted(self):
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            settings = Settings(LOG_LEVEL=level)
            assert settings.LOG_LEVEL == level

    def test_log_level_is_uppercased(self):
        settings = Settings(LOG_LEVEL="debug")
        assert settings.LOG_LEVEL == "DEBUG"
