import os
import requests
from datetime import datetime, timedelta
from strategy import StrategyEngine

API_KEY = os.environ["TWELVE_DATA_API_KEY"]

SYMBOLS = ["XAU/USD", "EUR/USD", "GBP/USD"]

LOOKBACK_HOURS = 48

# One setup cannot be counted again for 2 hours.
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


def result_after_entry(signal, future):
    entry = float(signal["entry"])
    sl = float(signal["sl"])
    tp = float(signal["tp1"])
    side = signal["side"]

    for candle in future:
        high = float(candle["high"])
        low = float(candle["low"])

        if side == "BUY":
            hit_sl = low <= sl
            hit_tp = high >= tp
        else:
            hit_sl = high >= sl
            hit_tp = low <= tp

        # If both were touched inside the same M15
        # candle, candle data cannot tell which came first.
        if hit_sl and hit_tp:
            return "AMBIGUOUS"

        if hit_sl:
            return "SL"

        if hit_tp:
            return "TP"

    return "OPEN"


def backtest_symbol(symbol):
    print()
    print("=" * 55)
    print(f"CHECKING: {symbol}")
    print("=" * 55)

    h1 = get_data(symbol, "1h", 250)
    m15 = get_data(symbol, "15min", 350)

    if len(m15) < 100:
        print("Not enough data.")
        return []

    engine = StrategyEngine()

    end_time = candle_time(m15[-1])
    start_time = end_time - timedelta(
        hours=LOOKBACK_HOURS
    )

    setups = []
    last_signal_index = -999

    for i in range(80, len(m15) - 1):

        current_time = candle_time(m15[i])

        if current_time < start_time:
            continue

        if i - last_signal_index < COOLDOWN_BARS:
            continue

        # StrategyEngine removes the last candle
        # as the forming candle, so add one candle.
        m15_slice = m15[:i + 2]

        h1_slice = [
            c for c in h1
           
