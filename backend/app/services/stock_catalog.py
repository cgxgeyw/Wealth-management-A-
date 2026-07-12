import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.stock_catalog import StockCatalogItem
from app.schemas.data_source import StockProfile, StockSearchItem


STOCKS = [
    StockSearchItem(symbol="300750", name="宁德时代", exchange="SZSE", pinyin="NDSD"),
    StockSearchItem(symbol="600519", name="贵州茅台", exchange="SSE", pinyin="GZMT"),
    StockSearchItem(symbol="002475", name="立讯精密", exchange="SZSE", pinyin="LXJM"),
    StockSearchItem(symbol="002837", name="英维克", exchange="SZSE", pinyin="YWK"),
    StockSearchItem(symbol="000333", name="美的集团", exchange="SZSE", pinyin="MDJT"),
    StockSearchItem(symbol="601318", name="中国平安", exchange="SSE", pinyin="ZGPA"),
    StockSearchItem(symbol="601012", name="隆基绿能", exchange="SSE", pinyin="LJLN"),
    StockSearchItem(symbol="688981", name="中芯国际", exchange="SSE", pinyin="ZXGJ"),
]

SINA_CATALOG_URL = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
EASTMONEY_CATALOG_URL = "https://push2.eastmoney.com/api/qt/clist/get"
CATALOG_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Referer": "https://finance.sina.com.cn/",
}


def search_stocks(db: Session, query: str, limit: int = 20) -> list[StockSearchItem]:
    normalized = query.strip().upper()
    rows = (
        db.scalars(
            select(StockCatalogItem)
            .where(or_(StockCatalogItem.name.contains(query.strip()), StockCatalogItem.symbol.contains(normalized)))
            .order_by(StockCatalogItem.symbol)
            .limit(limit)
        ).all()
        if query.strip()
        else []
    )
    catalog_matches = [StockSearchItem(symbol=row.symbol, name=row.name, exchange=row.exchange, pinyin="") for row in rows]
    if catalog_matches:
        return catalog_matches
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


def _fetch_sina_catalog(client: httpx.Client) -> list[dict]:
    rows: list[dict] = []
    for page in range(1, 101):
        response = client.get(
            SINA_CATALOG_URL,
            params={"page": page, "num": 100, "sort": "symbol", "asc": 1, "node": "hs_a", "symbol": "", "_s_r_a": "page"},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise httpx.DecodingError("Sina stock catalog response is not a list", request=response.request)
        rows.extend(item for item in payload if isinstance(item, dict))
        if len(payload) < 100:
            break
    if len(rows) < 1000:
        raise httpx.DecodingError("Sina stock catalog response is incomplete")
    return rows


def _fetch_eastmoney_catalog(client: httpx.Client) -> list[dict]:
    rows: list[dict] = []
    for page in (1, 2):
        response = client.get(
            EASTMONEY_CATALOG_URL,
            params={"pn": page, "pz": 5000, "po": 1, "np": 1, "fltt": 2, "invt": 2, "fid": "f3", "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048", "fields": "f12,f14"},
        )
        response.raise_for_status()
        diff = (response.json().get("data") or {}).get("diff") or []
        if isinstance(diff, dict):
            diff = list(diff.values())
        rows.extend(item for item in diff if isinstance(item, dict))
        if len(diff) < 5000:
            break
    return rows


def _catalog_item(item: dict, provider: str) -> tuple[str, str, str] | None:
    if provider == "sina":
        symbol = str(item.get("code") or "")
        name = str(item.get("name") or "")
        market_symbol = str(item.get("symbol") or "")
        exchange = {"sh": "SSE", "sz": "SZSE", "bj": "BSE"}.get(market_symbol[:2].lower(), "")
    else:
        symbol = str(item.get("f12") or "")
        name = str(item.get("f14") or "")
        exchange = "SSE" if symbol.startswith(("6", "68")) else "SZSE" if symbol.startswith(("0", "3")) else "BSE"
    return (symbol, name, exchange) if symbol and name else None


def sync_stock_catalog(db: Session) -> tuple[int, str]:
    StockCatalogItem.__table__.create(bind=db.get_bind(), checkfirst=True)
    with httpx.Client(timeout=20, headers=CATALOG_HEADERS, follow_redirects=True) as client:
        try:
            provider, rows = "sina", _fetch_sina_catalog(client)
        except httpx.HTTPError:
            provider, rows = "eastmoney", _fetch_eastmoney_catalog(client)
    existing = {item.symbol: item for item in db.scalars(select(StockCatalogItem)).all()}
    catalog_symbols: set[str] = set()
    count = 0
    for item in rows:
        catalog_item = _catalog_item(item, provider)
        if not catalog_item:
            continue
        symbol, name, exchange = catalog_item
        catalog_symbols.add(symbol)
        row = existing.get(symbol)
        if row:
            row.name, row.exchange = name, exchange
        else:
            db.add(StockCatalogItem(symbol=symbol, name=name, exchange=exchange))
        count += 1
    for symbol, row in existing.items():
        if symbol not in catalog_symbols:
            db.delete(row)
    db.commit()
    return count, provider


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
