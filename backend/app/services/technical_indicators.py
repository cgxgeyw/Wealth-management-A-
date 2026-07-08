from app.schemas.data_source import IndicatorResponse, IndicatorSeries, KlineBar, KlineResponse


def calculate_indicators(
    kline: KlineResponse,
    names: list[str],
) -> IndicatorResponse:
    requested = {name.strip().lower() for name in names if name.strip()}
    if not requested:
        requested = {"ma", "macd", "rsi", "kdj", "boll"}

    items: list[IndicatorSeries] = []
    bars = kline.items
    if "ma" in requested:
        items.extend(
            [
                IndicatorSeries(name="MA5", values=moving_average(bars, 5)),
                IndicatorSeries(name="MA10", values=moving_average(bars, 10)),
                IndicatorSeries(name="MA20", values=moving_average(bars, 20)),
            ]
        )
    if "macd" in requested:
        dif, dea, hist = macd(bars)
        items.extend(
            [
                IndicatorSeries(name="DIF", values=dif),
                IndicatorSeries(name="DEA", values=dea),
                IndicatorSeries(name="MACD", values=hist),
            ]
        )
    if "rsi" in requested:
        items.append(IndicatorSeries(name="RSI14", values=rsi(bars, 14)))
    if "kdj" in requested:
        k, d, j = kdj(bars, 9)
        items.extend(
            [
                IndicatorSeries(name="K", values=k),
                IndicatorSeries(name="D", values=d),
                IndicatorSeries(name="J", values=j),
            ]
        )
    if "boll" in requested:
        upper, middle, lower = boll(bars, 20)
        items.extend(
            [
                IndicatorSeries(name="BOLL_UPPER", values=upper),
                IndicatorSeries(name="BOLL_MIDDLE", values=middle),
                IndicatorSeries(name="BOLL_LOWER", values=lower),
            ]
        )

    return IndicatorResponse(
        symbol=kline.symbol,
        period=kline.period,
        source=kline.provider_key,
        items=items,
    )


def moving_average(bars: list[KlineBar], period: int) -> list[float | None]:
    result: list[float | None] = []
    for index, _ in enumerate(bars):
        if index + 1 < period:
            result.append(None)
            continue
        window = bars[index + 1 - period : index + 1]
        result.append(round(sum(item.close for item in window) / period, 4))
    return result


def ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    factor = 2 / (period + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append(value * factor + result[-1] * (1 - factor))
    return result


def macd(bars: list[KlineBar]) -> tuple[list[float], list[float], list[float]]:
    closes = [bar.close for bar in bars]
    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    dif = [round(ema12[index] - ema26[index], 4) for index in range(len(closes))]
    dea_raw = ema(dif, 9)
    dea = [round(value, 4) for value in dea_raw]
    hist = [round((dif[index] - dea[index]) * 2, 4) for index in range(len(dif))]
    return dif, dea, hist


def rsi(bars: list[KlineBar], period: int) -> list[float | None]:
    result: list[float | None] = []
    for index, _ in enumerate(bars):
        if index < period:
            result.append(None)
            continue
        gains = 0.0
        losses = 0.0
        for cursor in range(index - period + 1, index + 1):
            change = bars[cursor].close - bars[cursor - 1].close
            if change >= 0:
                gains += change
            else:
                losses += abs(change)
        if losses == 0:
            result.append(100.0)
        else:
            rs = gains / losses
            result.append(round(100 - 100 / (1 + rs), 4))
    return result


def kdj(bars: list[KlineBar], period: int) -> tuple[list[float | None], list[float | None], list[float | None]]:
    previous_k = 50.0
    previous_d = 50.0
    k_values: list[float | None] = []
    d_values: list[float | None] = []
    j_values: list[float | None] = []
    for index, bar in enumerate(bars):
        if index + 1 < period:
            k_values.append(None)
            d_values.append(None)
            j_values.append(None)
            continue
        window = bars[index + 1 - period : index + 1]
        low = min(item.low for item in window)
        high = max(item.high for item in window)
        rsv = 50.0 if high == low else ((bar.close - low) / (high - low)) * 100
        previous_k = (2 / 3) * previous_k + (1 / 3) * rsv
        previous_d = (2 / 3) * previous_d + (1 / 3) * previous_k
        k_values.append(round(previous_k, 4))
        d_values.append(round(previous_d, 4))
        j_values.append(round(3 * previous_k - 2 * previous_d, 4))
    return k_values, d_values, j_values


def boll(bars: list[KlineBar], period: int) -> tuple[list[float | None], list[float | None], list[float | None]]:
    upper: list[float | None] = []
    middle = moving_average(bars, period)
    lower: list[float | None] = []
    for index, _ in enumerate(bars):
        mid = middle[index]
        if mid is None:
            upper.append(None)
            lower.append(None)
            continue
        closes = [item.close for item in bars[index + 1 - period : index + 1]]
        avg = sum(closes) / period
        variance = sum((value - avg) ** 2 for value in closes) / period
        std = variance**0.5
        upper.append(round(mid + 2 * std, 4))
        lower.append(round(mid - 2 * std, 4))
    return upper, middle, lower
