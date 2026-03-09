"""
Pensy platform configuration.

Uses Pydantic Settings for typed, validated configuration from environment variables.
Critical safety: LIVE_TRADING_ENABLED defaults to False. Live trading requires both
this flag AND runtime operator confirmation via the admin API.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Application ---
    APP_NAME: str = "pensy"
    APP_ENV: AppEnvironment = AppEnvironment.DEVELOPMENT
    LOG_LEVEL: str = "INFO"

    # --- Trading Mode (CRITICAL SAFETY) ---
    LIVE_TRADING_ENABLED: bool = False  # Must be explicitly set to true

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://pensy:pensy_dev_password@localhost:5432/pensy"
    DATABASE_ECHO: bool = False

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- JWT Auth ---
    JWT_SECRET_KEY: SecretStr = SecretStr("change-this-to-a-random-secret-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --- Binance API ---
    BINANCE_API_KEY: SecretStr = SecretStr("")
    BINANCE_API_SECRET: SecretStr = SecretStr("")
    BINANCE_TESTNET: bool = True

    # --- Binance Futures ---
    BINANCE_FUTURES_API_KEY: SecretStr = SecretStr("")
    BINANCE_FUTURES_API_SECRET: SecretStr = SecretStr("")
    BINANCE_FUTURES_TESTNET: bool = True

    # --- Risk Limits ---
    MAX_ORDER_NOTIONAL: Decimal = Decimal("10000.0")
    MAX_ORDER_QUANTITY: Decimal = Decimal("100.0")
    MAX_POSITION_NOTIONAL: Decimal = Decimal("50000.0")
    MAX_GROSS_EXPOSURE: Decimal = Decimal("100000.0")
    MAX_DAILY_LOSS: Decimal = Decimal("5000.0")
    MAX_OPEN_ORDERS: int = 20
    PRICE_DEVIATION_THRESHOLD: Decimal = Decimal("0.05")
    STALE_PRICE_THRESHOLD_SECONDS: int = 30
    MAX_ORDERS_PER_MINUTE: int = 30

    # --- Symbol Whitelist ---
    SYMBOL_WHITELIST: str = ""

    # --- Market Data ---
    MARKET_DATA_SYMBOLS: str = "BTCUSDT,ETHUSDT"

    # --- Server ---
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # --- CORS ---
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # --- Agent Settings ---
    AGENT_SKILL_TIMEOUT_SECONDS: float = 30.0
    AGENT_MODEL_CONFIDENCE_THRESHOLD: float = 0.5
    AGENT_MAX_PIPELINE_TIME_SECONDS: float = 120.0
    AGENT_ENABLE_MODEL_ASSISTED: bool = True
    LLM_API_KEY: SecretStr = SecretStr("")
    LLM_MODEL_NAME: str = "claude-haiku-4-5-20251001"

    # --- Alert Webhooks ---
    SLACK_WEBHOOK_URL: Optional[str] = None
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None

    # --- Market Scraper ---
    SCRAPER_INTERVAL_SECONDS: int = 300
    SCRAPER_SYMBOLS: str = "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT,ADAUSDT,DOGEUSDT,AVAXUSDT,DOTUSDT,MATICUSDT,LINKUSDT,UNIUSDT,ATOMUSDT,LTCUSDT,ETCUSDT,NEARUSDT,APTUSDT,ARBUSDT,OPUSDT,FILUSDT"
    SCRAPER_OHLCV_INTERVALS: str = "1h,4h,1d"
    SCRAPER_OHLCV_LIMIT: int = 100

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}")
        return v.upper()

    @property
    def symbol_whitelist_set(self) -> set[str]:
        if not self.SYMBOL_WHITELIST:
            return set()
        return {s.strip().upper() for s in self.SYMBOL_WHITELIST.split(",") if s.strip()}

    @property
    def market_data_symbols_list(self) -> list[str]:
        return [s.strip().upper() for s in self.MARKET_DATA_SYMBOLS.split(",") if s.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        return [s.strip() for s in self.CORS_ORIGINS.split(",") if s.strip()]

    @property
    def scraper_symbols_list(self) -> list[str]:
        return [s.strip().upper() for s in self.SCRAPER_SYMBOLS.split(",") if s.strip()]

    @property
    def scraper_ohlcv_intervals_list(self) -> list[str]:
        return [s.strip() for s in self.SCRAPER_OHLCV_INTERVALS.split(",") if s.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == AppEnvironment.PRODUCTION

    def get_sanitized_config(self) -> dict:
        """Return config summary with secrets redacted, safe for logging."""
        return {
            "app_name": self.APP_NAME,
            "app_env": self.APP_ENV.value,
            "log_level": self.LOG_LEVEL,
            "live_trading_enabled": self.LIVE_TRADING_ENABLED,
            "database_url": self.DATABASE_URL.split("@")[-1] if "@" in self.DATABASE_URL else "***",
            "redis_url": self.REDIS_URL,
            "binance_testnet": self.BINANCE_TESTNET,
            "binance_api_key_set": bool(self.BINANCE_API_KEY.get_secret_value()),
            "max_order_notional": str(self.MAX_ORDER_NOTIONAL),
            "max_daily_loss": str(self.MAX_DAILY_LOSS),
            "symbol_whitelist": list(self.symbol_whitelist_set),
        }


# Global settings instance - created once at startup
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
