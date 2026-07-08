from app.schemas.data_source import StockProfile, StockSearchItem


STOCKS = [
    StockSearchItem(symbol="300750", name="宁德时代", exchange="SZSE", pinyin="NDSD"),
    StockSearchItem(symbol="600519", name="贵州茅台", exchange="SSE", pinyin="GZMT"),
    StockSearchItem(symbol="002475", name="立讯精密", exchange="SZSE", pinyin="LXJM"),
    StockSearchItem(symbol="000333", name="美的集团", exchange="SZSE", pinyin="MDJT"),
    StockSearchItem(symbol="601318", name="中国平安", exchange="SSE", pinyin="ZGPA"),
    StockSearchItem(symbol="601012", name="隆基绿能", exchange="SSE", pinyin="LJLN"),
    StockSearchItem(symbol="688981", name="中芯国际", exchange="SSE", pinyin="ZXGJ"),
]


def search_stocks(query: str, limit: int = 20) -> list[StockSearchItem]:
    normalized = query.strip().upper()
    if not normalized:
        return STOCKS[:limit]
    matches = [
        stock
        for stock in STOCKS
        if normalized in stock.symbol
        or normalized in stock.name.upper()
        or normalized in stock.pinyin.upper()
    ]
    return matches[:limit]


def get_stock_profile(symbol: str) -> StockProfile | None:
    normalized = symbol.strip().lower()
    for prefix in ("sh", "sz", "bj"):
        if normalized.startswith(prefix):
            normalized = normalized[2:]
    stock = next((item for item in STOCKS if item.symbol == normalized), None)
    if not stock:
        return None
    return StockProfile(
        symbol=stock.symbol,
        name=stock.name,
        exchange=stock.exchange,
        data_sources=["tencent_quote", "eastmoney_push2his", "sina_kline", "cls"],
    )
