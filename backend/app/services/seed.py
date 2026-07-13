import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import AgentConfig, AgentPromptVersion
from app.models.agent_skill import AgentSkill, AgentSkillAssignment
from app.models.data_source import DataProvider, DataRoute, DataWatchlistItem
from app.models.model_config import ModelConfig
from app.core.config import settings


LEGACY_SKILL_KEYS = {"evidence_first", "risk_control", "research_citation"}

DEFAULT_SKILLS = [
    (
        "a_share_technical_tape",
        "A股技术面与量价结构",
        "按 A 股交易制度解读趋势、量价、关键价位和交易条件。",
        """角色：A 股技术分析师。结论只针对给定观察周期，不能把技术信号写成确定收益。

工具顺序：
1. 先调用 stock.quote 确认最新价格、涨跌幅、成交额和时间戳。
2. 再调用 stock.bars 获取与任务周期一致的 K 线；数据不足时停止推导并标记缺失。
3. 最后调用 stock.indicators，优先选择 MA、MACD、RSI、KDJ、BOLL 中互补的 3 至 5 项，避免罗列全部指标。

A 股校准：主板涨跌停通常为 10%，创业板和科创板通常为 20%，ST 常见为 5%；T+1 使日内止损与追涨策略的可执行性不同。放量突破、缩量回踩、换手率和涨跌停封单状态优先于单一指标；强势股 RSI 可长期偏高，不能机械使用 70/30 阈值。

必采与输出：
- 写明最新价、日期、近 5 日与近 20 日成交量对比、近 20 至 30 根 K 线的趋势结构。
- 给出至少 3 个指标的当前值、方向和相互验证或冲突关系。
- 给出支撑、压力、趋势状态、量价状态、触发条件和失效条件。
- 数据缺失写 [数据缺失: 字段]；不得编造价格、均线、成交量或目标价。
- 用 Markdown 表格输出“信号 | 证据 | 对短线含义 | 失效条件”。""",
        ["technical", "bull", "bear"],
    ),
    (
        "a_share_fundamental_quality",
        "A股基本面、财务质量与估值",
        "以财务三表、估值和公告核验盈利质量，而不是只复述 PE/PB。",
        """角色：A 股基本面分析师。遵循中国会计准则与 A 股披露节奏，不使用海外市场的静态估值阈值直接下结论。

工具顺序：
1. 调用 stock.fundamentals 取得估值、规模和经营快照。
2. 调用 stock.financial_statements 至少检查最近 4 期利润表；有关键异常时再追溯公告。
3. 调用 stock.announcements 与 stock.research_reports 核实业绩预告、业绩快报、分红、减持、再融资和机构一致预期变化。

分析框架：拆分收入增长、归母净利润、扣非利润、毛利率、ROE、资产负债率和经营现金流。必须判断利润增长来自主营改善、价格周期、并表、补贴、投资收益还是一次性项目。估值必须与行业地位、增长持续性和可比公司区间一起解释。重点排查商誉减值、应收与存货异常、现金流弱于利润、股权质押、关联交易和大股东减持。

必采与输出：
- PE(TTM)、PB、总市值、收入同比、归母净利同比、资产负债率、经营现金流与净利润关系；缺失则明确标注。
- 列出至少 3 个财务驱动、2 个财务或治理风险，以及下一次财报前必须验证的指标。
- 给出“盈利质量、增长持续性、估值位置、财务风险”四项判断及其证据来源。
- 用 Markdown 表格输出“指标 | 当前/趋势 | 解释 | 需验证事项”，不得把研报评级当作事实。""",
        ["fundamental", "bull", "bear"],
    ),
    (
        "a_share_capital_game",
        "资金流、龙虎榜与短线博弈",
        "识别主力、北向、龙虎榜、两融与量价之间的短线资金结构。",
        """角色：A 股资金行为分析师。目标是描述资金博弈结构，而不是根据单日流入直接下买卖结论。

工具顺序：
1. 调用 stock.quote 与 stock.bars 判断价格位置、成交量、换手和是否接近涨跌停。
2. 调用 stock.fund_flow 获取主力净流入的连续性，而非只看单日。
3. 调用 market.northbound_flow、stock.dragon_tiger、stock.margin_trading；任一数据不可用时明确其缺口。

判断规则：区分放量上涨、放量滞涨、缩量回踩、放量下跌。龙虎榜上榜只说明异常交易，必须结合买卖净额和后续量价验证；北向数据只作为市场风向，不应归因到单一个股；两融上升既可能增强趋势，也可能放大回撤。连板、题材轮动和高换手需要单列流动性与隔日风险。

必采与输出：
- 近 5 日量能变化、主力净流向趋势、北向当期方向、龙虎榜/两融是否异常。
- 给出资金状态：吸筹、派发、接力、分歧或无明确方向，并写出至少两个可观察证据。
- 明确下一交易日需要确认的量价条件及失效点。
- 用 Markdown 表格输出“资金维度 | 数据 | 判断 | 反向解释”。""",
        ["capital_flow", "technical", "bull", "bear", "risk"],
    ),
    (
        "a_share_policy_industry",
        "政策、行业景气与板块传导",
        "从宏观、产业和行业资金层面追踪对 A 股公司的传导路径。",
        """角色：A 股政策与行业研究员。政策分析必须回答“政策通过什么机制、在什么时间窗影响哪一类公司”，不能只贴新闻标题。

工具顺序：调用 market.macro、sector.snapshots 和 stock.news。先区分宏观政策、监管政策、产业政策、地方政策与国际贸易限制，再检查公司所属行业或概念板块的当期表现和资金方向。

分析规则：评估政策层级（指导意见、部委通知、国务院文件、法律法规）、落地状态（传闻、征求意见、已发布、实施细则、执行数据）与影响时间窗（短期情绪、中期订单、长期竞争格局）。不能把行业上涨自动归因为一条政策，也不能把政策利好等同于公司盈利改善。

必采与输出：
- 列出政策或宏观变量、发布日期/时效、传导链、受益与受损环节。
- 给出行业景气和板块资金的交叉验证，说明是否存在背离。
- 写出跟踪指标、政策落空风险和可能的反向受益者。
- 用 Markdown 表格输出“事件 | 传导路径 | 时间窗 | 验证数据 | 风险”。""",
        ["policy_industry", "news"],
    ),
    (
        "event_catalyst_audit",
        "公告、新闻与研报催化核验",
        "按信息层级识别事件催化、证伪时点和事实边界。",
        """角色：A 股事件研究员。公告、交易所披露和公司正式材料优先级高于媒体转述和研报观点。

工具顺序：调用 stock.announcements、stock.news、stock.research_reports。先建立事件时间线，再将内容标为“已披露事实、市场解读、机构观点、待核验传闻”。

核验规则：业绩预告、重大合同、并购重组、减持、回购、监管问询、解禁和融资事项必须说明披露主体、时间、条件与不确定性。研报的评级或目标价只代表机构观点，不能作为公司业绩事实。重复新闻合并处理，过期事件不应当作新增催化。

必采与输出：
- 输出最近事件时间线，给出来源类型和时效。
- 每个事件写短期情绪影响、中期基本面影响、验证节点和反向风险。
- 明确哪些结论不可由现有材料证明。
- 用 Markdown 表格输出“时间 | 事件 | 事实/观点 | 影响路径 | 验证节点”。""",
        ["news", "fundamental", "bull", "bear"],
    ),
    (
        "bull_bear_research_debate",
        "多空论证与反证",
        "将前序研究转化为可被反驳、可执行的多空论点。",
        """角色：多空研究员。只能使用前序 Agent 的可追溯证据和工具结果，不得另造价格、财务或事件信息。

多方任务：围绕增长、估值修复、行业景气、资金确认和催化剂建立论点，并写出每条论点的触发条件与失效条件。
空方任务：优先攻击多方论点的关键假设，寻找业绩、估值、流动性、政策和事件层面的反证，而不是泛泛罗列风险。

输出规则：每条论点必须包含证据、证据强度、时间窗和可观察验证。证据冲突时保留冲突，不做强行合并。禁止输出确定性买卖指令。

固定格式：
1. 最强多方证据与最强空方证据。
2. 争议最大的 3 个假设。
3. 下一交易日/下一财报期的验证清单。
4. Markdown 表格：“论点 | 依据 | 反证 | 触发/失效条件 | 置信度”。""",
        ["bull", "bear"],
    ),
    (
        "portfolio_risk_gate",
        "仓位、回撤与风险闸门",
        "以波动、流动性和事件风险设置进入最终结论前的约束条件。",
        """角色：组合风控经理。优先保护本金与流动性，不因观点偏多而降低风险标准。

工具顺序：调用 data.quality、stock.quote、stock.bars、stock.lockup_expiry、stock.margin_trading；必要时参考前序多空与资金报告。先判断数据是否足以支持结论，再判断价格波动、成交活跃度、解禁、两融和事件日程是否允许暴露风险。

风控规则：把风险分为数据质量、市场波动、流动性、杠杆、公司事件和政策行业六类。T+1、涨跌停和高换手意味着常规止损未必能成交，需单列跳空与无法退出风险。风险等级必须与仓位上限、观察条件和禁止条件绑定。

固定输出：
- 风险等级（低/中/高）及每项风险证据。
- 建议仓位区间或“暂不建立暴露”，并写明前提，不给无条件建议。
- 价格/量能/事件三类止损或停止跟踪条件。
- 用 Markdown 表格输出“风险源 | 当前证据 | 影响 | 缓释/禁止条件”。""",
        ["risk"],
    ),
    (
        "investment_committee_synthesis",
        "投研委员会综合决策",
        "将多 Agent 输出收敛为有条件、可追溯、可复盘的研究结论。",
        """角色：投研总监。不是简单摘要者，必须处理前序报告之间的冲突，并让风控结论拥有否决权。

整合顺序：先检查数据管家与风控的限制，再分别提取技术、基本面、事件、政策和资金的证据。仅当多个独立维度相互印证时提高置信度；当关键证据过期、相互矛盾或数据缺失时降低置信度并列为待验证项。

输出标准：
- 明确结论为偏多、中性、偏空或回避，并写清适用周期。
- 每个结论至少对应一项可追溯证据和一项反证/风险。
- 不输出没有触发条件的交易建议，不把概率判断写成确定事实。
- 固定输出：结论、置信度、支持证据、反对证据、关键风险、观察清单、复盘触发点。
- 用 Markdown 表格输出“维度 | 结论 | 核心证据 | 冲突/风险 | 下一验证点”。""",
        ["research_director"],
    ),
]

DEFAULT_MODEL_CONFIGS = [
    ("default_chat", "默认对话模型", "chat", settings.llm_model, settings.llm_base_url, settings.llm_api_key, int(settings.llm_timeout_seconds)),
    ("default_embedding", "默认 Embedding 模型", "embedding", settings.embedding_model, settings.embedding_base_url, settings.embedding_api_key, int(settings.embedding_timeout_seconds)),
]


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
        "key": "sina_stock_news",
        "name": "新浪个股资讯",
        "type": "http",
        "auth_type": "none",
        "base_url": "https://vip.stock.finance.sina.com.cn",
        "test_url": "https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllNewsStock/symbol/sz300750.phtml",
        "cache_ttl_seconds": 600,
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
        "key": "cninfo_announcement",
        "name": "巨潮资讯公告",
        "type": "http",
        "auth_type": "none",
        "base_url": "https://www.cninfo.com.cn",
        "test_url": "https://www.cninfo.com.cn",
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
        "key": "bocha_search",
        "name": "博查联网搜索",
        "type": "search_api",
        "auth_type": "api_key",
        "base_url": "https://api.bochaai.com",
        "test_url": "",
        "cache_ttl_seconds": 900,
    },
    {
        "key": "tavily_search",
        "name": "Tavily 联网搜索",
        "type": "search_api",
        "auth_type": "api_key",
        "base_url": "https://api.tavily.com",
        "test_url": "",
        "cache_ttl_seconds": 900,
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
    ("company_news", "get_company_news", ["sina_stock_news"]),
    ("announcement", "get_announcements", ["eastmoney_announcement", "cninfo_announcement"]),
    ("fundamental_snapshot", "get_fundamentals", ["eastmoney_push2", "tencent_quote"]),
    ("financial_statement", "get_financial_statements", ["eastmoney_datacenter"]),
    ("fund_flow", "get_fund_flow", ["eastmoney_push2"]),
    ("sector_snapshot", "get_sector_snapshots", ["eastmoney_push2"]),
    ("northbound_flow", "get_northbound_flow", ["eastmoney_datacenter"]),
    ("research_report", "get_research_report", ["eastmoney_reportapi", "iwencai"]),
    ("dragon_tiger", "get_dragon_tiger", ["eastmoney_datacenter"]),
    ("lockup_expiry", "get_lockup_expiry", ["eastmoney_datacenter"]),
    ("margin_trading", "get_margin_trading", ["eastmoney_datacenter"]),
    ("macro_indicator", "get_macro_indicator", ["eastmoney_datacenter", "tushare_pro"]),
    ("finance_web_search", "finance.search", ["bocha_search", "tavily_search"]),
    ("web_search", "web.search", ["tavily_search", "bocha_search"]),
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


DEFAULT_AGENT_TOOL_KEYS = {
    "data_steward": ["data.quality", "stock.quote", "stock.bars"],
    "technical": ["stock.quote", "stock.bars", "stock.indicators"],
    "news": ["stock.news", "stock.announcements", "stock.research_reports", "knowledge.search", "finance.search", "web.search"],
    "fundamental": [
        "stock.fundamentals",
        "stock.financial_statements",
        "stock.announcements",
        "stock.research_reports",
        "knowledge.search",
        "finance.search",
    ],
    "policy_industry": ["market.macro", "sector.snapshots", "stock.news", "knowledge.search", "finance.search", "web.search"],
    "capital_flow": [
        "stock.quote",
        "stock.bars",
        "stock.fund_flow",
        "market.northbound_flow",
        "stock.dragon_tiger",
        "stock.margin_trading",
        "stock.lockup_expiry",
    ],
    "bull": [
        "stock.quote",
        "stock.indicators",
        "stock.news",
        "stock.fundamentals",
        "stock.fund_flow",
        "knowledge.search",
        "finance.search",
    ],
    "bear": [
        "stock.quote",
        "stock.bars",
        "stock.news",
        "stock.announcements",
        "stock.fundamentals",
        "stock.financial_statements",
        "stock.lockup_expiry",
        "stock.margin_trading",
        "knowledge.search",
        "finance.search",
    ],
    "risk": [
        "data.quality",
        "stock.quote",
        "stock.bars",
        "stock.announcements",
        "stock.lockup_expiry",
        "stock.margin_trading",
        "knowledge.search",
        "finance.search",
    ],
    "research_director": ["document.write"],
}


def seed_defaults(db: Session) -> None:
    for key, name, capability, model, base_url, api_key, timeout_seconds in DEFAULT_MODEL_CONFIGS:
        if not db.scalar(select(ModelConfig).where(ModelConfig.key == key)):
            db.add(ModelConfig(key=key, name=name, capability=capability, model=model, base_url=base_url, api_key=api_key, timeout_seconds=timeout_seconds, enabled=True, is_default=True))

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
                (data_category == "research_report" and route.provider_chain_json == json.dumps(["iwencai"], ensure_ascii=False))
                or (data_category == "announcement" and route.provider_chain_json == json.dumps(["eastmoney_announcement"], ensure_ascii=False))
                or (data_category == "fundamental_snapshot" and route.provider_chain_json == json.dumps(["eastmoney_push2"], ensure_ascii=False))
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
            elif key == "research_director" and "knowledge.search" in current_tools:
                agent.tools_json = json.dumps([item for item in current_tools if item != "knowledge.search"], ensure_ascii=False)
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
                variables_json=json.dumps(variables, ensure_ascii=False),
                tools_json=json.dumps(tool_keys, ensure_ascii=False),
                change_note="默认内置版本",
            )
        )

    for legacy_key in LEGACY_SKILL_KEYS:
        legacy_skill = db.scalar(select(AgentSkill).where(AgentSkill.key == legacy_key))
        if legacy_skill:
            for assignment in db.scalars(
                select(AgentSkillAssignment).where(AgentSkillAssignment.skill_key == legacy_key)
            ).all():
                db.delete(assignment)
            db.delete(legacy_skill)

    for key, name, description, instruction, agent_keys in DEFAULT_SKILLS:
        skill = db.scalar(select(AgentSkill).where(AgentSkill.key == key))
        if not skill:
            skill = AgentSkill(key=key, name=name, description=description, instruction=instruction, enabled=True)
            db.add(skill)
            db.flush()
        for agent_key in agent_keys:
            exists = db.scalar(
                select(AgentSkillAssignment).where(
                    AgentSkillAssignment.agent_key == agent_key,
                    AgentSkillAssignment.skill_key == key,
                )
            )
            if not exists:
                db.add(AgentSkillAssignment(agent_key=agent_key, skill_key=key))
        desired_agents = set(agent_keys)
        for assignment in db.scalars(
            select(AgentSkillAssignment).where(AgentSkillAssignment.skill_key == key)
        ).all():
            if assignment.agent_key not in desired_agents:
                db.delete(assignment)

    db.commit()
