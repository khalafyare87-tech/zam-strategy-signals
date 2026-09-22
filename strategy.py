def pivots(d, left=2, right=2):
    highs = []
    lows = []

    for i in range(left, len(d) - right):
        w = d[i-left:i+right+1]
        x = d[i]

        high = float(x["high"])
        low = float(x["low"])

        if high == max(float(z["high"]) for z in w):
            highs.append((i, high))

        if low == min(float(z["low"]) for z in w):
            lows.append((i, low))

    return highs, lows


def bias(h1):
    h, l = pivots(h1[:-1])

    if len(h) < 2 or len(l) < 2:
        return "NEUTRAL"

    if h[-1][1] > h[-2][1] and l[-1][1] > l[-2][1]:
        return "BULLISH"

    if h[-1][1] < h[-2][1] and l[-1][1] < l[-2][1]:
        return "BEARISH"

    return "NEUTRAL"


def fmt(symbol, x):
    if symbol == "XAU/USD":
        return f"{x:.2f}"

    return f"{x:.5f}"


class StrategyEngine:

    def find_signal(self, symbol, h1, m15):

        # Ignore the currently forming 15-minute candle.
        d = m15[:-1]

        if len(d) < 80:
            return None

        b = bias(h1)

        if b == "NEUTRAL":
            return None

        d = d[-80:]

        hi, lo = pivots(d)

        buf = {
            "XAU/USD": 0.80,
            "EUR/USD": 0.00015,
            "GBP/USD": 0.00020
        }.get(symbol, 0.0002)

        # =========================
        # BEARISH SETUP
        # Sweep -> BOS -> Retest
        # =========================

        if b == "BEARISH":

            for si in range(
                len(d) - 8,
                max(8, len(d) - 35),
                -1
            ):

                ph = [
                    p for p in hi
                    if p[0] < si
                ]

                if not ph:
                    continue

                level = max(
                    p[1] for p in ph[-3:]
                )

                s = d[si]

                if not (
                    float(s["high"]) >= level
                    and float(s["close"]) < level
                ):
                    continue

                pl = [
                    p for p in lo
                    if p[0] < si
                ]

                if not pl:
                    continue

                bos = pl[-1][1]

                bi = next(
                    (
                        j for j in range(
                            si + 1,
                            min(si + 9, len(d))
                        )
                        if float(d[j]["close"]) < bos
                    ),
                    None
                )

                if bi is None:
                    continue

                # Only the latest closed candle can trigger
                # the retest signal.
                r = len(d) - 1

                if r <= bi:
                    continue

                c = d[r]

                if (
                    float(c["high"]) >= bos - 1.5 * buf
                    and float(c["close"]) < bos
                ):

                    entry = float(c["close"])

                    sl = max(
                        float(s["high"]),
                        level
                    ) + buf

                    risk = sl - entry

                    if risk <= 0:
                        continue

                    return {
                        "symbol": symbol,
                        "side": "SELL",
                        "bias": b,
                        "entry": fmt(symbol, entry),
                        "sl": fmt(symbol, sl),
                        "tp1": fmt(symbol, entry - 2 * risk),
                        "rr": 2.0,
                        "bar": c["datetime"],
                        "reason": (
                            f"Sweep/rejection near "
                            f"{fmt(symbol, level)}, "
                            f"bearish BOS below "
                            f"{fmt(symbol, bos)}, "
                            f"then latest-candle "
                            f"retest rejection."
                        )
                    }

        # =========================
        # BULLISH SETUP
        # Sweep -> BOS -> Retest
        # =========================

        if b == "BULLISH":

            for si in range(
                len(d) - 8,
                max(8, len(d) - 35),
                -1
            ):

                pl = [
                    p for p in lo
                    if p[0] < si
                ]

                if not pl:
                    continue

                level = min(
                    p[1] for p in pl[-3:]
                )

                s = d[si]

                if not (
                    float(s["low"]) <= level
                    and float(s["close"]) > level
                ):
                    continue

                ph = [
                    p for p in hi
                    if p[0] < si
                ]

                if not ph:
                    continue

                bos = ph[-1][1]

                bi = next(
                    (
                        j for j in range(
                            si + 1,
                            min(si + 9, len(d))
                        )
                        if float(d[j]["close"]) > bos
                    ),
                    None
                )

                if bi is None:
                    continue

                # Only the latest closed candle can trigger
                # the retest signal.
                r = len(d) - 1

                if r <= bi:
                    continue

                c = d[r]

                if (
                    float(c["low"]) <= bos + 1.5 * buf
                    and float(c["close"]) > bos
                ):

                    entry = float(c["close"])

                    sl = min(
                        float(s["low"]),
                        level
                    ) - buf

                    risk = entry - sl

                    if risk <= 0:
                        continue

                    return {
                        "symbol": symbol,
                        "side": "BUY",
                        "bias": b,
                        "entry": fmt(symbol, entry),
                        "sl": fmt(symbol, sl),
                        "tp1": fmt(symbol, entry + 2 * risk),
                        "rr": 2.0,
                        "bar": c["datetime"],
                        "reason": (
                            f"Sweep/rejection near "
                            f"{fmt(symbol, level)}, "
                            f"bullish BOS above "
                            f"{fmt(symbol, bos)}, "
                            f"then latest-candle "
                            f"retest confirmation."
                        )
                    }

        return None
