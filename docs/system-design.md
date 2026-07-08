# A 股交易智能体系统总体设计

## 1. 产品定位

本项目是一个面向 A 股市场的多 Agent 投研辅助平台，目标是帮助使用者完成数据查看、技术面分析、新闻分析、知识库问答和综合研讨。

系统不直接执行交易，不提供确定性收益承诺，不把模型输出包装成投资建议。所有结论必须展示数据来源、生成时间和主要风险。

本项目不设计用户体系：

- 没有登录、租户、用户权限。
- 所有 Agent、Prompt、数据源、API Key、知识库、任务历史均为全局配置。
- 如果后续需要多人协作，再单独引入用户和权限。

## 2. 参考项目机制

### TradingAgents

可借鉴：

- 多 Agent 投研结构。
- Analyst、Bull/Bear Researcher、Trader、Risk Manager、Portfolio Manager 的流程。
- 工具和数据源路由分层。
- 分析过程可拆成多阶段报告。

不直接照搬：

- 原项目偏研究框架，产品化页面、Prompt 管理、数据源运营能力不足。

### TradingAgents-astock

可借鉴：

- A 股角色扩展：政策、游资、解禁、资金流。
- A 股规则和交易语境：T+1、涨跌停、ST、北向资金、龙虎榜。
- 免费数据源组合。
- 中文 Prompt 和 A 股分析框架。

不直接照搬：

- Streamlit UI 不适合作为复杂前后端产品底座。
- 数据层集中在大文件里，不利于长期维护。
- Agent Prompt 仍然偏代码内置，不能满足前端全量可编辑。

### go-stock

可借鉴：

- 产品级数据采集覆盖面。
- 统一 HTTP 客户端、代理、超时、定时任务。
- 东方财富 K 线 + 新浪 fallback。
- 新闻落库、去重、打标签。
- API Key 状态影响工具可用性。
- 桌面端实时推送和数据页面实践。

不直接照搬：

- 它是 Wails 桌面应用，本项目要求前后端分离。
- 数据采集、UI 事件、Agent 工具有一定耦合，需要拆成独立服务。

## 3. 总体架构

```text
Frontend Web
  - 对话页面
  - 数据分析页面
  - Agent 管理页面
  - 数据源管理页面
  - 知识库管理页面
  - 任务/报告页面

Backend API
  - Chat API
  - Analysis Task API
  - Stock/Data API
  - Agent Config API
  - Data Source API
  - Knowledge Base API
  - Report API
  - SSE/WebSocket Stream API

Worker / Scheduler
  - 数据定时采集
  - 深度分析任务
  - 知识库解析和向量化
  - 报告生成

Agent Engine
  - Workflow 编排
  - Tool 调用
  - Prompt 渲染
  - 多 Agent 研讨
  - 输出结构化校验

Data Service
  - Provider Router
  - Provider Adapters
  - Normalizer
  - Cache
  - Fetch Logs

Storage
  - PostgreSQL
  - Redis
  - Vector DB / pgvector
  - Object Storage / Local Files
```

推荐技术栈：

- 前端：React + TypeScript + Vite/Next.js，ECharts 或 Lightweight Charts。
- 后端：Python FastAPI。
- Agent 编排：LangGraph 或自研状态机。
- 队列：Celery、Dramatiq、RQ 或 Arq。
- 数据库：PostgreSQL，后期可加 TimescaleDB/ClickHouse。
- 缓存：Redis。
- 向量库：pgvector、Qdrant 或 Milvus。

## 4. 核心页面

### 对话页面

用于自然语言提问和查看 Agent 分析过程。

能力：

- 流式对话。
- 显示当前 Agent 阶段。
- 展开中间报告。
- 展示引用数据、新闻、公告、知识库片段。
- 支持追问，例如“让空方继续反驳”。
- 支持从对话生成正式报告。

### 数据分析页面

用于股票和市场数据分析。

模块：

- 股票搜索与基础卡片。
- K 线和技术指标。
- 实时行情。
- 资金流。
- 新闻公告时间线。
- 研报和知识库引用。
- Agent 报告区。
- 历史分析结果对比。

### Agent 管理页面

用于维护所有 Agent 和发送给 Agent 的 Prompt。

能力：

- Agent 列表。
- Agent 名称、描述、模型、温度、最大 token。
- 系统提示词、任务提示词、输出格式可编辑。
- Prompt 变量说明和自动补全。
- Prompt 版本管理、diff、回滚。
- 工具权限配置。
- 单 Agent 测试运行。
- 查看渲染后的 Prompt、工具调用、模型输出、token 消耗。

### 数据源管理页面

用于管理数据源、路由、密钥、健康和日志。

能力：

- 数据源列表和健康状态。
- 数据类别路由，例如 K 线走东财、mootdx、Sina。
- API Key、Token、Cookie、代理、超时、限流配置。
- 健康检查。
- 采集日志。
- 缓存清理。
- 字段映射和解析版本。

### 知识库管理页面

用于维护系统知识和投研资料。

能力：

- 上传 PDF、Word、Markdown、网页链接、纯文本。
- 标签：股票、行业、主题、来源、时间、可信度。
- 文档切分、摘要、向量化。
- 检索测试。
- 启用/禁用文档。
- 查看引用记录。

## 5. Agent 设计

第一版建议内置 Agent：

| Agent | 职责 |
| --- | --- |
| 数据管家 | 校验股票、交易日、数据完整性、数据新鲜度。 |
| 技术面分析师 | 解读 K 线、成交量、均线、MACD、KDJ、RSI、BOLL、ATR。 |
| 新闻分析师 | 解读新闻、公告、快讯、研报观点。 |
| 基本面分析师 | 解读财务、估值、盈利质量。 |
| 政策行业分析师 | 解读宏观政策、产业政策、行业景气。 |
| 资金行为分析师 | 解读资金流、北向、龙虎榜、融资融券。 |
| 多方研究员 | 构建看多逻辑。 |
| 空方研究员 | 构建风险和反对逻辑。 |
| 风控经理 | 审查数据质量、波动、流动性、事件风险。 |
| 投研总监 | 形成最终综合结论。 |

输出建议：

```text
结论：偏多 / 中性 / 偏空 / 回避
适用周期：日内 / 短线 / 波段 / 中长线
置信度：0-100
关键依据：3-5 条
主要风险：3-5 条
关键观察指标：价位、量能、新闻、公告、资金流
数据新鲜度：行情时间、新闻时间、财报期
引用来源：数据快照、新闻、公告、知识库
```

## 6. Agent Workflow

快速分析：

```text
Start
  -> Data Snapshot
  -> Technical Analyst
  -> News Analyst
  -> Final Synthesis
  -> Report Persist
```

标准分析：

```text
Start
  -> Data Manager
  -> Technical / News / Fundamental / Capital Flow Analysts
  -> Final Synthesis
  -> Report Persist
```

深度分析：

```text
Start
  -> Data Manager
  -> Parallel Analysts
  -> Bull Researcher
  -> Bear Researcher
  -> Debate Rounds
  -> Risk Manager
  -> Investment Director
  -> Report Persist
```

所有工作流都必须保存：

- 使用的 Agent 版本。
- 使用的 Prompt 版本。
- 使用的数据快照 ID。
- 工具调用记录。
- 模型输出。
- 结构化解析结果。

## 7. Prompt 管理

Prompt 不能写死在代码里，必须数据库化。

核心表：

```text
agents
agent_prompt_versions
agent_workflows
agent_workflow_nodes
agent_tool_permissions
agent_runs
```

Prompt 支持变量：

```text
{{stock_code}}
{{stock_name}}
{{trade_date}}
{{market_snapshot}}
{{technical_indicators}}
{{news_context}}
{{announcement_context}}
{{knowledge_context}}
{{previous_agent_reports}}
{{user_question}}
{{risk_preference}}
```

系统保留一段全局不可编辑约束：

- 不构成投资建议。
- 不得编造数据。
- 必须说明数据来源和时间。
- 数据缺失时必须显式说明。

## 8. 数据获取模块

详见 [data-acquisition-design.md](./data-acquisition-design.md)。

系统关键原则：

- Agent 只调用工具，不直接访问第三方数据源。
- 数据源 fallback 必须可见。
- 技术指标由程序计算。
- 新闻、公告、研报、知识库都要可引用。
- 数据源管理页面是核心运营能力。

## 9. 知识库设计

知识库类型：

- 通用投研知识库：交易规则、指标解释、估值方法。
- 行业知识库：产业链、景气指标、政策框架。
- 公司知识库：年报、公告、调研纪要、历史事件。
- 策略知识库：全局交易纪律、风控规则、偏好。

RAG 流程：

```text
问题/任务
  -> 意图识别
  -> 股票/行业/时间过滤
  -> 向量检索 + 关键词检索
  -> rerank
  -> 注入 Agent 上下文
  -> 带引用输出
```

## 10. 存储设计

核心配置：

```text
system_settings
agents
agent_prompt_versions
agent_workflows
data_providers
data_routes
knowledge_documents
```

任务与报告：

```text
analysis_tasks
agent_runs
tool_call_logs
analysis_reports
report_references
```

数据：

```text
stocks
daily_bars
minute_bars
quote_snapshots
technical_indicators
news_articles
announcements
research_reports
fund_flow_snapshots
sector_snapshots
raw_data_snapshots
```

## 11. 任务与流式状态

完整分析任务不应同步阻塞 HTTP。

流程：

```text
POST /api/analysis/tasks
  -> 返回 task_id
  -> Worker 执行
  -> SSE/WebSocket 推送状态
  -> 前端展示进度和中间报告
```

任务状态：

```text
pending
fetching_data
running_agents
debating
risk_reviewing
synthesizing
completed
failed
cancelled
```

## 12. 合规和安全

- 默认展示免责声明。
- 最终结论避免“保证上涨”“稳赚”等措辞。
- API Key 加密存储。
- 数据源密钥不在前端明文回显。
- Prompt 可编辑，但工具权限由后端控制。
- 模型输出必须经过结构化校验。
- 报告导出带生成时间和数据版本。

## 13. MVP 范围

第一阶段：

1. 前后端基础架构。
2. 数据源管理页 MVP。
3. Agent 管理页 MVP。
4. 股票搜索、实时行情、K 线、技术指标。
5. 新闻和市场快讯。
6. 知识库上传和检索。
7. 对话页面。
8. 数据分析页面。
9. 快速分析和标准分析工作流。
10. 分析报告落库。

第二阶段：

1. 公告、财务、资金流、板块。
2. Prompt 版本 diff 和回滚。
3. 多空辩论。
4. 风控 Agent。
5. 报告导出 PDF/Markdown。

第三阶段：

1. 龙虎榜、解禁、融资融券。
2. 定时扫描关注池。
3. 策略回测。
4. 组合风险分析。
5. 付费数据源适配。

## 14. 核心取舍

不建议直接 fork 三个参考项目作为底座。推荐吸收它们的机制，重新建设：

```text
前后端分离产品
  + 可配置 Agent 平台
  + 可运营数据源中台
  + RAG 知识库
  + A 股多 Agent 投研工作流
```

这样系统后期才容易维护 Prompt、替换数据源、追踪错误，并让每个分析结论都能回到具体数据和来源。
