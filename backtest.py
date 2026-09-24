import os
import requests
from datetime import datetime, timedelta
from strategy import StrategyEngine

API_KEY = os.environ["TWELVE_DATA_API_KEY"]

SYMBOLS = [
    "XAU/USD",
    "EUR/USD",
    "GBP/USD",
]

LOOKBACK_HOURS = 48

# Prevent the same setup from being counted repeatedly.
# 8 M15 candles = 2 hours.
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
        raise RuntimeError(
            f"{symbol} {interval}: {data}"
        )

    return list(reversed(data["values"]))


def candle_time(candle):
    return datetime.strptime(
        candle["datetime"],
        "%Y-%m-%d %H:%M:%S",
    )


def find_h1_slice(h1, current_time):
    candles = [
        x for x in h1
        if candle_time(x) <= current_time
    ]

    return candles[-120:]


def backtest_symbol(symbol):
    print()
    print("=" * 55)
    print(f"CHECKING: {symbol}")
    print("=" * 55)

    h1 = get_data(symbol, "1h", 200)
    m15 = get_data(symbol, "15min", 300)

    if len(m15) < 100:
        print("Not enough M15 data.")
        return []

    engine = StrategyEngine()

    latest_time = candle_time(m15[-1])
    start_time = latest_time - timedelta(
        hours=LOOKBACK_HOURS
    )

    results = []

    last_accepted_index = -999

    # Walk forward candle by candle.
    for i in range(80, len(m15)):

        current_time = candle_time(m15[i])

        if current_time < start_time:
            continue

        # Prevent duplicate signals from the same setup.
        if i - last_accepted_index < COOLDOWN_BARS:
            continue

        # Include one extra candle because StrategyEngine
        # removes the currently-forming candle internally.
        m15_slice = m15[:i + 1]

        h1_slice = find_h1_slice(
            h1,
            current_time,
        )

        if len(h1_slice) < 20:
            continue

        try:
            signal = engine.find_signal(
                symbol,
                h1_slice,
                m15_slice,
            )
        except Exception as e:
            print(
                f"Strategy error at "
                f"{current_time}: {e}"
            )
            continue

        if not signal:
            continue

        # Extra duplicate
