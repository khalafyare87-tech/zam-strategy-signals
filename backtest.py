import os
import requests
from datetime import datetime, timedelta, timezone
from strategy import StrategyEngine

API_KEY = os.environ["TWELVE_DATA_API_KEY"]

SYMBOLS = ["XAU/USD", "EUR/USD", "GBP/USD"]


def get_data(symbol, interval, outputsize=500):
    url = "https://api.twelvedata.com/time_series"

    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": API_KEY,
        "format": "JSON",
    }

    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()

    data = r.json()

    if "values" not in data:
        raise RuntimeError(
            f"{symbol} {interval}: {data}"
        )

    # Twelve Data returns newest candle first.
    return list(reversed(data["values"]))


def parse_dt(value):
    return datetime.strptime(
        value,
        "%Y-%m-%d %H:%M:%S"
    ).replace(tzinfo=timezone.utc)


def main():

    engine = StrategyEngine()

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=2)

    print("=" * 60)
    print("ZAM STRATEGY - 2 DAY BACKTEST")
    print("Period:", start, "to", now)
    print("=" * 60)

    total = 0

    for symbol in SYMBOLS:

        print()
        print("=" * 60)
        print("CHECKING:", symbol)
        print("=" * 60)

        try:
            h1 = get_data(symbol, "1h", 300)
            m15 = get_data(symbol, "15min", 500)

        except Exception as e:
            print("DATA ERROR:", e)
            continue

        found = []

        # Walk forward candle by candle.
        # StrategyEngine ignores the last candle because it assumes
        # that candle is currently forming. Therefore we include one
        # additional candle after each historical decision point.
        for i in range(81, len(m15)):

            decision_candle = m15[i - 1]

            try:
                decision_time = parse_dt(
                    decision_candle["datetime"]
                )
            except Exception:
                continue

            if decision_time < start:
                continue

            if decision_time > now:
                continue

            # Only give the strategy H1 candles that would have
            # existed by this historical point.
            historical_h1 = []

            for candle in h1:
                try:
                    h1_time = parse_dt(candle["datetime"])
                except Exception:
                    continue

                if h1_time <= decision_time:
                    historical_h1.append(candle)

            if len(historical_h1) < 20:
                continue

            # Add the next M15 candle as the simulated
            # "currently forming" candle. StrategyEngine removes it.
            historical_m15 = m15[:i + 1]

            try:
                signal = engine.find_signal(
                    symbol,
                    historical_h1,
                    historical_m15
                )
            except Exception as e:
                print("STRATEGY ERROR:", e)
                continue

            if not signal:
                continue

            # Avoid counting the same signal repeatedly.
            signal_key = (
                signal.get("side"),
                signal.get("bar"),
                signal.get("entry")
            )

            if signal_key in [
                x["key"] for x in found
            ]:
                continue

            found.append({
                "key": signal_key,
                "signal": signal
            })

        if not found:
            print("No valid historical setups found.")
            continue

        for item in found:

            s = item["signal"]

            total += 1

            print()
            print("VALID SETUP FOUND")
            print("Time:", s.get("bar"))
            print("Pair:", s.get("symbol"))
            print("Direction:", s.get("side"))
            print("H1 Bias:", s.get("bias"))
            print("Entry:", s.get("entry"))
            print("Stop Loss:", s.get("sl"))
            print("Take Profit:", s.get("tp1"))
            print("R:R:", s.get("rr"))
            print("Reason:", s.get("reason"))

    print()
    print("=" * 60)
    print("TOTAL VALID SETUPS:", total)
    print("=" * 60)


if __name__ == "__main__":
    main()
