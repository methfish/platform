"""
AI Chat API — Claude-powered conversational assistant for the Pensy platform.

Provides a chat endpoint that streams responses from Claude with full context
about the user's portfolio, positions, orders, strategies, and risk status.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user
from app.config import get_settings
from app.db.session import get_session
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    context: Optional[str] = None


class ChatResponse(BaseModel):
    role: str = "assistant"
    content: str


async def _build_system_prompt(session: AsyncSession) -> str:
    """Build a system prompt with current platform context."""
    from app.position.tracker import PositionTracker
    from app.dependencies import get_oms_service, get_risk_engine

    context_parts = [
        "You are Pensy AI, the intelligent assistant for the Pensy quantitative trading research platform.",
        "You help users with strategy research, backtesting, data analysis, risk management, and trading decisions.",
        "The platform focuses on forex and stock markets (no crypto).",
        "Available asset classes: Forex (EURUSD, GBPUSD, USDJPY, etc.) and Stocks (AAPL, MSFT, NVDA, etc.).",
        "",
        "Available strategies: sma_crossover, rsi, bollinger, macd.",
        "Cost models: forex_retail, forex_ecn, stock_retail, stock_ib.",
        "",
        "Platform capabilities:",
        "- Data collection via yfinance (forex + stocks)",
        "- Backtesting with multiple strategies and cost models",
        "- Parameter sweeps for optimization",
        "- Live paper trading with risk management",
        "- AI agents: Research Agent (data analysis, backtesting) and Strategy Coding Agent (code generation)",
        "",
        "Be concise, quantitative, and actionable. Use numbers and data when possible.",
        "If the user asks about their portfolio, positions, or P&L, provide the info from context.",
        "Format responses with markdown for readability.",
    ]

    # Try to add live context
    try:
        tracker = PositionTracker()
        positions = await tracker.get_all_positions(session)
        if positions:
            context_parts.append("\nCurrent Open Positions:")
            for pos in positions:
                context_parts.append(
                    f"  - {pos.symbol}: {pos.side} {pos.quantity} @ avg {pos.avg_entry_price}, "
                    f"unrealized P&L: {pos.unrealized_pnl}"
                )
    except Exception:
        pass

    try:
        risk = get_risk_engine()
        context_parts.append(f"\nRisk Engine: {len(risk.checks)} checks active")
    except Exception:
        pass

    return "\n".join(context_parts)


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Send a message to the AI assistant and get a response."""
    settings = get_settings()
    api_key = settings.LLM_API_KEY.get_secret_value()

    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="AI chat is not configured. Set LLM_API_KEY in environment.",
        )

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    system_prompt = await _build_system_prompt(session)

    # Convert messages to Anthropic format
    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    try:
        response = client.messages.create(
            model=settings.LLM_MODEL_NAME,
            max_tokens=2048,
            system=system_prompt,
            messages=messages,
        )

        content = response.content[0].text if response.content else "I couldn't generate a response."

        return ChatResponse(content=content)

    except anthropic.APIError as e:
        logger.exception("Anthropic API error: %s", e)
        raise HTTPException(status_code=502, detail=f"AI service error: {str(e)}")
    except Exception as e:
        logger.exception("Chat error: %s", e)
        raise HTTPException(status_code=500, detail="Internal chat error")


@router.post("/stream")
async def chat_stream(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Stream a chat response from the AI assistant."""
    settings = get_settings()
    api_key = settings.LLM_API_KEY.get_secret_value()

    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="AI chat is not configured. Set LLM_API_KEY in environment.",
        )

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    system_prompt = await _build_system_prompt(session)
    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    async def generate():
        try:
            with client.messages.stream(
                model=settings.LLM_MODEL_NAME,
                max_tokens=2048,
                system=system_prompt,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield f"data: {text}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.exception("Stream error: %s", e)
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
