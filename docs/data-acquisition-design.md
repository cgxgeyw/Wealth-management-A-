# A 股交易智能体数据获取模块设计

## 1. 模块目标

数据获取模块负责为投研智能体、对话页面、数据分析页面和知识库流程提供统一、可追溯、可维护的 A 股数据。

核心目标：

- 支持行情、K 线、技术指标、新闻、公告、财务、研报、资金流、板块、龙虎榜、解禁、融资融券等数据。
- Agent 不直接访问第三方接口，只能调用内部工具或数据服务。
- 每条数据都保留来源、抓取时间、市场时间、缓存状态、解析版本和异常信息。
- 支持主备数据源、显式 fallback、健康检查、限流、缓存、手动刷新。
- 为最终分析报告提供可追溯证据链。

本项目不设计用户体系，所有数据源配置、密钥、缓存、任务和知识库均为全局配置。

## 2. 参考项目结论

### TradingAgents

原版 TradingAgents 的核心价值在于 provider routing：

- 工具按类别划分，例如行情、技术指标、基本面、新闻、宏观数据。
- Agent 调用工具，工具通过 `route_to_vendor` 路由到具体 vendor。
- 新版强调显式 vendor chain，不静默切到用户未配置的数据源。

可借鉴点：

- 数据类别和工具分层。
- 主备数据源链路显式配置。
- 数据源错误要暴露给 Agent，避免 Agent 编造。

### TradingAgents-astock

A 股版重点提供了免费数据源组合：

- `mootdx`：通达信 TCP，K 线、财务快照、F10。
- 腾讯财经：实时行情、PE/PB、市值、换手率。
- 东方财富：资金流、龙虎榜、解禁、板块、个股新闻。
- 新浪财经：K 线 fallback、新闻、财务数据。
- 同花顺：一致预期、热点、北向资金。
- 财联社：财经快讯。
- 百度股市通：概念板块。

可借鉴点：

- A 股数据源组合。
- 东方财富统一限流。
- K 线主备源补齐。
- 北向资金历史数据自建本地缓存。
- A 股特色信号层：龙虎榜、解禁、资金流、板块。

### go-stock

go-stock 更偏产品级桌面应用，数据覆盖和调度更丰富：

- 统一 HTTP 客户端，支持连接池、代理、超时配置。
- K 线优先东方财富 `push2his`，失败 fallback 新浪。
- K 线返回实际使用的数据源。
- 新浪 K 线会补“今日实时 K 线”，改善图表新鲜度。
- 财联社、新浪、TradingView 新闻定时拉取、落库、去重、打标签。
- 定时任务刷新股票价格、新闻、市场统计、板块资金流、概念资金流。
- Agent 工具按 API Key 配置状态动态启用或禁用。

可借鉴点：

- 数据源管理页要展示健康、日志、路由、密钥和缓存。
- K 线响应必须带 `source`。
- API Key 状态应影响工具可用性。
- 调度任务应该独立于页面，但可以把进度推给前端。

## 3. 总体架构

```text
Frontend
  -> Backend API
    -> Data Service
      -> Data Router
        -> Provider Adapters
          -> Eastmoney / Sina / Tencent / mootdx / Tonghuashun / CLS / Baidu / Tushare optional
      -> Normalizer
      -> Cache
      -> Database
      -> Fetch Log
    -> Agent Tools
      -> Data Service
```

调用规则：

```text
Agent -> Tool -> Data Service -> Data Router -> Provider Adapter
```

前端、Agent、任务调度都不直接访问第三方数据源。

## 4. 数据源优先级

| 数据类型 | 主源 | 备源 | 说明 |
| --- | --- | --- | --- |
| 股票搜索/基础信息 | 本地股票表 + 东方财富 | Tushare 可选 | 股票基础表每日同步，本地优先。 |
| 实时行情 | 腾讯财经 | 东方财富 push2 | 腾讯简单稳定，东财作为 fallback。 |
| 日 K/周 K/月 K | 东方财富 push2his / mootdx | 新浪财经 | 东财周期和分页能力强，mootdx 稳定，新浪兜底。 |
| 分钟 K | 东方财富 push2his | 新浪财经 | 优先满足数据分析页图表。 |
| 今日合成 K 线 | 实时行情 + 当日分时 | 新浪行情 | 用于日 K 未更新时的图表展示。 |
| 技术指标 | 内部计算 | 无 | 基于标准化 OHLCV 计算，不让 LLM 算。 |
| 财务快照 | 腾讯财经 + 东方财富 F10 | mootdx | 估值、ROE、营收、利润等。 |
| 财务三表 | 新浪财经 / 东方财富 F10 | Tushare 可选 | 第一版以稳定免费源为主。 |
| 公司新闻 | 东方财富 | 新浪财经 | 新闻要去重、记录 URL 和发布时间。 |
| 市场快讯 | 财联社 | 东方财富 7x24 / 新浪 | 政策、宏观、行业事件。 |
| 公告 | 东方财富公告 | 巨潮资讯 | 高优先级数据，应保留原文链接。 |
| 研报 | 东方财富 reportapi | 同花顺问财 | 只作为观点参考，不作为事实源。 |
| 个股资金流 | 东方财富 push2/push2his | 百度股市通 | 主力、大单、中单、小单。 |
| 板块资金流 | 东方财富 | 无 | 用于行业/概念轮动分析。 |
| 概念资金流 | 东方财富 | 百度股市通 | 用于主题分析。 |
| 北向资金 | 同花顺实时 | 本地历史缓存 | 历史源可能断供，需自缓存。 |
| 龙虎榜 | 东方财富 datacenter | 无 | 游资和机构席位。 |
| 限售解禁 | 东方财富 datacenter | 无 | 供给压力。 |
| 融资融券 | 东方财富 datacenter | 无 | 风险和杠杆信号。 |
| 宏观指标 | 东方财富 datacenter | Tushare 可选 | GDP、CPI、PPI、PMI 等。 |

## 5. 数据路由设计

数据源路由按“数据类别 + 工具”配置，而不是简单开关某个 provider。

示例：

```json
{
  "daily_kline": ["eastmoney_push2his", "mootdx", "sina_kline"],
  "realtime_quote": ["tencent_quote", "eastmoney_push2"],
  "company_news": ["eastmoney_news", "sina_news"],
  "market_news": ["cls", "eastmoney_7x24", "sina_news"],
  "announcement": ["eastmoney_notice", "cninfo"],
  "research_report": ["eastmoney_reportapi", "iwencai_search"],
  "fund_flow": ["eastmoney_fund_flow"],
  "northbound_flow": ["ths_hsgt", "local_cache"]
}
```

路由原则：

- 显式 provider chain，禁止静默切到未配置数据源。
- 核心行情失败时任务应进入 degraded 或 failed 状态。
- 新闻、研报、板块等增强数据失败时，可以返回 `DATA_UNAVAILABLE` 并继续分析。
- 每次 fallback 都要记录在日志和响应 envelope 中。

## 6. 统一数据响应

所有数据服务返回统一 envelope：

```json
{
  "ok": true,
  "data_type": "daily_kline",
  "symbol": "300750",
  "market": "A_SHARE",
  "source": "eastmoney_push2his",
  "fallback_sources": ["sina_kline"],
  "fetched_at": "2026-07-07T10:30:00+08:00",
  "market_time": "2026-07-07",
  "freshness": "fresh",
  "cache_hit": false,
  "parser_version": "eastmoney_kline_v1",
  "confidence": 0.92,
  "warnings": [],
  "data": []
}
```

`freshness` 枚举：

- `fresh`：数据符合预期最新时间。
- `stale`：数据源返回旧数据。
- `partial`：数据不完整。
- `closed_market`：市场休市，使用最近交易日数据。
- `synthetic`：由实时行情合成。
- `unavailable`：无可用数据。

## 7. 缓存策略

TTL 是缓存有效期，即一份缓存数据多久以内可以复用。

建议 TTL：

| 数据 | 交易中 TTL | 收盘后 TTL |
| --- | --- | --- |
| 实时行情 | 5-15 秒 | 1-5 分钟 |
| 分钟 K | 30-60 秒 | 到下个交易日 |
| 日 K | 1-5 分钟 | 到下个交易日 |
| 技术指标 | 跟随 K 线 | 跟随 K 线 |
| 公司新闻 | 5-15 分钟 | 30-60 分钟 |
| 市场快讯 | 1-5 分钟 | 10-30 分钟 |
| 公告 | 30-60 分钟 | 6-24 小时 |
| 财务报表 | 1 天 | 1-7 天 |
| 研报 | 6-24 小时 | 6-24 小时 |
| 龙虎榜 | 1 天 | 1 天 |
| 解禁 | 1 天 | 1 天 |
| 股票基础信息 | 1 天 | 1 天 |

缓存层：

- 进程内缓存：交易日历、数据源配置、字段映射。
- Redis：实时行情、快讯、任务快照、短 TTL 数据。
- PostgreSQL：标准化历史数据、采集日志、报告引用。
- 对象存储/本地文件：原始响应、公告 PDF、研报快照。

## 8. 定时任务

调度服务独立于 Backend API。

建议任务：

| 任务 | 频率 | 说明 |
| --- | --- | --- |
| 股票基础信息同步 | 每日 02:00 | 更新股票名称、行业、状态。 |
| 日 K 补齐 | 每日收盘后 | 补齐关注池和热门股票。 |
| 实时行情刷新 | 交易中 5-30 秒 | 仅刷新关注池、页面活跃股票和任务股票。 |
| 市场快讯 | 交易中 1-5 分钟 | 财联社、东财 7x24。 |
| 公司公告 | 5-30 分钟 | 开盘前、午间、收盘后更频繁。 |
| 板块资金流 | 交易中 1 分钟 | 支撑板块页面。 |
| 概念资金流 | 交易中 1 分钟 | 支撑主题分析。 |
| 北向资金快照 | 交易中 1-5 分钟 | 当日实时 + 收盘保存。 |
| 龙虎榜 | 收盘后 | 每日一次。 |
| 数据源健康检查 | 5-30 分钟 | 写入健康状态。 |

## 9. 数据源管理页面

页面包括：

- `Overview`：整体健康、最近失败、数据新鲜度。
- `Providers`：数据源启用、类型、用途、状态、平均耗时。
- `Routes`：每类数据的主备源链路。
- `Credentials`：API Key、Token、Cookie、代理配置。
- `Health Checks`：用指定股票测试接口。
- `Fetch Logs`：采集日志、错误、fallback、缓存命中。
- `Cache`：查看命中率、清理缓存、强制刷新。
- `Parser Mappings`：字段映射和解析版本。

状态枚举：

```text
healthy
degraded
rate_limited
auth_required
auth_failed
stale
schema_changed
disabled
unavailable
```

## 10. 数据库表

```text
data_providers
  id
  key
  name
  type
  enabled
  auth_type
  base_url
  config_json
  rate_limit_json
  cache_ttl_seconds
  health_status
  last_success_at
  last_failure_at
  created_at
  updated_at

data_provider_credentials
  id
  provider_id
  credential_type
  encrypted_value
  last_verified_at
  verification_status

data_routes
  id
  data_category
  tool_name
  provider_chain_json
  enabled
  fallback_policy
  created_at
  updated_at

data_fetch_logs
  id
  provider_key
  data_category
  tool_name
  symbol
  status
  http_status
  latency_ms
  cache_hit
  fallback_used
  error_type
  error_message
  fetched_at

data_parser_versions
  id
  provider_key
  data_type
  parser_version
  field_mapping_json
  enabled
  created_at
```

业务数据表：

```text
stocks
trading_calendar
daily_bars
minute_bars
quote_snapshots
technical_indicators
fundamental_snapshots
financial_statements
news_articles
announcements
research_reports
fund_flow_snapshots
northbound_flow_snapshots
dragon_tiger_records
lockup_expiry_events
margin_trading_records
sector_memberships
sector_snapshots
raw_data_snapshots
```

## 11. API 设计

```text
GET  /api/stocks/search?q=
GET  /api/stocks/{code}/profile
GET  /api/stocks/{code}/quote
GET  /api/stocks/{code}/bars?period=1d&start=&end=
GET  /api/stocks/{code}/indicators?names=macd,rsi,boll
GET  /api/stocks/{code}/fundamentals
GET  /api/stocks/{code}/financial-statements
GET  /api/stocks/{code}/news
GET  /api/stocks/{code}/announcements
GET  /api/stocks/{code}/research-reports
GET  /api/stocks/{code}/fund-flow
GET  /api/stocks/{code}/dragon-tiger
GET  /api/stocks/{code}/lockup-expiry
GET  /api/stocks/{code}/margin-trading
GET  /api/market/news
GET  /api/market/northbound-flow
GET  /api/sectors/snapshots
POST /api/data/refresh
GET  /api/data/providers
GET  /api/data/routes
GET  /api/data/fetch-logs
POST /api/data/health-check
POST /api/data/cache/clear
```

Agent 工具可以使用内部 service，不一定暴露为公网 HTTP，但必须复用同一套数据响应结构。

## 12. MVP 顺序

第一阶段：

1. 数据源管理页 MVP：providers、routes、credentials、health check、fetch logs。
2. 股票搜索和基础信息。
3. 实时行情。
4. K 线：东方财富/mootdx + 新浪 fallback。
5. 技术指标计算。
6. 公司新闻和市场快讯。
7. 任务级数据快照。

第二阶段：

1. 公告。
2. 财务快照和财务三表。
3. 资金流。
4. 板块/概念。
5. 北向资金。
6. 研报。

第三阶段：

1. 龙虎榜。
2. 解禁。
3. 融资融券。
4. 宏观指标。
5. 付费数据源适配器。
6. 数据质量评分和异常告警。

## 13. 关键原则

- 数据事实和观点数据分开。行情、公告、财报属于事实；研报、AI 点评属于观点。
- LLM 不计算指标，只解释由程序计算好的指标。
- 数据源 fallback 必须可见。
- 原始响应要能追溯。
- 字段映射要版本化。
- 免费源容易变，数据源管理页不是附属功能，而是系统稳定性的核心。
