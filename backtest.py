import os
import requests
from datetime import datetime, timedelta, timezone
from strategy import StrategyEngine

API_KEY = os.environ["TWELVE_DATA_API_KEY"]
SYMBOLS = ["XAU/USD", "EUR/USD", "GBP/USD"]

# Test roughly the last 2 days.
LOOKBACK_HOURS = 48

# After accepting one setup, do not count another signal from the
# same symbol until this many M15 candles have passed.
COOLDOWN_BARS = 8


def get_data(symbol, interval, outputsize):
    r = requests.get(
        "https://api.twelvedata.com/time_series",
        params={
            "symbol": symbol,
            "interval": interval,
            "outputsize": outputsize,
            "apikey": API_KEY,
            "format": "JSON",
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()

    if "values" not in data:
        raise RuntimeError(f"{symbol} {interval}: {data}")

    # Twelve Data returns newest first.
    return list(reversed(data["values"]))


def candle_time(candle):
    return datetime.strptime(
        candle["datetime"],
        "%Y-%m-%d %H:%M:%S",
    ).replace(tzinfo=timezone.utc)


def price(candle, key):
    return float(candle[key])


def outcome_after(signal, future):
    entry = float(signal["entry"])
    sl = float(signal["sl"])
    tp = float(signal["tp1"])
    side = signal["side"]

    for candle in future:
        high = price(candle, "high")
        low = price(candle, "low")

        if side == "BUY":
            hit_sl = low <= sl
            hit_tp = high >= tp
        else:
            hit_sl = high >= sl
            hit_tp = low <= tp

        # With OHLC data we cannot know which was touched first
        # if both levels were reached inside the same candle.
        if hit_sl and hit_tp:
            return "AMBIGUOUS"

        if hit_sl:
            return "SL"

        if hit_tp:
            return "TP"

    return "OPEN"


def same_setup(a, b):
    if a["side"] != b["side"]:
        return False

    a_entry = float(a["entry"])
    b_entry = float(b["entry"])
    a_sl = float(a["sl"])
    b_sl = float(b["sl"])

    a_risk = abs(a_entry - a_sl)

    if a_risk == 0:
        return False

    # Signals with very similar entry and stop are treated
    # as the same underlying setup.
    entry_close = abs(a_entry - b_entry) <= a_risk * 0.35
    sl_close = abs(a_sl - b_sl) <= a_risk * 0.35

    return entry_close and sl_close


def main():
    engine = StrategyEngine()

    cutoff = datetime.now(timezone.utc) - timedelta(
        hours=LOOKBACK_HOURS
    )

    total = 0
    wins = 0
    losses = 0
    open_trades = 0
    ambiguous = 0

    for symbol in SYMBOLS:
        print("\n" + "=" * 55)
        print(f"CHECKING: {symbol}")
        print("=" * 55)

        h1 = get_data(symbol, "1h", 200)
        m15 = get_data(symbol, "15min", 400)

        accepted = []
        last_signal_index = None
        last_signal = None

        # Replay history one candle at a time.
        # strategy.py ignores the final candle as forming,
        # so include one extra candle in each replay window.
        for i in range(90, len(m15) - 1):
            closed_candle = m15[i - 1]

            if candle_time(closed_candle) < cutoff:
                continue

            m15_slice = m15[: i + 1]

            current_time = candle_time(closed_candle)

            h1_slice = [
                c for c in h1
                if candle_time(c) <= current_time
            ]

            if len(h1_slice) < 20:
                continue

            signal = engine.find_signal(
                symbol,
                h1_slice,
                m15_slice,
            )

            if not signal:
                continue

            # Prevent repeated alerts from consecutive candles.
           
