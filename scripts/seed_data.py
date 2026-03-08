"""
Seed script - creates demo data for paper trading development.

Run: python -m scripts.seed_data
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from uuid import uuid4
from app.config import get_settings
from app.db.session import init_db, get_session, close_db
from app.auth.password import hash_password
from app.models.user import User
from app.models.strategy import Strategy


async def seed():
    settings = get_settings()
    init_db()

    async for session in get_session():
        # Create default admin user
        admin = User(
            id=uuid4(),
            username="admin",
            email="admin@pensy.local",
            password_hash=hash_password("admin123"),
            role="ADMIN",
            is_active=True,
        )
        session.add(admin)

        # Create operator user
        operator = User(
            id=uuid4(),
            username="operator",
            email="operator@pensy.local",
            password_hash=hash_password("operator123"),
            role="OPERATOR",
            is_active=True,
        )
        session.add(operator)

        # Create example strategies
        twap = Strategy(
            id=uuid4(),
            name="twap_example",
            description="Example TWAP strategy - splits orders over time",
            strategy_type="TWAP",
            status="PAUSED",
            trading_mode="PAPER",
            config_json={
                "symbol": "BTCUSDT",
                "side": "BUY",
                "total_quantity": "0.1",
                "num_slices": 5,
                "interval_seconds": 30,
            },
        )
        session.add(twap)

        await session.commit()
        print("Seed data created successfully:")
        print(f"  - Admin user: admin / admin123")
        print(f"  - Operator user: operator / operator123")
        print(f"  - Strategy: twap_example (PAUSED)")

    await close_db()


if __name__ == "__main__":
    asyncio.run(seed())
