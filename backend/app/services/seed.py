import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import AgentConfig, AgentPromptVersion
from app.models.data_source import DataProvider, DataRoute, DataWatchlistItem


DEFAULT_PROVIDERS = [
    {
        "key": "eastmoney_push2his",
        "name": "东方财富 K 线",
        "type": "http",
        "auth_type": "none",
        "base_url": "https://push2his.eastmoney.com",
        "test_url": "https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=0.300750&fields1=f1&fields2=f51,f52,f53,f54,f55,f56&klt=101&fqt=1&beg=20260701&end=20260707",
        "cache_ttl_seconds": 60,
    },
    {
        "key": "sina_kline",
        "name": "新浪 K 线",
        "type": "http",
        "auth_type": "none",
        "base_url": "https://quotes.sina.cn",
        "test_url": "https://quotes.sina.cn",
        "cache_ttl_seconds": 60,
    },
    {
        "key": "tencent_quote",
        "name": "腾讯实时行情",
        "type": "http",
        "auth_type": "none",
        "base_url": "https://qt.gtimg.cn",
        "test_url": "https://qt.gtimg.cn/q=sz300750",
        "cache_ttl_seconds": 10,
    },
    {
        "key": "cls",
        "name": "财联社快讯",
        "type": "http",
        "auth_type": "none",
        "base_url": "https://www.cls.cn",
        "test_url": "https://www.cls.cn/api/cache?app=CailianpressWeb&name=telegraph&os=web&sv=8.7.9",
        "cache_ttl_seconds": 60,
    },
    {
        "key": "eastmoney_announcement",
        "name": "东方财富公告",
        "type": "http",
        "auth_type": "none",
        "base_url": "https://np-anotice-stock.eastmoney.com",
        "test_url": "https://np-anotice-stock.eastmoney.com/api/security/ann?sr=-1&page_size=1&page_index=1&ann_type=A&client_source=web&stock_list=300750",
        "cache_ttl_seconds": 3600,
    },
    {
        "key": "eastmoney_push2",
        "name": "东方财富实时扩展",
        "type": "http",
        "auth_type": "none",
        "base_url": "https://push2.eastmoney.com",
        "test_url": "https://push2.eastmoney.com/api/qt/stock/get?secid=0.300750&fields=f57,f58",
        "cache_ttl_seconds": 300,
    },
    {
        "key": "eastmoney_datacenter",
        "name": "东方财富数据中心",
        "type": "http",
        "auth_type": "none",
        "base_url": "https://datacenter-web.eastmoney.com",
        "test_url": "https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_DMSK_FN_INCOME&columns=SECURITY_CODE&filter=(SECURITY_CODE%3D%22300750%22)&pageNumber=1&pageSize=1",
        "cache_ttl_seconds": 3600,
    },
    {
        "key": "eastmoney_reportapi",
        "name": "东方财富研报",
        "type": "http",
        "auth_type": "none",
        "base_url": "https://reportapi.eastmoney.com",
        "test_url": "https://reportapi.eastmoney.com/report/list?pageSize=1&pageNo=1&qType=0&code=300750",
        "cache_ttl_seconds": 21600,
    },
    {
        "key": "tushare_pro",
        "name": "Tushare Pro",
        "type": "paid_api",
        "auth_type": "api_key",
        "base_url": "https://api.tushare.pro",
        "test_url": "",
        "enabled": False,
        "cache_ttl_seconds": 3600,
    },
    {
        "key": "iwencai",
        "name": "同花顺问财",
        "type": "openapi",
        "auth_type": "api_key",
        "base_url": "https://openapi.iwencai.com",
        "test_url": "",
        "enabled": False,
        "cache_ttl_seconds": 3600,
    },
]


DEFAULT_ROUTES = [
    ("daily_kline", "get_daily_kline", ["eastmoney_push2his", "sina_kline"]),
    ("minute_kline", "get_minute_kline", ["eastmoney_push2his", "sina_kline"]),
    ("realtime_quote", "get_realtime_quote", ["tencent_quote"]),
    ("market_news", "get_market_news", ["cls"]),
    ("announcement", "get_announcements", ["eastmoney_announcement"]),
    ("fundamental_snapshot", "get_fundamentals", ["eastmoney_push2"]),
    ("financial_statement", "get_financial_statements", ["eastmoney_datacenter"]),
    ("fund_flow", "get_fund_flow", ["eastmoney_push2"]),
    ("sector_snapshot", "get_sector_snapshots", ["eastmoney_push2"]),
    ("northbound_flow", "get_northbound_flow", ["eastmoney_datacenter"]),
    ("research_report", "get_research_report", ["eastmoney_reportapi", "iwencai"]),
    ("dragon_tiger", "get_dragon_tiger", ["eastmoney_datacenter"]),
    ("lockup_expiry", "get_lockup_expiry", ["eastmoney_datacenter"]),
    ("margin_trading", "get_margin_trading", ["eastmoney_datacenter"]),
    ("macro_indicator", "get_macro_indicator", ["eastmoney_datacenter", "tushare_pro"]),
]


DEFAULT_WATCHLIST = [
    ("300750", "宁德时代"),
    ("600519", "贵州茅台"),
    ("002475", "立讯精密"),
    ("000333", "美的集团"),
    ("601318", "中国平安"),
]


DEFAULT_AGENTS = [
    (
        "data_steward",
        "数据管家",
        "数据校验",
        "校验股票、交易日、数据完整性、数据新鲜度。",
        ["行情数据", "数据质量", "数据源日志"],
        ["{{stock_code}}", "{{stock_name}}", "{{quote_snapshot}}", "{{data_quality}}"],
        "你是 A 股投研系统的数据管家，必须检查输入数据的新鲜度、完整性和来源，不得补全不存在的数据。",
        "检查 {{stock_code}} {{stock_name}} 的数据快照，输出可用性、缺失项、异常项和后续 Agent 可使用的数据范围。",
    ),
    (
        "technical",
        "技术面",
        "技术分析",
        "解读 K 线、成交量、均线、MACD、KDJ、RSI、BOLL、ATR。",
        ["行情数据", "K线数据", "技术指标"],
        ["{{stock_code}}", "{{stock_name}}", "{{period}}", "{{quote_snapshot}}", "{{indicators}}"],
        "你是专业 A 股技术面分析师，必须基于输入数据分析趋势、量价、指标和关键风险，不得编造行情。",
        "分析 {{stock_code}} {{stock_name}} 的 {{period}} 技术结构，输出支撑位、压力位、趋势判断和交易观察条件。",
    ),
    (
        "news",
        "新闻",
        "事件解读",
        "解读新闻、公告、快讯、研报观点。",
        ["新闻检索", "公告检索", "研报检索"],
        ["{{stock_code}}", "{{stock_name}}", "{{news_context}}", "{{announcement_context}}"],
        "你是 A 股新闻事件分析师，只能基于给定新闻、公告和研报摘要判断影响，不得把观点当事实。",
        "分析 {{stock_code}} {{stock_name}} 最近事件，区分事实、观点、潜在利好、潜在利空和待验证信息。",
    ),
    (
        "fundamental",
        "基本面",
        "基本面分析",
        "解读财务、估值、盈利质量。",
        ["财务数据", "公告检索"],
        ["{{stock_code}}", "{{stock_name}}", "{{fundamentals}}", "{{financial_statements}}"],
        "你是 A 股基本面分析师，必须基于财务和估值数据分析盈利质量、成长性和估值压力。",
        "分析 {{stock_code}} {{stock_name}} 的基本面，输出收入利润质量、估值水平、财务风险和关键跟踪指标。",
    ),
    (
        "policy_industry",
        "政策行业",
        "政策与行业",
        "解读宏观政策、产业政策、行业景气。",
        ["市场快讯", "宏观指标", "板块数据"],
        ["{{macro_context}}", "{{sector_snapshot}}", "{{policy_news}}"],
        "你是政策与行业分析师，必须区分宏观、产业政策和行业景气数据，避免泛化结论。",
        "分析当前宏观与行业环境，对 {{stock_code}} 所在行业形成景气度、政策方向和风险判断。",
    ),
    (
        "capital_flow",
        "资金",
        "资金行为",
        "解读资金流、北向、龙虎榜、融资融券。",
        ["资金流", "北向资金", "龙虎榜", "融资融券"],
        ["{{fund_flow}}", "{{northbound_flow}}", "{{dragon_tiger}}", "{{margin_trading}}"],
        "你是 A 股资金行为分析师，必须基于资金流、北向、龙虎榜和融资融券数据分析资金行为。",
        "分析 {{stock_code}} {{stock_name}} 的资金行为，输出资金强弱、异常交易、杠杆风险和观察信号。",
    ),
    (
        "bull",
        "多方",
        "看多研究",
        "构建看多逻辑。",
        ["行情数据", "新闻检索", "财务数据", "资金流"],
        ["{{technical_report}}", "{{news_report}}", "{{fundamental_report}}", "{{capital_report}}"],
        "你是多方研究员，只负责提出有证据支持的看多逻辑，同时必须说明证据强弱。",
        "基于前序 Agent 报告，为 {{stock_code}} 构建看多论点，列出关键证据、触发条件和失效条件。",
    ),
    (
        "bear",
        "空方",
        "风险反驳",
        "构建风险和反对逻辑。",
        ["行情数据", "新闻检索", "财务数据", "风险数据"],
        ["{{technical_report}}", "{{news_report}}", "{{fundamental_report}}", "{{capital_report}}"],
        "你是空方研究员，只负责寻找反对买入或降低仓位的证据，必须基于数据和事件。",
        "基于前序 Agent 报告，为 {{stock_code}} 构建风险反驳，列出核心风险、验证方式和回避条件。",
    ),
    (
        "risk",
        "风控",
        "风险审查",
        "审查数据质量、波动、流动性、事件风险。",
        ["数据质量", "行情数据", "风险数据"],
        ["{{data_quality}}", "{{volatility}}", "{{liquidity}}", "{{event_risk}}"],
        "你是风控经理，必须审查数据质量、波动、流动性和事件风险，输出是否允许进入最终结论。",
        "审查 {{stock_code}} 的风险，给出风险等级、仓位约束、止损观察点和禁止交易条件。",
    ),
    (
        "research_director",
        "投研总监",
        "综合结论",
        "形成最终综合结论。",
        ["报告汇总", "引用追踪"],
        ["{{previous_agent_reports}}", "{{risk_review}}", "{{data_references}}"],
        "你是投研总监，必须综合多个 Agent 的证据和风险，形成审慎、可追溯的最终结论。",
        "综合 {{stock_code}} 的全部 Agent 报告，输出结论、适用周期、置信度、关键依据、主要风险和观察指标。",
    ),
]


DEFAULT_OUTPUT_SCHEMA = json.dumps(
    {
        "conclusion": "偏多/中性/偏空/回避",
        "horizon": "日内/短线/波段/中长线",
        "confidence": 0,
        "key_evidence": ["string"],
        "risks": ["string"],
        "watch_items": ["string"],
        "references": ["string"],
    },
    ensure_ascii=False,
)


DEFAULT_AGENT_TOOL_KEYS = {
    "data_steward": ["stock.quote", "data.quality"],
    "technical": ["stock.quote", "stock.bars", "stock.indicators"],
    "news": ["stock.news", "stock.announcements", "stock.research_reports"],
    "fundamental": ["stock.fundamentals", "stock.financial_statements", "stock.announcements"],
    "policy_industry": ["market.macro", "sector.snapshots", "stock.news"],
    "capital_flow": [
        "stock.fund_flow",
        "market.northbound_flow",
        "stock.dragon_tiger",
        "stock.margin_trading",
    ],
    "bull": ["stock.quote", "stock.news", "stock.fundamentals", "stock.fund_flow"],
    "bear": ["stock.quote", "stock.news", "stock.fundamentals", "stock.lockup_expiry"],
    "risk": ["data.quality", "stock.quote", "stock.lockup_expiry", "stock.margin_trading"],
    "research_director": ["document.write", "knowledge.search"],
}


def seed_defaults(db: Session) -> None:
    for item in DEFAULT_PROVIDERS:
        provider = db.scalar(select(DataProvider).where(DataProvider.key == item["key"]))
        if provider:
            continue
        provider = DataProvider(
            key=item["key"],
            name=item["name"],
            type=item["type"],
            enabled=item.get("enabled", True),
            auth_type=item["auth_type"],
            base_url=item["base_url"],
            test_url=item["test_url"],
            cache_ttl_seconds=item["cache_ttl_seconds"],
            rate_limit_json=json.dumps({"min_interval_ms": 1000}, ensure_ascii=False),
        )
        db.add(provider)

    for data_category, tool_name, chain in DEFAULT_ROUTES:
        route = db.scalar(select(DataRoute).where(DataRoute.data_category == data_category))
        if route:
            if (
                data_category == "research_report"
                and route.provider_chain_json == json.dumps(["iwencai"], ensure_ascii=False)
            ):
                route.provider_chain_json = json.dumps(chain, ensure_ascii=False)
                db.add(route)
            continue
        route = DataRoute(
            data_category=data_category,
            tool_name=tool_name,
            provider_chain_json=json.dumps(chain, ensure_ascii=False),
            enabled=True,
            fallback_policy="explicit_chain",
        )
        db.add(route)

    for index, (symbol, name) in enumerate(DEFAULT_WATCHLIST):
        exists = db.scalar(select(DataWatchlistItem).where(DataWatchlistItem.symbol == symbol))
        if exists:
            continue
        db.add(DataWatchlistItem(symbol=symbol, name=name, sort_order=index))

    for key, name, role, description, tools, variables, system_prompt, task_prompt in DEFAULT_AGENTS:
        tool_keys = DEFAULT_AGENT_TOOL_KEYS.get(key, tools)
        agent = db.scalar(select(AgentConfig).where(AgentConfig.key == key))
        if agent:
            try:
                current_tools = json.loads(agent.tools_json) if agent.tools_json else []
            except json.JSONDecodeError:
                current_tools = []
            if not any("." in str(item) for item in current_tools):
                agent.tools_json = json.dumps(tool_keys, ensure_ascii=False)
                db.add(agent)
            continue
        agent = AgentConfig(
            key=key,
            name=name,
            role=role,
            description=description,
            model="deep-research-model",
            temperature=0.2,
            max_tokens=4096,
            enabled=True,
            system_prompt=system_prompt,
            task_prompt=task_prompt,
            output_schema=DEFAULT_OUTPUT_SCHEMA,
            variables_json=json.dumps(variables, ensure_ascii=False),
            tools_json=json.dumps(tool_keys, ensure_ascii=False),
            current_version=1,
        )
        db.add(agent)
        db.add(
            AgentPromptVersion(
                agent_key=key,
                version=1,
                system_prompt=system_prompt,
                task_prompt=task_prompt,
                output_schema=DEFAULT_OUTPUT_SCHEMA,
                variables_json=json.dumps(variables, ensure_ascii=False),
                tools_json=json.dumps(tool_keys, ensure_ascii=False),
                change_note="默认内置版本",
            )
        )

    db.commit()
