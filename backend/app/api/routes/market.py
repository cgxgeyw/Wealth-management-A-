from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.data_source import MacroIndicatorResponse, NewsResponse, NorthboundFlowResponse
from app.services.data_fetcher import DataFetchError, get_macro_indicator, get_market_news, get_northbound_flow

router = APIRouter()


@router.get("/news", response_model=NewsResponse)
def news(limit: int = 30, db: Session = Depends(get_db)) -> NewsResponse:
    try:
        return get_market_news(db, limit=limit)
    except DataFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/northbound-flow", response_model=NorthboundFlowResponse)
def northbound_flow(limit: int = 20, db: Session = Depends(get_db)) -> NorthboundFlowResponse:
    try:
        return get_northbound_flow(db, limit=limit)
    except DataFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/macro", response_model=MacroIndicatorResponse)
def macro(
    indicator: str = "cpi",
    limit: int = 12,
    db: Session = Depends(get_db),
) -> MacroIndicatorResponse:
    try:
        return get_macro_indicator(db, indicator=indicator, limit=limit)
    except DataFetchError as exc:
        status_code = 400 if exc.error_type == "invalid_macro_indicator" else 502
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
