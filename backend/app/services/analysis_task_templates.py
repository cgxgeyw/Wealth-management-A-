from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis_task import AnalysisTaskTemplateOverride


@dataclass(frozen=True)
class AnalysisTaskTemplate:
    key: str
    group: str
    group_name: str
    name: str
    description: str
    agent_keys: list[str]
    include_report: bool
    default_prompt: str
    reference: str
    focus: list[str]
    required_output: list[str]

    def merged_read(self, override: AnalysisTaskTemplateOverride | None = None) -> dict[str, Any]:
        agent_keys = self.agent_keys
        if override and override.agent_keys_json:
            try:
                parsed_agent_keys = json.loads(override.agent_keys_json)
            except json.JSONDecodeError:
                parsed_agent_keys = []
            if isinstance(parsed_agent_keys, list) and parsed_agent_keys:
                agent_keys = [str(item) for item in parsed_agent_keys]
        include_report = self.include_report
        if override and override.include_report in {0, 1}:
            include_report = bool(override.include_report)
        return {
            **self.read(),
            "agent_keys": agent_keys,
            "include_report": include_report,
            "default_prompt": override.default_prompt if override and override.default_prompt else self.default_prompt,
            "is_customized": bool(override),
        }

    def mode_protocol(self) -> dict[str, Any]:
        return {
            "reference": self.reference,
            "focus": self.focus,
            "required_output": self.required_output,
        }

    def read(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "group": self.group,
            "group_name": self.group_name,
            "name": self.name,
            "description": self.description,
            "agent_keys": self.agent_keys,
            "include_report": self.include_report,
            "default_prompt": self.default_prompt,
            "reference": self.reference,
            "focus": self.focus,
            "required_output": self.required_output,
        }


def _prompt(*lines: str) -> str:
    return "\n".join(lines)


TASK_TEMPLATES: list[AnalysisTaskTemplate] = [
    AnalysisTaskTemplate(
        key="quick",
        group="stock",
        group_name="个股分析",
        name="快速个股诊断",
        description="数据管家、技术面、新闻、投研总监，适合先看方向。",
        agent_keys=["data_steward", "technical", "news", "research_director"],
        include_report=False,
        reference="TradingAgents analyst-to-manager short path",
        focus=["数据可用性", "技术方向", "近期事件", "核心风险"],
        required_output=["一句话结论", "短线方向", "关键证据", "继续跟踪条件"],
        default_prompt=_prompt(
            "任务：快速个股诊断，参考 TradingAgents 的 market/news 到 manager 短流程。",
            "流程：先校验行情和新闻数据可用性，再判断技术结构和近期事件，最后由投研总监给出方向。",
            "必须覆盖：最新价格状态、近 5 至 20 日趋势、成交量变化、最近新闻/公告、主要风险。",
            "输出：一句话结论、短线方向、关键证据、风险、继续跟踪条件。不得编造未获取的数据。",
        ),
    ),
    AnalysisTaskTemplate(
        key="standard",
        group="stock",
        group_name="个股分析",
        name="标准个股投研",
        description="覆盖技术、新闻、基本面、资金和风控，生成 Markdown 报告。",
        agent_keys=["data_steward", "technical", "news", "fundamental", "capital_flow", "risk", "research_director"],
        include_report=True,
        reference="TradingAgents analyst team -> risk -> research manager",
        focus=["技术面", "新闻公告", "基本面", "资金行为", "风控约束"],
        required_output=["综合结论", "适用周期", "关键证据", "主要风险", "观察指标"],
        default_prompt=_prompt(
            "任务：标准个股投研，参考 TradingAgents 的 analyst team -> risk -> research manager。",
            "流程：数据管家先检查数据新鲜度；技术面分析趋势、量价和指标；新闻分析事实、观点和事件窗口；基本面分析估值、盈利质量和财务风险；资金分析主力、北向、龙虎榜和两融；风控审查流动性、解禁和事件风险；投研总监综合。",
            "必须覆盖：技术信号、新闻/公告影响、财务估值、资金行为、风险约束、观察指标。",
            "输出：Markdown 研究报告，包含结论、适用周期、置信度、关键证据、主要风险、后续观察项。仅供研究，不构成投资建议。",
        ),
    ),
    AnalysisTaskTemplate(
        key="deep",
        group="stock",
        group_name="个股分析",
        name="深度 A 股投研",
        description="加入政策行业、多方、空方和风控审查，适合正式研判。",
        agent_keys=["data_steward", "technical", "news", "fundamental", "policy_industry", "capital_flow", "bull", "bear", "risk", "research_director"],
        include_report=True,
        reference="TradingAgents-astock A股七分析师 -> 多空辩论 -> 风控 -> 最终决策",
        focus=["技术", "事件", "基本面", "政策行业", "资金", "多方论点", "空方论点", "风控"],
        required_output=["分节证据", "多空分歧", "风险审查", "最终倾向", "结论失效条件"],
        default_prompt=_prompt(
            "任务：深度 A 股投研，参考 TradingAgents-astock 的七分析师、质量门控、多空辩论、风控和最终决策框架。",
            "流程：数据管家检查数据质量；技术面、新闻、基本面、政策行业、资金行为分别形成证据；多方只构建有证据支持的看多逻辑；空方只构建反对或降低仓位的证据；风控审查交易约束；投研总监形成最终判断。",
            "A 股约束：纳入涨跌停、T+1、北向资金、换手率、政策市、解禁/减持、两融和龙虎榜影响。",
            "输出：深度 Markdown 报告，包含分析师分节、多方观点、空方观点、风险审查、最终结论、置信度、结论失效条件和跟踪清单。不得把推测写成事实。",
        ),
    ),
    AnalysisTaskTemplate(
        key="technical_focus",
        group="special",
        group_name="专项分析",
        name="技术面专项",
        description="聚焦趋势、量价、指标、支撑压力和交易观察条件。",
        agent_keys=["data_steward", "technical", "capital_flow", "risk"],
        include_report=False,
        reference="TradingAgents-astock market analyst",
        focus=["K线", "成交量", "均线", "MACD", "KDJ", "RSI", "BOLL", "支撑压力"],
        required_output=["技术结论", "关键价位", "触发条件", "失效条件"],
        default_prompt=_prompt(
            "任务：技术面专项，参考 TradingAgents-astock market analyst 的 A 股技术框架。",
            "流程：先取 K 线和指标，再结合资金行为验证量价信号，最后由风控检查波动和可执行性。",
            "必须覆盖：趋势级别、均线结构、MACD/KDJ/RSI/BOLL、成交量与换手、支撑位、压力位、涨跌停和 T+1 对交易计划的影响。",
            "输出：技术结论、关键价位、触发条件、失效条件、风险提醒。",
        ),
    ),
    AnalysisTaskTemplate(
        key="news_event",
        group="special",
        group_name="专项分析",
        name="新闻事件专项",
        description="聚焦新闻、公告、研报和政策事件的事实与影响窗口。",
        agent_keys=["news", "policy_industry", "fundamental", "risk", "research_director"],
        include_report=True,
        reference="TradingAgents news analyst + A股 policy analyst",
        focus=["事实", "观点", "公告", "研报", "政策层级", "影响窗口"],
        required_output=["事件时间线", "影响方向", "证据强弱", "待验证信息"],
        default_prompt=_prompt(
            "任务：新闻事件专项，参考 TradingAgents news analyst 与 A 股政策分析师框架。",
            "流程：新闻 Agent 区分事实、观点和市场传闻；政策行业 Agent 判断政策层级和影响窗口；基本面 Agent 判断事件是否影响收入、利润、估值或现金流；风控 Agent 检查事件风险；投研总监汇总。",
            "必须覆盖：事件来源、发布日期、影响对象、利好/利空方向、短中长期窗口、待验证信息。",
            "输出：事件时间线、影响链条、证据强弱、风险和跟踪事项。",
        ),
    ),
    AnalysisTaskTemplate(
        key="capital_focus",
        group="special",
        group_name="专项分析",
        name="资金行为专项",
        description="聚焦主力资金、北向、龙虎榜、两融和异常交易。",
        agent_keys=["data_steward", "technical", "capital_flow", "risk"],
        include_report=False,
        reference="TradingAgents-astock hot_money_tracker",
        focus=["主力资金", "北向资金", "龙虎榜", "两融", "量价异动"],
        required_output=["资金面判断", "短线信号", "风险", "观察条件"],
        default_prompt=_prompt(
            "任务：资金行为专项，参考 TradingAgents-astock hot_money_tracker。",
            "流程：数据管家校验行情与资金数据；技术面识别量价异动；资金 Agent 分析主力资金、北向、龙虎榜、两融；风控检查追高、流动性和杠杆风险。",
            "必须覆盖：近 5 日成交量变化、主力资金净流入、北向资金、龙虎榜席位/机构参与、两融变化、是否存在游资接力或出货迹象。",
            "输出：资金面总体判断、短线资金信号、风险和观察条件。",
        ),
    ),
    AnalysisTaskTemplate(
        key="policy_sector",
        group="special",
        group_name="专项分析",
        name="政策行业专项",
        description="聚焦宏观政策、产业政策、行业景气和板块轮动。",
        agent_keys=["policy_industry", "news", "capital_flow", "research_director"],
        include_report=True,
        reference="TradingAgents-astock policy analyst",
        focus=["宏观政策", "监管政策", "产业政策", "地方政策", "国际政策", "行业景气"],
        required_output=["政策评级", "行业方向", "传导路径", "风险"],
        default_prompt=_prompt(
            "任务：政策行业专项，参考 TradingAgents-astock policy analyst。",
            "流程：政策行业 Agent 从宏观、监管、产业、地方和国际政策分层；新闻 Agent 补充事件证据；资金 Agent 检查板块资金是否确认；投研总监判断行业影响。",
            "必须覆盖：政策发布方、政策力度、受益/受损链条、影响时间窗口、行业景气、板块轮动和资金确认。",
            "输出：政策评级、行业方向、对目标公司的传导路径、风险和观察指标。",
        ),
    ),
    AnalysisTaskTemplate(
        key="debate",
        group="debate",
        group_name="辩论风控",
        name="多空辩论",
        description="聚焦多方和空方论证，适合检查结论是否过度单边。",
        agent_keys=["technical", "news", "fundamental", "capital_flow", "bull", "bear", "risk", "research_director"],
        include_report=True,
        reference="TradingAgents bull/bear researchers + research manager",
        focus=["看多证据", "看空证据", "关键分歧", "胜负手", "结论失效条件"],
        required_output=["多方论点", "空方论点", "风控意见", "最终倾向"],
        default_prompt=_prompt(
            "任务：多空辩论，参考 TradingAgents bull researcher、bear researcher 和 research manager。",
            "流程：先形成技术、新闻、基本面、资金四类证据；多方只提出看多逻辑和触发条件；空方逐条反驳并提出风险；风控审查双方是否忽略流动性、事件、解禁、两融和数据质量；投研总监裁决。",
            "辩论规则：每个观点必须对应工具结果或明确标注为假设；禁止只给单边结论；必须列出胜负手和结论失效条件。",
            "输出：多方论点、空方论点、关键分歧、风控意见、最终倾向。",
        ),
    ),
    AnalysisTaskTemplate(
        key="risk_review",
        group="debate",
        group_name="辩论风控",
        name="风控审查",
        description="只跑数据质量、事件风险、解禁和两融相关 Agent。",
        agent_keys=["data_steward", "news", "capital_flow", "risk"],
        include_report=False,
        reference="TradingAgents risk debate",
        focus=["数据质量", "流动性", "波动率", "解禁减持", "两融", "事件风险"],
        required_output=["风险等级", "仓位约束", "禁止交易条件", "需补充数据"],
        default_prompt=_prompt(
            "任务：风控审查，参考 TradingAgents 的 aggressive / neutral / conservative risk debate，当前版本先执行保守风控检查。",
            "流程：数据管家检查缺失和新鲜度；新闻 Agent 检查事件风险；资金 Agent 检查资金与杠杆风险；风控 Agent 给出风险等级和约束。",
            "必须覆盖：数据质量、流动性、波动率、解禁/减持、两融、新闻事件、禁止交易条件。",
            "输出：风险等级、仓位约束、止损观察点、禁止交易条件、需要补充的数据。",
        ),
    ),
    AnalysisTaskTemplate(
        key="watchlist_scan",
        group="market",
        group_name="市场扫描",
        name="自选股扫描",
        description="按同一套条件扫描关注池，输出优先级和触发原因。",
        agent_keys=["data_steward", "technical", "news", "capital_flow", "risk", "research_director"],
        include_report=True,
        reference="go-stock stock_analysis scheduled task",
        focus=["候选优先级", "触发原因", "风险过滤", "复查条件"],
        required_output=["优先级", "触发原因", "风险标签", "后续动作"],
        default_prompt=_prompt(
            "任务：自选股扫描，参考 go-stock stock_analysis 定时任务和 TradingAgents 分析师管线。",
            "流程：对关注池按数据质量、技术、新闻、资金和风险维度打分，投研总监给出优先级。",
            "必须覆盖：候选理由、触发条件、风险过滤、需要回避的标的、下一次复查条件。",
            "输出：优先级列表、触发原因、风险标签和后续动作。当前版本如只传入单个代码，则先对该代码输出扫描样式结果。",
        ),
    ),
    AnalysisTaskTemplate(
        key="market_sector",
        group="market",
        group_name="市场扫描",
        name="大盘板块分析",
        description="分析指数环境、板块强弱、资金偏好和市场风险。",
        agent_keys=["policy_industry", "news", "capital_flow", "risk", "research_director"],
        include_report=True,
        reference="go-stock market_analysis + TradingAgents macro/news/risk",
        focus=["大盘状态", "板块强弱", "资金偏好", "政策变量", "风险事件"],
        required_output=["市场温度", "板块方向", "资金方向", "风险提示"],
        default_prompt=_prompt(
            "任务：大盘板块分析，参考 go-stock market_analysis 与 TradingAgents news/macro/risk 管线。",
            "流程：政策行业 Agent 判断宏观和板块环境；新闻 Agent 提取市场事件；资金 Agent 检查北向和板块资金；风控 Agent 判断市场风险；投研总监总结。",
            "必须覆盖：市场状态、主线板块、资金偏好、政策变量、风险事件和明日观察点。",
            "输出：市场温度、板块强弱、资金方向、风险提示和关注清单。",
        ),
    ),
    AnalysisTaskTemplate(
        key="daily_review",
        group="scheduled",
        group_name="定时任务",
        name="每日收盘复盘",
        description="适合后续接入定时任务，生成市场和关注池复盘。",
        agent_keys=["policy_industry", "news", "capital_flow", "risk", "research_director"],
        include_report=True,
        reference="go-stock scheduled review task",
        focus=["收盘复盘", "板块主线", "资金变化", "新闻事件", "明日观察"],
        required_output=["收盘报告", "明日观察点", "风险事件"],
        default_prompt=_prompt(
            "任务：每日收盘复盘，参考 go-stock 定时任务里的 market_analysis / stock_analysis。",
            "流程：收盘后汇总市场、板块、新闻、资金、风险，再生成可归档报告。",
            "必须覆盖：今日市场状态、板块主线、资金变化、重要新闻、风险事件、明日观察点。",
            "输出：收盘复盘报告。当前版本先作为手动长任务运行，后续接入定时任务调度。",
        ),
    ),
]

TASK_TEMPLATES_BY_KEY = {template.key: template for template in TASK_TEMPLATES}


def list_task_templates() -> list[dict[str, Any]]:
    return [template.read() for template in TASK_TEMPLATES]


def list_task_templates_for_db(db: Session) -> list[dict[str, Any]]:
    ensure_task_template_schema(db)
    overrides = db.scalars(select(AnalysisTaskTemplateOverride)).all()
    by_key = {override.template_key: override for override in overrides}
    return [template.merged_read(by_key.get(template.key)) for template in TASK_TEMPLATES]


def get_task_template(key: str) -> AnalysisTaskTemplate | None:
    return TASK_TEMPLATES_BY_KEY.get(key)


def get_task_template_for_db(db: Session, key: str) -> dict[str, Any] | None:
    ensure_task_template_schema(db)
    template = get_task_template(key)
    if not template:
        return None
    override = db.scalar(select(AnalysisTaskTemplateOverride).where(AnalysisTaskTemplateOverride.template_key == key))
    return template.merged_read(override)


def update_task_template_override(
    db: Session,
    key: str,
    default_prompt: str | None = None,
    agent_keys: list[str] | None = None,
    include_report: bool | None = None,
) -> dict[str, Any] | None:
    ensure_task_template_schema(db)
    template = get_task_template(key)
    if not template:
        return None
    override = db.scalar(select(AnalysisTaskTemplateOverride).where(AnalysisTaskTemplateOverride.template_key == key))
    if not override:
        override = AnalysisTaskTemplateOverride(template_key=key)
    if default_prompt is not None:
        override.default_prompt = default_prompt.strip()
    if agent_keys is not None:
        override.agent_keys_json = json.dumps(agent_keys, ensure_ascii=False)
    if include_report is not None:
        override.include_report = 1 if include_report else 0
    db.add(override)
    db.commit()
    db.refresh(override)
    return template.merged_read(override)


def reset_task_template_override(db: Session, key: str) -> dict[str, Any] | None:
    ensure_task_template_schema(db)
    template = get_task_template(key)
    if not template:
        return None
    override = db.scalar(select(AnalysisTaskTemplateOverride).where(AnalysisTaskTemplateOverride.template_key == key))
    if override:
        db.delete(override)
        db.commit()
    return template.merged_read(None)


def ensure_task_template_schema(db: Session) -> None:
    AnalysisTaskTemplateOverride.__table__.create(bind=db.get_bind(), checkfirst=True)


def get_mode_protocol(mode: str) -> dict[str, Any]:
    template = get_task_template(mode)
    if template:
        return template.mode_protocol()
    return {"reference": "generic analysis", "focus": [], "required_output": []}
