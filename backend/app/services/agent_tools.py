from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.services.data_fetcher import (
    DataFetchError,
    get_announcements,
    get_dragon_tiger,
    get_financial_statements,
    get_fund_flow,
    get_fundamentals,
    get_klines,
    get_lockup_expiry,
    get_market_news,
    get_margin_trading,
    get_northbound_flow,
    get_realtime_quote,
    get_research_reports,
)
from app.services.stock_catalog import get_stock_profile
from app.services.technical_indicators import calculate_indicators


class AgentToolError(RuntimeError):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class ToolSpec:
    key: str
    name: str
    description: str
    category: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    enabled: bool = True


ToolHandler = Callable[[Session, dict[str, Any]], dict[str, Any]]


def _text_schema(description: str) -> dict[str, str]:
    return {"type": "string", "description": description}


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "stock.quote": ToolSpec(
        key="stock.quote",
        name="实时行情",
        description="读取个股实时行情，复用现有数据源路由与缓存策略。",
        category="market",
        input_schema={
            "type": "object",
            "required": ["symbol"],
            "properties": {"symbol": _text_schema("股票代码，如 300750")},
        },
        output_schema={"type": "object"},
        enabled=True,
    ),
    "stock.bars": ToolSpec(
        key="stock.bars",
        name="K线数据",
        description="读取个股 K 线序列，支持 5m/30m/60m/daily/weekly/monthly 等周期。",
        category="market",
        input_schema={
            "type": "object",
            "required": ["symbol", "period"],
            "properties": {
                "symbol": _text_schema("股票代码"),
                "period": _text_schema("周期，如 5m/30m/60m/daily/weekly/monthly"),
            },
        },
        output_schema={"type": "object"},
        enabled=True,
    ),
    "stock.indicators": ToolSpec(
        key="stock.indicators",
        name="技术指标",
        description="基于 K 线计算 MA、MACD、KDJ、RSI、BOLL 等技术指标。",
        category="market",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        enabled=True,
    ),
    "stock.news": ToolSpec(
        key="stock.news",
        name="个股新闻",
        description="读取市场快讯并按股票代码、股票名称和关联股票过滤。",
        category="news",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        enabled=True,
    ),
    "stock.announcements": ToolSpec(
        key="stock.announcements",
        name="公司公告",
        description="读取公司公告，复用现有公告数据源路由。",
        category="news",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        enabled=True,
    ),
    "stock.research_reports": ToolSpec(
        key="stock.research_reports",
        name="研报检索",
        description="读取券商研报列表，复用现有研报数据源路由。",
        category="news",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        enabled=True,
    ),
    "stock.fundamentals": ToolSpec(
        key="stock.fundamentals",
        name="基本面快照",
        description="读取估值、盈利、成长等基本面快照，复用现有基本面数据源路由。",
        category="fundamental",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        enabled=True,
    ),
    "stock.financial_statements": ToolSpec(
        key="stock.financial_statements",
        name="财务报表",
        description="读取利润表、资产负债表、现金流等财务报表。",
        category="fundamental",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        enabled=True,
    ),
    "stock.fund_flow": ToolSpec(
        key="stock.fund_flow",
        name="资金流",
        description="读取主力资金流向，复用现有资金流数据源路由。",
        category="capital",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        enabled=True,
    ),
    "market.northbound_flow": ToolSpec(
        key="market.northbound_flow",
        name="北向资金",
        description="读取北向资金数据，复用现有市场级数据源路由。",
        category="capital",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        enabled=True,
    ),
    "stock.dragon_tiger": ToolSpec(
        key="stock.dragon_tiger",
        name="龙虎榜",
        description="读取龙虎榜交易行为，复用现有交易行为数据源路由。",
        category="capital",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        enabled=True,
    ),
    "stock.margin_trading": ToolSpec(
        key="stock.margin_trading",
        name="融资融券",
        description="读取融资融券余额与变动，复用现有两融数据源路由。",
        category="capital",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        enabled=True,
    ),
    "stock.lockup_expiry": ToolSpec(
        key="stock.lockup_expiry",
        name="限售解禁",
        description="读取限售解禁风险，复用现有风险数据源路由。",
        category="risk",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        enabled=True,
    ),
    "data.quality": ToolSpec(
        key="data.quality",
        name="数据质量",
        description="读取数据质量评分与告警。执行器后续接入数据源健康服务。",
        category="risk",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        enabled=False,
    ),
    "sector.snapshots": ToolSpec(
        key="sector.snapshots",
        name="板块概览",
        description="读取行业/概念板块快照。执行器后续接入板块数据服务。",
        category="macro",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        enabled=False,
    ),
    "market.macro": ToolSpec(
        key="market.macro",
        name="宏观指标",
        description="读取 CPI、PMI 等宏观指标。执行器后续接入宏观数据服务。",
        category="macro",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        enabled=False,
    ),
    "document.write": ToolSpec(
        key="document.write",
        name="文档编写",
        description="根据结构化输入生成 Markdown 研究文档，并保存到本地报告目录。",
        category="document",
        input_schema={
            "type": "object",
            "required": ["title", "topic"],
            "properties": {
                "title": _text_schema("文档标题"),
                "topic": _text_schema("研究主题或股票代码"),
                "summary": _text_schema("核心摘要"),
                "sections": {
                    "type": "array",
                    "description": "章节列表。每项可包含 heading 与 bullets。",
                    "items": {
                        "type": "object",
                        "properties": {
                            "heading": _text_schema("章节标题"),
                            "bullets": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                },
                "references": {
                    "type": "array",
                    "description": "引用来源或数据快照标识。",
                    "items": {"type": "string"},
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
        },
    ),
    "knowledge.search": ToolSpec(
        key="knowledge.search",
        name="知识库检索",
        description="预留给专业 RAG 系统的检索入口，后续接入索引、召回、重排和引用追踪。",
        category="knowledge",
        input_schema={
            "type": "object",
            "required": ["query"],
            "properties": {"query": _text_schema("检索问题")},
        },
        output_schema={"type": "object"},
        enabled=False,
    ),
}


def list_tool_specs(include_disabled: bool = True) -> list[ToolSpec]:
    specs = list(TOOL_REGISTRY.values())
    if not include_disabled:
        specs = [spec for spec in specs if spec.enabled]
    return sorted(specs, key=lambda item: (item.category, item.key))


def get_tool_spec(tool_key: str) -> ToolSpec:
    spec = TOOL_REGISTRY.get(tool_key)
    if not spec:
        raise AgentToolError("Tool not found.", status_code=404)
    return spec


def execute_tool(db: Session, tool_key: str, params: dict[str, Any]) -> dict[str, Any]:
    spec = get_tool_spec(tool_key)
    if not spec.enabled:
        raise AgentToolError("Tool is disabled.", status_code=409)
    handler = _HANDLERS.get(tool_key)
    if not handler:
        raise AgentToolError("Tool handler is not implemented.", status_code=501)
    return handler(db, params)


def _require_text(params: dict[str, Any], key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AgentToolError(f"Missing required text field: {key}.")
    return value.strip()


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _safe_filename(title: str) -> str:
    normalized = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", title, flags=re.UNICODE).strip("-")
    return normalized[:80] or "agent-report"


def _int_param(params: dict[str, Any], key: str, default: int, minimum: int, maximum: int) -> int:
    value = params.get(key, default)
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise AgentToolError(f"Invalid integer field: {key}.") from exc
    return min(max(parsed, minimum), maximum)


def _model_to_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict"):
        return value.dict()
    return dict(value)


def _quote_tool(db: Session, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_text(params, "symbol")
    try:
        quote = get_realtime_quote(db, symbol)
    except DataFetchError as exc:
        status_code = 400 if exc.error_type.startswith("invalid") else 502
        raise AgentToolError(str(exc), status_code=status_code) from exc
    return _model_to_dict(quote)


def _bars_tool(db: Session, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_text(params, "symbol")
    period = str(params.get("period") or "daily")
    adjust = str(params.get("adjust") or "qfq")
    limit = _int_param(params, "limit", 120, 1, 800)
    try:
        bars = get_klines(db, symbol=symbol, period=period, limit=limit, adjust=adjust)
    except DataFetchError as exc:
        status_code = 400 if exc.error_type.startswith("invalid") else 502
        raise AgentToolError(str(exc), status_code=status_code) from exc
    return _model_to_dict(bars)


def _indicators_tool(db: Session, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_text(params, "symbol")
    period = str(params.get("period") or "daily")
    adjust = str(params.get("adjust") or "qfq")
    limit = _int_param(params, "limit", 120, 1, 800)
    names_value = params.get("names", ["ma", "macd", "rsi", "kdj", "boll"])
    if isinstance(names_value, str):
        names = [item.strip() for item in names_value.split(",") if item.strip()]
    else:
        names = _string_list(names_value)
    try:
        bars = get_klines(db, symbol=symbol, period=period, limit=limit, adjust=adjust)
        indicators = calculate_indicators(bars, names)
    except DataFetchError as exc:
        status_code = 400 if exc.error_type.startswith("invalid") else 502
        raise AgentToolError(str(exc), status_code=status_code) from exc
    return _model_to_dict(indicators)


def _stock_news_tool(db: Session, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_text(params, "symbol")
    limit = _int_param(params, "limit", 30, 1, 100)
    normalized_symbol = symbol.strip().lower().removeprefix("sh").removeprefix("sz").removeprefix("bj")
    profile = get_stock_profile(symbol)
    keywords = [normalized_symbol]
    if profile:
        keywords.append(profile.name)
    try:
        news = get_market_news(db, limit=100)
    except DataFetchError as exc:
        raise AgentToolError(str(exc), status_code=502) from exc
    filtered = [
        item
        for item in news.items
        if any(keyword and keyword in f"{item.title}{item.content}" for keyword in keywords)
        or normalized_symbol in item.related_stocks
    ]
    payload = _model_to_dict(news)
    payload["items"] = [
        _model_to_dict(item) if not isinstance(item, dict) else item
        for item in filtered[:limit]
    ]
    payload["symbol"] = normalized_symbol
    return payload


def _announcements_tool(db: Session, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_text(params, "symbol")
    limit = _int_param(params, "limit", 20, 1, 100)
    try:
        announcements = get_announcements(db, symbol=symbol, limit=limit)
    except DataFetchError as exc:
        raise AgentToolError(str(exc), status_code=502) from exc
    return _model_to_dict(announcements)


def _research_reports_tool(db: Session, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_text(params, "symbol")
    limit = _int_param(params, "limit", 10, 1, 50)
    try:
        reports = get_research_reports(db, symbol=symbol, limit=limit)
    except DataFetchError as exc:
        raise AgentToolError(str(exc), status_code=502) from exc
    return _model_to_dict(reports)


def _fundamentals_tool(db: Session, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_text(params, "symbol")
    try:
        fundamentals = get_fundamentals(db, symbol=symbol)
    except DataFetchError as exc:
        raise AgentToolError(str(exc), status_code=502) from exc
    return _model_to_dict(fundamentals)


def _financial_statements_tool(db: Session, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_text(params, "symbol")
    statement_type = str(params.get("statement_type") or "income")
    limit = _int_param(params, "limit", 4, 1, 20)
    try:
        statements = get_financial_statements(
            db,
            symbol=symbol,
            statement_type=statement_type,
            limit=limit,
        )
    except DataFetchError as exc:
        status_code = 400 if exc.error_type.startswith("invalid") else 502
        raise AgentToolError(str(exc), status_code=status_code) from exc
    return _model_to_dict(statements)


def _fund_flow_tool(db: Session, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_text(params, "symbol")
    limit = _int_param(params, "limit", 20, 1, 120)
    try:
        flow = get_fund_flow(db, symbol=symbol, limit=limit)
    except DataFetchError as exc:
        raise AgentToolError(str(exc), status_code=502) from exc
    return _model_to_dict(flow)


def _northbound_flow_tool(db: Session, params: dict[str, Any]) -> dict[str, Any]:
    limit = _int_param(params, "limit", 20, 1, 100)
    try:
        flow = get_northbound_flow(db, limit=limit)
    except DataFetchError as exc:
        raise AgentToolError(str(exc), status_code=502) from exc
    return _model_to_dict(flow)


def _dragon_tiger_tool(db: Session, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_text(params, "symbol")
    limit = _int_param(params, "limit", 10, 1, 50)
    try:
        data = get_dragon_tiger(db, symbol=symbol, limit=limit)
    except DataFetchError as exc:
        raise AgentToolError(str(exc), status_code=502) from exc
    return _model_to_dict(data)


def _lockup_expiry_tool(db: Session, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_text(params, "symbol")
    limit = _int_param(params, "limit", 10, 1, 50)
    try:
        data = get_lockup_expiry(db, symbol=symbol, limit=limit)
    except DataFetchError as exc:
        raise AgentToolError(str(exc), status_code=502) from exc
    return _model_to_dict(data)


def _margin_trading_tool(db: Session, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_text(params, "symbol")
    limit = _int_param(params, "limit", 10, 1, 50)
    try:
        data = get_margin_trading(db, symbol=symbol, limit=limit)
    except DataFetchError as exc:
        raise AgentToolError(str(exc), status_code=502) from exc
    return _model_to_dict(data)


def _write_document(_: Session, params: dict[str, Any]) -> dict[str, Any]:
    title = _require_text(params, "title")
    topic = _require_text(params, "topic")
    summary = str(params.get("summary", "")).strip()
    sections = params.get("sections") if isinstance(params.get("sections"), list) else []
    references = _string_list(params.get("references"))
    now = datetime.now(ZoneInfo("Asia/Shanghai"))

    lines = [
        f"# {title}",
        "",
        f"- 主题: {topic}",
        f"- 生成时间: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        "",
    ]
    if summary:
        lines.extend(["## 摘要", "", summary, ""])

    for index, section in enumerate(sections, start=1):
        if isinstance(section, dict):
            heading = str(section.get("heading") or f"章节 {index}").strip()
            bullets = _string_list(section.get("bullets"))
        else:
            heading = f"章节 {index}"
            bullets = [str(section).strip()]
        lines.extend([f"## {heading}", ""])
        if bullets:
            lines.extend([f"- {item}" for item in bullets])
        else:
            lines.append("- 待补充")
        lines.append("")

    if references:
        lines.extend(["## 引用与数据来源", ""])
        lines.extend([f"- {item}" for item in references])
        lines.append("")

    content = "\n".join(lines).rstrip() + "\n"
    output_dir = Path("data") / "generated_reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / f"{now.strftime('%Y%m%d-%H%M%S')}-{_safe_filename(title)}.md"
    file_path.write_text(content, encoding="utf-8")

    return {
        "title": title,
        "path": str(file_path.resolve()),
        "content": content,
        "bytes": file_path.stat().st_size,
    }


_HANDLERS: dict[str, ToolHandler] = {
    "stock.quote": _quote_tool,
    "stock.bars": _bars_tool,
    "stock.indicators": _indicators_tool,
    "stock.news": _stock_news_tool,
    "stock.announcements": _announcements_tool,
    "stock.research_reports": _research_reports_tool,
    "stock.fundamentals": _fundamentals_tool,
    "stock.financial_statements": _financial_statements_tool,
    "stock.fund_flow": _fund_flow_tool,
    "market.northbound_flow": _northbound_flow_tool,
    "stock.dragon_tiger": _dragon_tiger_tool,
    "stock.lockup_expiry": _lockup_expiry_tool,
    "stock.margin_trading": _margin_trading_tool,
    "document.write": _write_document,
}
