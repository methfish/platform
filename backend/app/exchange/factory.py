"""
Exchange adapter factory.

Creates the appropriate exchange adapter based on configuration.
Paper adapter is always available. Live adapters require credentials.
"""

from __future__ import annotations

import logging

from app.config import Settings
from app.core.enums import ExchangeName, TradingMode
from app.exchange.base import ExchangeAdapter
from app.exchange.paper.adapter import PaperExchangeAdapter

logger = logging.getLogger(__name__)


def create_exchange_adapter(
    exchange: ExchangeName,
    settings: Settings,
    trading_mode: TradingMode = TradingMode.PAPER,
) -> ExchangeAdapter:
    """
    Factory function to create exchange adapters.

    In PAPER mode, always returns PaperExchangeAdapter regardless of exchange.
    In LIVE mode, returns the appropriate live adapter.
    """
    if trading_mode == TradingMode.PAPER:
        logger.info(f"Creating PAPER adapter (requested exchange: {exchange.value})")
        return PaperExchangeAdapter()

    # Live adapters
    if exchange == ExchangeName.BINANCE_SPOT:
        from app.exchange.binance.adapter import BinanceSpotAdapter

        api_key = settings.BINANCE_API_KEY.get_secret_value()
        api_secret = settings.BINANCE_API_SECRET.get_secret_value()
        if not api_key or not api_secret:
            raise ValueError("Binance API credentials not configured for live trading")

        return BinanceSpotAdapter(
            api_key=api_key,
            api_secret=api_secret,
            testnet=settings.BINANCE_TESTNET,
        )

    if exchange == ExchangeName.BINANCE_FUTURES:
        from app.exchange.binance.futures_adapter import BinanceFuturesAdapter

        api_key = settings.BINANCE_FUTURES_API_KEY.get_secret_value()
        api_secret = settings.BINANCE_FUTURES_API_SECRET.get_secret_value()
        if not api_key or not api_secret:
            raise ValueError("Binance Futures API credentials not configured")

        return BinanceFuturesAdapter(
            api_key=api_key,
            api_secret=api_secret,
            testnet=settings.BINANCE_FUTURES_TESTNET,
        )

    if exchange == ExchangeName.PAPER:
        return PaperExchangeAdapter()

    raise ValueError(f"Unsupported exchange: {exchange}")
