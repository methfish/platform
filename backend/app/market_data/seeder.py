"""
Simulated market data seeder.

Seeds realistic paper-trading prices for forex pairs and stocks
into the TickerSnapshot table so they appear alongside crypto.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

import app.db.session as _db_session
from app.models.market_data import TickerSnapshot

logger = logging.getLogger(__name__)

# Simulated prices: (bid, ask, last, volume_24h)
FOREX_SYMBOLS: dict[str, tuple[str, str, str, str]] = {
    "EURUSD": ("1.0848", "1.0850", "1.0849", "125000000"),
    "GBPUSD": ("1.2641", "1.2643", "1.2642", "98000000"),
    "USDJPY": ("149.42", "149.44", "149.43", "112000000"),
    "AUDUSD": ("0.6547", "0.6549", "0.6548", "67000000"),
    "USDCAD": ("1.3581", "1.3583", "1.3582", "71000000"),
    "USDCHF": ("0.9041", "0.9043", "0.9042", "58000000"),
    "NZDUSD": ("0.6093", "0.6095", "0.6094", "42000000"),
    "EURGBP": ("0.8581", "0.8583", "0.8582", "53000000"),
}

STOCK_SYMBOLS: dict[str, tuple[str, str, str, str]] = {
    "AAPL":  ("174.21", "174.23", "174.22", "58000000"),
    "MSFT":  ("378.85", "378.87", "378.86", "23000000"),
    "NVDA":  ("822.14", "822.18", "822.16", "41000000"),
    "GOOGL": ("140.32", "140.34", "140.33", "18000000"),
    "AMZN":  ("178.54", "178.56", "178.55", "32000000"),
    "TSLA":  ("248.42", "248.46", "248.44", "97000000"),
    "META":  ("501.29", "501.33", "501.31", "15000000"),
    "SPY":   ("512.78", "512.80", "512.79", "75000000"),
    "QQQ":   ("443.21", "443.23", "443.22", "45000000"),
    "BRK.B": ("402.11", "402.13", "402.12", "5000000"),
}


async def seed_simulated_tickers() -> None:
    """Insert or update TickerSnapshot rows for forex and stock symbols."""
    if _db_session.async_session_factory is None:
        logger.warning("DB not ready, skipping ticker seed")
        return

    now = datetime.now(timezone.utc)
    rows: list[TickerSnapshot] = []

    for symbol, (bid, ask, last, vol) in FOREX_SYMBOLS.items():
        rows.append(TickerSnapshot(
            symbol=symbol,
            exchange="forex_sim",
            bid=Decimal(bid),
            ask=Decimal(ask),
            last=Decimal(last),
            volume_24h=Decimal(vol),
            snapshot_time=now,
        ))

    for symbol, (bid, ask, last, vol) in STOCK_SYMBOLS.items():
        rows.append(TickerSnapshot(
            symbol=symbol,
            exchange="alpaca",
            bid=Decimal(bid),
            ask=Decimal(ask),
            last=Decimal(last),
            volume_24h=Decimal(vol),
            snapshot_time=now,
        ))

    try:
        async with _db_session.async_session_factory() as session:
            session.add_all(rows)
            await session.commit()
        logger.info(f"Seeded {len(rows)} simulated tickers ({len(FOREX_SYMBOLS)} forex, {len(STOCK_SYMBOLS)} stocks)")
    except Exception as e:
        logger.warning(f"Could not seed simulated tickers: {e}")
