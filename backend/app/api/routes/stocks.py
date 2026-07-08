from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.data_source import (
    AnnouncementResponse,
    DragonTigerResponse,
    FinancialStatementResponse,
    FundamentalResponse,
    FundFlowResponse,
    IndicatorResponse,
    KlineResponse,
    LockupExpiryResponse,
    MarginTradingResponse,
    NewsResponse,
    RealtimeQuote,
    ResearchReportResponse,
    StockProfile,
    StockSearchResponse,
)
from app.services.data_fetcher import (
    DataFetchError,
    get_announcements,
    get_dragon_tiger,
    get_financial_statements,
    get_fund_flow,
    get_fundamentals,
    get_klines,
    get_lockup_expiry,
    get_margin_trading,
    get_market_news,
    get_realtime_quote,
    get_research_reports,
)
from app.services.stock_catalog import get_stock_profile, search_stocks
from app.services.technical_indicators import calculate_indicators

router = APIRouter()


@router.get("/search", response_model=StockSearchResponse)
def search(q: str = "", limit: int = 20) -> StockSearchResponse:
    return StockSearchResponse(items=search_stocks(q, min(max(limit, 1), 100)))


@router.get("/{symbol}/profile", response_model=StockProfile)
def profile(symbol: str) -> StockProfile:
    result = get_stock_profile(symbol)
    if not result:
        raise HTTPException(status_code=404, detail="Stock not found.")
    return result


@router.get("/{symbol}/quote", response_model=RealtimeQuote)
def quote(symbol: str, db: Session = Depends(get_db)) -> RealtimeQuote:
    try:
        return get_realtime_quote(db, symbol)
    except DataFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{symbol}/bars", response_model=KlineResponse)
def bars(
    symbol: str,
    period: str = "daily",
    limit: int = 120,
    adjust: str = "qfq",
    db: Session = Depends(get_db),
) -> KlineResponse:
    try:
        return get_klines(db, symbol=symbol, period=period, limit=limit, adjust=adjust)
    except DataFetchError as exc:
        status_code = 400 if exc.error_type == "invalid_period" else 502
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("/{symbol}/indicators", response_model=IndicatorResponse)
def indicators(
    symbol: str,
    names: str = "ma,macd,rsi,kdj,boll",
    period: str = "daily",
    limit: int = 120,
    db: Session = Depends(get_db),
) -> IndicatorResponse:
    try:
        kline = get_klines(db, symbol=symbol, period=period, limit=limit)
    except DataFetchError as exc:
        status_code = 400 if exc.error_type == "invalid_period" else 502
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return calculate_indicators(kline, names.split(","))


@router.get("/{symbol}/news", response_model=NewsResponse)
def stock_news(symbol: str, limit: int = 30, db: Session = Depends(get_db)) -> NewsResponse:
    profile_result = get_stock_profile(symbol)
    normalized_symbol = symbol.strip().lower().removeprefix("sh").removeprefix("sz").removeprefix("bj")
    try:
        news = get_market_news(db, limit=100)
    except DataFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    keywords = [normalized_symbol]
    if profile_result:
        keywords.append(profile_result.name)
    filtered = [
        item
        for item in news.items
        if any(keyword and keyword in f"{item.title}{item.content}" for keyword in keywords)
        or normalized_symbol in item.related_stocks
    ]
    return NewsResponse(provider_key=news.provider_key, items=filtered[: min(max(limit, 1), 100)])


@router.get("/{symbol}/announcements", response_model=AnnouncementResponse)
def announcements(
    symbol: str,
    limit: int = 20,
    db: Session = Depends(get_db),
) -> AnnouncementResponse:
    try:
        return get_announcements(db, symbol=symbol, limit=limit)
    except DataFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{symbol}/fundamentals", response_model=FundamentalResponse)
def fundamentals(symbol: str, db: Session = Depends(get_db)) -> FundamentalResponse:
    try:
        return get_fundamentals(db, symbol=symbol)
    except DataFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{symbol}/financial-statements", response_model=FinancialStatementResponse)
def financial_statements(
    symbol: str,
    statement_type: str = "income",
    limit: int = 4,
    db: Session = Depends(get_db),
) -> FinancialStatementResponse:
    try:
        return get_financial_statements(
            db,
            symbol=symbol,
            statement_type=statement_type,
            limit=limit,
        )
    except DataFetchError as exc:
        status_code = 400 if exc.error_type == "invalid_statement_type" else 502
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("/{symbol}/fund-flow", response_model=FundFlowResponse)
def fund_flow(symbol: str, limit: int = 20, db: Session = Depends(get_db)) -> FundFlowResponse:
    try:
        return get_fund_flow(db, symbol=symbol, limit=limit)
    except DataFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{symbol}/research-reports", response_model=ResearchReportResponse)
def research_reports(
    symbol: str,
    limit: int = 10,
    db: Session = Depends(get_db),
) -> ResearchReportResponse:
    try:
        return get_research_reports(db, symbol=symbol, limit=limit)
    except DataFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{symbol}/dragon-tiger", response_model=DragonTigerResponse)
def dragon_tiger(symbol: str, limit: int = 10, db: Session = Depends(get_db)) -> DragonTigerResponse:
    try:
        return get_dragon_tiger(db, symbol=symbol, limit=limit)
    except DataFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{symbol}/lockup-expiry", response_model=LockupExpiryResponse)
def lockup_expiry(
    symbol: str,
    limit: int = 10,
    db: Session = Depends(get_db),
) -> LockupExpiryResponse:
    try:
        return get_lockup_expiry(db, symbol=symbol, limit=limit)
    except DataFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{symbol}/margin-trading", response_model=MarginTradingResponse)
def margin_trading(
    symbol: str,
    limit: int = 10,
    db: Session = Depends(get_db),
) -> MarginTradingResponse:
    try:
        return get_margin_trading(db, symbol=symbol, limit=limit)
    except DataFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
