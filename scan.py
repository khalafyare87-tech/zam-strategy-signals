import os
import requests
from strategy import StrategyEngine

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
API_KEY = os.environ["TWELVE_DATA_API_KEY"]
TEST_TELEGRAM = os.getenv("TEST_TELEGRAM", "false").lower() == "true"
SYMBOLS = [
    x.strip()
    for x in os.getenv(
        "SYMBOLS",
        "XAU/USD,EUR/USD,GBP/USD"
    ).split(",")
    if x.strip()
]


def get_bars(symbol, interval, size=250):

    response = requests.get(
        "https://api.twelvedata.com/time_series",
        params={
            "symbol": symbol,
            "interval": interval,
            "outputsize": size,
            "apikey": API_KEY,
            "timezone": "UTC"
        },
        timeout=20
    )

    response.raise_for_status()

    data = response.json()

    if "values" not in data:
        raise RuntimeError(str(data))

    return list(reversed(data["values"]))


def send_telegram(message):

    response = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": message
        },
        timeout=20
    )

    response.raise_for_status()


def format_signal(signal):

    icon = "🟢 BUY" if signal["side"] == "BUY" else "🔴 SELL"

    return (
        f"🚨 {icon} — VALID SETUP\n\n"
        f"Pair: {signal['symbol']}\n"
        f"Strategy: H1 Bias → M15 Sweep → BOS → Retest\n"
        f"Bias: {signal['bias']}\n\n"
        f"Entry: {signal['entry']}\n"
        f"SL: {signal['sl']}\n"
        f"TP1: {signal['tp1']}\n"
        f"R:R: 1:{signal['rr']:.1f}\n\n"
        f"Why:\n{signal['reason']}\n\n"
        f"⚠️ Manual execution only.\n"
        f"This bot does NOT open trades.\n\n"
        f"Risk reference: maximum $125 "
        f"(0.25% of $50,000)."
    )


def main():

    engine = StrategyEngine()

    signals_sent = 0

    for symbol in SYMBOLS:

        try:

            h1 = get_bars(
                symbol,
                "1h",
                250
            )

            m15 = get_bars(
                symbol,
                "15min",
                300
            )

            signal = engine.find_signal(
                symbol,
                h1,
                m15
            )

            if signal:

                send_telegram(
                    format_signal(signal)
                )

                signals_sent += 1

                print(
                    f"Signal sent: "
                    f"{symbol} "
                    f"{signal['side']}"
                )

            else:

                print(
                    f"No valid setup: "
                    f"{symbol}"
                )

        except Exception as error:

            print(
                f"{symbol} error: "
                f"{error}"
            )

    print(
        f"Scan complete. "
        f"Signals sent: {signals_sent}"
    )


if __name__ == "__main__":
    main()
