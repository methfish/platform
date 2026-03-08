"""Technical indicators - pure Python implementation without numpy."""

from __future__ import annotations


def sma(values: list[float], period: int = 20) -> list[float]:
    """Simple moving average."""
    if len(values) < period:
        return []
    result = []
    for i in range(period - 1, len(values)):
        window = values[i - period + 1 : i + 1]
        result.append(sum(window) / period)
    return result


def ema(values: list[float], period: int = 20) -> list[float]:
    """Exponential moving average."""
    if len(values) < period:
        return []
    multiplier = 2.0 / (period + 1)
    result = []
    sma_val = sum(values[:period]) / period
    result.append(sma_val)
    for i in range(period, len(values)):
        sma_val = (values[i] - sma_val) * multiplier + sma_val
        result.append(sma_val)
    return result


def rsi(values: list[float], period: int = 14) -> list[float]:
    """Relative Strength Index."""
    if len(values) < period + 1:
        return []
    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
    seed = sum([d for d in deltas[:period] if d > 0]) / period
    seed2 = sum([abs(d) for d in deltas[:period] if d < 0]) / period
    rs_values = []
    rs = seed / seed2 if seed2 != 0 else 0
    rs_values.append(100 - 100 / (1 + rs) if rs != 0 else 0)
    for i in range(period, len(deltas)):
        u = deltas[i] if deltas[i] > 0 else 0
        d = abs(deltas[i]) if deltas[i] < 0 else 0
        seed = (seed * (period - 1) + u) / period
        seed2 = (seed2 * (period - 1) + d) / period
        rs = seed / seed2 if seed2 != 0 else 0
        rs_values.append(100 - 100 / (1 + rs) if rs != 0 else 0)
    return rs_values


def macd(
    values: list[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> dict[str, list[float]]:
    """MACD - Moving Average Convergence Divergence."""
    ema_fast = ema(values, fast)
    ema_slow = ema(values, slow)
    if len(ema_fast) < len(ema_slow):
        ema_fast = [0] * (len(ema_slow) - len(ema_fast)) + ema_fast
    if len(ema_slow) < len(ema_fast):
        ema_slow = [0] * (len(ema_fast) - len(ema_slow)) + ema_slow
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line = ema(macd_line, signal)
    histogram = []
    for i in range(len(macd_line)):
        idx = i - (len(macd_line) - len(signal_line))
        if idx >= 0:
            histogram.append(macd_line[i] - signal_line[idx])
        else:
            histogram.append(0)
    return {
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram,
    }


def bollinger_bands(
    values: list[float], period: int = 20, std_dev: int = 2
) -> dict[str, list[float]]:
    """Bollinger Bands."""
    if len(values) < period:
        return {"upper": [], "middle": [], "lower": []}
    middle = sma(values, period)
    upper = []
    lower = []
    for i in range(period - 1, len(values)):
        window = values[i - period + 1 : i + 1]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        std = variance ** 0.5
        upper.append(middle[i - period + 1] + std_dev * std)
        lower.append(middle[i - period + 1] - std_dev * std)
    return {"upper": upper, "middle": middle, "lower": lower}


def atr(
    highs: list[float], lows: list[float], closes: list[float], period: int = 14
) -> list[float]:
    """Average True Range."""
    if len(highs) < 2 or len(lows) < 2 or len(closes) < 2:
        return []
    tr_values = []
    for i in range(1, len(highs)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        tr_values.append(tr)
    if len(tr_values) < period:
        return []
    atr_vals = [sum(tr_values[:period]) / period]
    for i in range(period, len(tr_values)):
        atr_vals.append((atr_vals[-1] * (period - 1) + tr_values[i]) / period)
    return atr_vals


def vwap(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float],
) -> list[float]:
    """Volume Weighted Average Price."""
    if not highs or not lows or not closes or not volumes:
        return []
    result = []
    cumsum_pv = 0.0
    cumsum_v = 0.0
    for h, l, c, v in zip(highs, lows, closes, volumes):
        typical_price = (h + l + c) / 3.0
        cumsum_pv += typical_price * v
        cumsum_v += v
        if cumsum_v > 0:
            result.append(cumsum_pv / cumsum_v)
        else:
            result.append(c)
    return result
