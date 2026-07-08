import {
  Activity,
  BarChart3,
  Bot,
  BrainCircuit,
  Database,
  FileText,
  LibraryBig,
  MessageSquareText,
  Settings,
  ShieldCheck,
  SlidersHorizontal
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  createAgentRun,
  fetchAgentRuns,
  fetchAgentVersions,
  fetchAgentTools,
  fetchAgents,
  fetchHealth,
  renderAgentPrompt,
  rollbackAgent,
  runAgentTool,
  testRunAgent,
  updateAgent,
  type AgentConfig,
  type AgentPromptVersion,
  type AgentRenderResponse,
  type AgentRun,
  type AgentTestRunResponse,
  type AgentToolRunResponse,
  type AgentToolSpec,
  type HealthResponse
} from "./api/client";
import { DataAnalysisPage } from "./pages/DataAnalysisPage";
import { DataSourcesPage } from "./pages/DataSourcesPage";

type PageKey =
  | "data_sources"
  | "data_analysis"
  | "chat"
  | "agents"
  | "knowledge_base"
  | "tasks_reports"
  | "settings";

interface NavItem {
  key: PageKey;
  name: string;
  description: string;
  icon: JSX.Element;
}

const navItems: NavItem[] = [
  { key: "data_sources", name: "数据源管理", description: "Provider、路由、缓存与健康检查", icon: <Database size={17} /> },
  { key: "data_analysis", name: "数据分析", description: "行情、K 线、新闻与指标", icon: <BarChart3 size={17} /> },
  { key: "chat", name: "对话分析", description: "多 Agent 投研对话工作台", icon: <MessageSquareText size={17} /> },
  { key: "agents", name: "智能体管理", description: "提示词、工具权限与版本", icon: <Bot size={17} /> },
  { key: "knowledge_base", name: "知识库管理", description: "资料导入、向量化与检索测试", icon: <LibraryBig size={17} /> },
  { key: "tasks_reports", name: "任务与报告", description: "任务队列、研报归档与导出", icon: <FileText size={17} /> },
  { key: "settings", name: "系统设置", description: "模型、缓存、语言与运行参数", icon: <Settings size={17} /> }
];

const pageMeta: Record<PageKey, { title: string; subtitle: string }> = {
  data_sources: {
    title: "数据源管理",
    subtitle: "维护 A 股数据 Provider、调用路由、健康状态和采集日志。"
  },
  data_analysis: {
    title: "数据分析",
    subtitle: "接入真实行情、K 线和市场快讯，作为后续 Agent 分析的输入层。"
  },
  chat: {
    title: "对话分析",
    subtitle: "在同一上下文里查看 Agent 推理进度、证据引用和最终结论。"
  },
  agents: {
    title: "智能体管理",
    subtitle: "前端可编辑所有发送给 Agent 的系统提示词、任务提示词和输出格式。"
  },
  knowledge_base: {
    title: "知识库管理",
    subtitle: "导入投研资料，维护标签、分块、向量索引，并验证检索效果。"
  },
  tasks_reports: {
    title: "任务与报告",
    subtitle: "追踪分析任务生命周期，沉淀可导出的结构化投研报告。"
  },
  settings: {
    title: "系统设置",
    subtitle: "配置本地服务、模型、数据缓存和安全维护项，不包含用户体系。"
  }
};

function StatusBadge({ tone = "neutral", children }: { tone?: string; children: React.ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

function Panel({
  title,
  description,
  actions,
  children,
  className = ""
}: {
  title?: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      {title ? (
        <div className="panel-titlebar">
          <div>
            <h2>{title}</h2>
            {description ? <p>{description}</p> : null}
          </div>
          {actions ? <div className="panel-actions">{actions}</div> : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}

function ChatAnalysisPage() {
  const [symbol, setSymbol] = useState("300750");
  const [query, setQuery] = useState("分析 300750，给我一个 2 周交易视角。");
  const [latestRun, setLatestRun] = useState<AgentRun | null>(null);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [message, setMessage] = useState("");
  const [running, setRunning] = useState(false);

  async function loadRuns() {
    const result = await fetchAgentRuns(8);
    setRuns(result.items);
    setLatestRun((current) => current ?? result.items[0] ?? null);
  }

  useEffect(() => {
    loadRuns().catch((err: unknown) => {
      setMessage(err instanceof Error ? err.message : "运行记录加载失败");
    });
  }, []);

  async function startRun(includeReport = false) {
    setRunning(true);
    setMessage("");
    try {
      const result = await createAgentRun({
        symbol,
        query,
        mode: "analysis",
        period: "daily",
        limit: 60,
        include_report: includeReport
      });
      setLatestRun(result);
      await loadRuns();
      setMessage("Agent 编排完成");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Agent 编排失败");
    } finally {
      setRunning(false);
    }
  }

  const stageNames = latestRun?.result.agent_summaries instanceof Array
    ? latestRun.result.agent_summaries.map((item) => String((item as Record<string, unknown>).agent_name ?? "Agent"))
    : ["数据获取", "技术面", "新闻", "基本面", "资金", "风控", "综合"];
  const confidence = Number(latestRun?.result.confidence ?? 0);

  return (
    <div className="chat-layout">
      <Panel title="会话列表" className="conversation-panel">
        {runs.length === 0 ? <div className="empty-hint">暂无运行记录</div> : null}
        {runs.map((item) => (
          <button className={`conversation ${latestRun?.run_key === item.run_key ? "active" : ""}`} key={item.run_key} onClick={() => setLatestRun(item)} type="button">
            <strong>{item.symbol} {item.mode}</strong>
            <span>{item.status} · {formatDateTime(item.created_at)}</span>
          </button>
        ))}
      </Panel>

      <Panel
        title="投研对话"
        actions={
          <>
            <button className="btn btn-secondary" disabled={running} onClick={() => startRun(false)} type="button">重跑</button>
            <button className="btn btn-secondary" disabled={!latestRun} type="button">导出</button>
            <button className="btn btn-primary" disabled={running} onClick={() => startRun(true)} type="button">生成报告</button>
          </>
        }
      >
        {message ? <div className="notice">{message}</div> : null}
        <div className="stage-strip">
          {stageNames.map((stage, index) => (
            <div className={latestRun ? "stage done" : index === 0 ? "stage active" : "stage"} key={`${stage}-${index}`}>
              <span>{index + 1}</span>
              <strong>{stage}</strong>
            </div>
          ))}
        </div>
        <div className="message-list">
          <div className="msg user">{latestRun?.query || query}</div>
          {latestRun?.steps.map((step) => (
            <div className={step.status === "success" ? "msg agent" : "msg agent muted"} key={`${step.agent_key}-${step.tool_key}`}>
              <strong>{step.agent_name} · {step.tool_key}</strong>
              <p>{step.status === "success" ? String(step.output_preview.summary ?? "已获取数据") : step.error}</p>
            </div>
          ))}
          {!latestRun ? <div className="msg agent muted"><strong>Agent 编排</strong><p>输入标的和问题后，系统会按 Agent 工具权限执行真实工具并生成可追踪结果。</p></div> : null}
        </div>
        <div className="conclusion">
          <div><span className="label">结构化结论</span><strong>{String(latestRun?.result.conclusion ?? "等待运行 Agent 编排")}</strong></div>
          <StatusBadge tone={confidence >= 80 ? "green" : confidence >= 50 ? "amber" : "red"}>置信度 {confidence}%</StatusBadge>
          <p>成功工具 {String(latestRun?.result.tool_success_count ?? 0)} 个，失败工具 {String(latestRun?.result.tool_failed_count ?? 0)} 个。当前结论来自工具编排层，模型研讨层待接入。</p>
        </div>
        <div className="composer">
          <input className="input mono" value={symbol} onChange={(event) => setSymbol(event.target.value)} />
          <input className="input" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="继续追问，例如：请空方 Agent 反驳这个结论" />
          <button className="btn btn-primary" disabled={running} onClick={() => startRun(false)} type="button">{running ? "运行中" : "发送"}</button>
        </div>
      </Panel>

      <Panel title="上下文与引用">
        <div className="kv-list">
          <div><span>股票</span><strong>{latestRun?.symbol ?? symbol}</strong></div>
          <div><span>运行编号</span><strong className="mono">{latestRun?.run_key ?? "未创建"}</strong></div>
          <div><span>状态</span><strong>{latestRun?.status ?? "idle"}</strong></div>
        </div>
        <div className="reference-list">
          {latestRun?.steps.map((step) => (
            <button key={`${step.agent_key}-${step.tool_key}-ref`} type="button">{step.tool_key} · {step.status}</button>
          )) ?? <button type="button">暂无引用</button>}
        </div>
      </Panel>
    </div>
  );
}

function AgentManagementPage() {
  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [selectedKey, setSelectedKey] = useState("");
  const [form, setForm] = useState<AgentConfig | null>(null);
  const [versions, setVersions] = useState<AgentPromptVersion[]>([]);
  const [rendered, setRendered] = useState<AgentRenderResponse | null>(null);
  const [testResult, setTestResult] = useState<AgentTestRunResponse | null>(null);
  const [toolSpecs, setToolSpecs] = useState<AgentToolSpec[]>([]);
  const [toolResult, setToolResult] = useState<AgentToolRunResponse | null>(null);
  const [toolSearch, setToolSearch] = useState("");
  const [testInput, setTestInput] = useState("用 300750 的最新日 K 快照测试提示词输出。");
  const [message, setMessage] = useState("");

  async function loadAgents(nextKey?: string) {
    const result = await fetchAgents();
    setAgents(result.items);
    const key = nextKey || selectedKey || result.items[0]?.key || "";
    setSelectedKey(key);
    const selected = result.items.find((item) => item.key === key) ?? result.items[0] ?? null;
    setForm(selected ? { ...selected } : null);
    if (selected) {
      const versionResult = await fetchAgentVersions(selected.key);
      setVersions(versionResult.items);
    }
  }

  useEffect(() => {
    loadAgents().catch((err: unknown) => {
      setMessage(err instanceof Error ? err.message : "Agent 加载失败");
    });
    fetchAgentTools()
      .then((result) => setToolSpecs(result.items))
      .catch((err: unknown) => {
        setMessage(err instanceof Error ? err.message : "工具注册表加载失败");
      });
  }, []);

  async function selectAgent(key: string) {
    setSelectedKey(key);
    const selected = agents.find((item) => item.key === key) ?? null;
    setForm(selected ? { ...selected } : null);
    setRendered(null);
    setTestResult(null);
    setToolResult(null);
    const versionResult = await fetchAgentVersions(key);
    setVersions(versionResult.items);
  }

  async function saveAgent() {
    if (!form) return;
    try {
      const updated = await updateAgent(form.key, {
        name: form.name,
        role: form.role,
        description: form.description,
        model: form.model,
        temperature: Number(form.temperature),
        max_tokens: Number(form.max_tokens),
        enabled: form.enabled,
        system_prompt: form.system_prompt,
        task_prompt: form.task_prompt,
        output_schema: form.output_schema,
        variables: form.variables,
        tools: form.tools,
        change_note: "前端保存提示词配置"
      });
      setMessage(`已保存 ${updated.name} v${updated.current_version}`);
      await loadAgents(updated.key);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "保存失败");
    }
  }

  async function previewPrompt() {
    if (!form) return;
    const variableValues = Object.fromEntries(form.variables.map((item) => [variableName(item), sampleVariableValue(item)]));
    const result = await renderAgentPrompt(form.key, variableValues);
    setRendered(result);
  }

  async function runTest() {
    if (!form) return;
    const variableValues = Object.fromEntries(form.variables.map((item) => [variableName(item), sampleVariableValue(item)]));
    const result = await testRunAgent(form.key, testInput, variableValues);
    setTestResult(result);
    setRendered(result.rendered_prompt);
  }

  async function rollback(version: number) {
    if (!form) return;
    const updated = await rollbackAgent(form.key, version);
    setMessage(`已回滚并生成 v${updated.current_version}`);
    await loadAgents(updated.key);
  }

  async function runDocumentTool() {
    if (!form) return;
    try {
      const result = await runAgentTool(form.key, "document.write", {
        title: `${form.name} 工具测试报告`,
        topic: "300750",
        summary: "这是从前端 Agent 管理页触发的真实文档编写工具测试。",
        sections: [
          { heading: "工具权限", bullets: [`当前 Agent: ${form.key}`, "已通过后端权限校验"] },
          { heading: "后续规划", bullets: ["知识库检索将接入专业 RAG 系统", "工具执行结果将作为 Agent 上下文引用"] }
        ],
        references: ["agent-tools.registry", "document.write"]
      });
      setToolResult(result);
      setMessage("文档工具执行成功");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "文档工具执行失败");
    }
  }

  function updateTool(tool: string, checked: boolean) {
    if (!form) return;
    const nextTools = checked ? Array.from(new Set([...form.tools, tool])) : form.tools.filter((item) => item !== tool);
    setForm({ ...form, tools: nextTools });
  }

  const selectedAgent = form;
  const legacyTools = agents
    .flatMap((agent) => agent.tools)
    .filter((tool) => !toolSpecs.some((spec) => spec.key === tool));
  const allTools = [
    ...toolSpecs,
    ...Array.from(new Set(legacyTools)).map((tool) => ({
      key: tool,
      name: tool,
      description: "历史工具标签，建议迁移为稳定 tool_key。",
      category: "legacy",
      enabled: false,
      input_schema: {},
      output_schema: {}
    }))
  ];
  const normalizedToolSearch = toolSearch.trim().toLowerCase();
  const visibleTools = normalizedToolSearch
    ? allTools.filter((tool) =>
        `${tool.name} ${tool.key} ${tool.description} ${tool.category}`.toLowerCase().includes(normalizedToolSearch)
      )
    : allTools;

  return (
    <div className="page-grid agent-layout">
      <Panel title="Agent 列表">
        <div className="agent-list">
          {agents.map((agent) => (
            <button className={selectedKey === agent.key ? "agent-row active" : "agent-row"} key={agent.key} onClick={() => selectAgent(agent.key)} type="button">
              <span className="agent-avatar"><BrainCircuit size={15} /></span>
              <strong>{agent.name} Agent</strong>
              <StatusBadge tone={agent.enabled ? "green" : "amber"}>{agent.enabled ? "启用" : "停用"}</StatusBadge>
            </button>
          ))}
        </div>
      </Panel>

      <div className="main-column agent-detail-scroll">
        {message ? <div className="notice">{message}</div> : null}
        <Panel
          title={selectedAgent ? `${selectedAgent.name} Agent` : "Agent 配置"}
          description={selectedAgent?.description ?? "前端可编辑所有实际发送给 Agent 的提示词配置。"}
          actions={
            <>
              <button className="btn btn-secondary" onClick={previewPrompt} type="button">预览变量</button>
              <button className="btn btn-primary" onClick={saveAgent} type="button">保存提示词</button>
            </>
          }
        >
          {form ? (
            <>
              <div className="form-grid">
                <label>名称<input className="input" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
                <label>模型<input className="input" value={form.model} onChange={(event) => setForm({ ...form, model: event.target.value })} /></label>
                <label>Temperature<input className="input mono" type="number" step="0.01" value={form.temperature} onChange={(event) => setForm({ ...form, temperature: Number(event.target.value) })} /></label>
                <label>Max Tokens<input className="input mono" type="number" value={form.max_tokens} onChange={(event) => setForm({ ...form, max_tokens: Number(event.target.value) })} /></label>
                <label>启用状态<select className="input" value={form.enabled ? "enabled" : "disabled"} onChange={(event) => setForm({ ...form, enabled: event.target.value === "enabled" })}><option value="enabled">启用</option><option value="disabled">停用</option></select></label>
                <label>角色<input className="input" value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })} /></label>
              </div>
              <div className="prompt-grid">
                <label>系统提示词<textarea className="textarea" value={form.system_prompt} onChange={(event) => setForm({ ...form, system_prompt: event.target.value })} /></label>
                <label>任务提示词<textarea className="textarea" value={form.task_prompt} onChange={(event) => setForm({ ...form, task_prompt: event.target.value })} /></label>
                <label>输出 Schema<textarea className="textarea mono" value={form.output_schema} onChange={(event) => setForm({ ...form, output_schema: event.target.value })} /></label>
              </div>
              <div className="chip-row">
                {form.variables.map((item) => (
                  <button className="chip-btn" key={item} type="button">{item}</button>
                ))}
              </div>
            </>
          ) : <div className="empty-hint">暂无 Agent 配置</div>}
        </Panel>

        <Panel title="版本与测试">
          <div className="split">
            <div className="version-list">
              {versions.map((version) => (
                <div className="version-row" key={version.id}>
                  <strong>v{version.version} {version.version === selectedAgent?.current_version ? "当前版本" : version.change_note}</strong>
                  <button className="btn btn-secondary" onClick={() => rollback(version.version)} type="button">回滚</button>
                </div>
              ))}
            </div>
            <div className="test-run">
              <textarea className="textarea" value={testInput} onChange={(event) => setTestInput(event.target.value)} />
              <button className="btn btn-primary" onClick={runTest} type="button">运行测试</button>
              {testResult ? <div className="notice">{testResult.output} 估算 token：{testResult.estimated_tokens}</div> : null}
            </div>
          </div>
        </Panel>
        <Panel
          title="真实工具执行"
          description="当前已接入 document.write，后续知识库检索会走专业 RAG 系统。"
          actions={<button className="btn btn-primary" onClick={runDocumentTool} type="button">执行文档工具</button>}
        >
          {toolResult ? (
            <div className="test-run">
              <div className="notice">工具执行成功：{String(toolResult.output.path ?? "")}</div>
              <textarea className="textarea mono" readOnly value={String(toolResult.output.content ?? "")} />
            </div>
          ) : (
            <div className="empty-hint">选择拥有 document.write 权限的 Agent 后可生成 Markdown 报告。</div>
          )}
        </Panel>
        {rendered ? (
          <Panel title="渲染后 Prompt">
            <div className="prompt-grid">
              <label>System<textarea className="textarea" readOnly value={rendered.rendered_system_prompt} /></label>
              <label>Task<textarea className="textarea" readOnly value={rendered.rendered_task_prompt} /></label>
              <label>缺失变量<textarea className="textarea mono" readOnly value={rendered.missing_variables.join("\n") || "无"} /></label>
            </div>
          </Panel>
        ) : null}
      </div>

      <Panel title="工具权限" className="tool-permission-panel">
        <div className="tool-search">
          <input
            className="input"
            placeholder="搜索工具名、tool_key 或描述"
            value={toolSearch}
            onChange={(event) => setToolSearch(event.target.value)}
          />
        </div>
        <div className="permission-list">
          {visibleTools.map((tool) => (
            <label className="check-line" key={tool.key} title={tool.description}>
              <input checked={form?.tools.includes(tool.key) ?? false} onChange={(event) => updateTool(tool.key, event.target.checked)} type="checkbox" />
              <span>{tool.name}</span>
              <small>{tool.key}{tool.enabled ? "" : " · 未接执行器"}</small>
            </label>
          ))}
          {visibleTools.length === 0 ? <div className="empty-hint">没有匹配的工具</div> : null}
        </div>
      </Panel>
    </div>
  );
}

function variableName(value: string): string {
  return value.replace(/[{}]/g, "").trim();
}

function sampleVariableValue(value: string): string {
  const key = variableName(value);
  const samples: Record<string, string> = {
    stock_code: "300750",
    stock_name: "宁德时代",
    period: "daily",
    risk_level: "中",
    quote_snapshot: "最新价 377.48，涨跌幅 0.79%",
    indicators: "MACD 金叉，MA20 附近震荡",
  };
  return samples[key] ?? `[${key}]`;
}

function KnowledgeBasePage() {
  const docs = [
    ["宁德时代 2025 年报", "PDF", "公司财报", "已向量化", "1,248"],
    ["新能源车产业链跟踪", "Markdown", "行业研究", "已向量化", "386"],
    ["储能业务深度报告", "Word", "研报", "处理中", "92"],
    ["监管政策网页摘录", "网页", "政策", "待切分", "0"]
  ];

  return (
    <div className="page-grid knowledge-layout">
      <div className="main-column">
        <Panel
          title="资料导入"
          actions={
            <>
              <button className="btn btn-primary" type="button">上传文件</button>
              <button className="btn btn-secondary" type="button">添加网页链接</button>
              <button className="btn btn-secondary" type="button">粘贴文本</button>
            </>
          }
        >
          <div className="upload-row">
            {["PDF", "Word", "Markdown", "网页链接", "纯文本"].map((item) => (
              <button className="upload-tile" key={item} type="button"><LibraryBig size={18} />{item}</button>
            ))}
          </div>
        </Panel>

        <Panel title="文档库">
          <div className="toolbar">
            <input className="input" placeholder="搜索标题、标签、来源" />
            <button className="btn btn-secondary" type="button">标签筛选</button>
            <button className="btn btn-secondary" type="button">重新向量化</button>
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>标题</th><th>类型</th><th>标签</th><th>状态</th><th>Chunks</th><th>操作</th></tr></thead>
              <tbody>
                {docs.map(([title, type, tag, status, chunks]) => (
                  <tr key={title}>
                    <td>{title}</td>
                    <td>{type}</td>
                    <td><StatusBadge>{tag}</StatusBadge></td>
                    <td><StatusBadge tone={status === "已向量化" ? "green" : "amber"}>{status}</StatusBadge></td>
                    <td className="mono">{chunks}</td>
                    <td><button className="btn btn-table" type="button">查看</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>

      <Panel title="检索测试">
        <textarea className="textarea" defaultValue="宁德时代储能业务的增长驱动是什么？" />
        <button className="btn btn-primary full" type="button">运行检索</button>
        <div className="match-list">
          {["储能系统出货同比提升，海外大客户订单贡献主要增量。", "毛利率改善来自原材料成本下降与产品结构优化。", "风险集中在海外政策、汇率与交付节奏。"].map((text, index) => (
            <div className="match" key={text}>
              <StatusBadge tone="green">相似度 {(0.86 - index * 0.05).toFixed(2)}</StatusBadge>
              <p>{text}</p>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function TasksReportsPage() {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<AgentRun | null>(null);
  const [message, setMessage] = useState("");

  async function loadRuns() {
    const result = await fetchAgentRuns(30);
    setRuns(result.items);
    setSelectedRun((current) => current ?? result.items[0] ?? null);
  }

  useEffect(() => {
    loadRuns().catch((err: unknown) => {
      setMessage(err instanceof Error ? err.message : "任务加载失败");
    });
  }, []);

  return (
    <div className="page-grid reports-layout">
      <div className="main-column">
        {message ? <div className="notice">{message}</div> : null}
        <Panel title="任务队列" actions={<button className="btn btn-primary" onClick={loadRuns} type="button">刷新</button>}>
          <div className="table-wrap">
            <table>
              <thead><tr><th>ID</th><th>标的</th><th>模式</th><th>状态</th><th>创建时间</th><th>步骤</th><th>快照</th></tr></thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.run_key}>
                    <td className="mono">{run.run_key}</td>
                    <td>{run.symbol}</td>
                    <td>{run.mode}</td>
                    <td><StatusBadge tone={run.status === "completed" ? "green" : run.status === "partial" ? "amber" : "red"}>{run.status}</StatusBadge></td>
                    <td>{formatDateTime(run.created_at)}</td>
                    <td className="mono">{run.steps.length}</td>
                    <td><button className="btn btn-table" onClick={() => setSelectedRun(run)} type="button">打开</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {runs.length === 0 ? <div className="empty-hint">暂无 Agent 运行记录</div> : null}
          </div>
        </Panel>

        <Panel title="报告详情">
          {selectedRun ? (
            <>
              <div className="report-block">
                <div>
                  <span className="label">最终结论</span>
                  <h3>{selectedRun.symbol}：{String(selectedRun.result.conclusion ?? "工具编排完成")}</h3>
                  <p>成功工具 {String(selectedRun.result.tool_success_count ?? 0)} 个，失败工具 {String(selectedRun.result.tool_failed_count ?? 0)} 个。运行编号 {selectedRun.run_key}。</p>
                </div>
                <StatusBadge tone={Number(selectedRun.result.confidence ?? 0) >= 80 ? "green" : "amber"}>置信度 {String(selectedRun.result.confidence ?? 0)}%</StatusBadge>
              </div>
              <div className="reference-list">
                {selectedRun.steps.map((step) => (
                  <button key={`${selectedRun.run_key}-${step.agent_key}-${step.tool_key}`} type="button">
                    {step.agent_name} · {step.tool_key} · {step.status}
                  </button>
                ))}
              </div>
            </>
          ) : <div className="empty-hint">选择一个运行记录查看详情</div>}
        </Panel>
      </div>

      <Panel title="报告归档">
        {runs.slice(0, 8).map((item) => (
          <div className="archive-row" key={item.run_key}>
            <strong>{item.symbol} {item.mode}</strong>
            <span>{formatDateTime(item.created_at)} · {item.status}</span>
            <div>
              <button className="btn btn-secondary" type="button">Markdown</button>
              <button className="btn btn-secondary" type="button">PDF</button>
            </div>
          </div>
        ))}
        {runs.length === 0 ? <div className="empty-hint">生成报告后会出现在这里</div> : null}
      </Panel>
    </div>
  );
}

function formatDateTime(value: string): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function SettingsPage() {
  return (
    <div className="settings-grid">
      <Panel title="基础设置">
        <div className="form-grid two">
          <label>应用名称<input className="input" defaultValue="A 股交易智能体" /></label>
          <label>运行环境<input className="input" defaultValue="local-desktop" /></label>
          <label>语言<select className="input" defaultValue="zh-CN"><option value="zh-CN">简体中文</option></select></label>
          <label>时区<input className="input" defaultValue="Asia/Shanghai" /></label>
        </div>
      </Panel>

      <Panel title="模型设置">
        <div className="form-grid two">
          <label>快速模型<input className="input" defaultValue="fast-chat-model" /></label>
          <label>深度模型<input className="input" defaultValue="deep-research-model" /></label>
          <label>API Base<input className="input mono" defaultValue="https://api.example.com/v1" /></label>
          <label>API Key 状态<input className="input" defaultValue="已配置，本地加密保存" /></label>
        </div>
      </Panel>

      <Panel title="数据设置">
        <div className="settings-list">
          <label className="check-line"><input defaultChecked type="checkbox" /><span>启动时自动健康检查数据源</span></label>
          <label className="check-line"><input defaultChecked type="checkbox" /><span>启用本地缓存和失败回退</span></label>
          <label className="check-line"><input type="checkbox" /><span>强制实时行情绕过缓存</span></label>
        </div>
        <div className="button-stack inline">
          <button className="btn btn-secondary" type="button">清理缓存</button>
          <button className="btn btn-secondary" type="button">清理日志</button>
          <button className="btn btn-primary" type="button">保存设置</button>
        </div>
      </Panel>

      <Panel title="安全与维护">
        <div className="security-row">
          <ShieldCheck size={22} />
          <div>
            <strong>本地密钥加密已启用</strong>
            <span>不包含用户、角色或权限管理，仅维护本机运行配置。</span>
          </div>
        </div>
      </Panel>
    </div>
  );
}

function renderPage(activePage: PageKey) {
  switch (activePage) {
    case "data_sources":
      return <DataSourcesPage />;
    case "data_analysis":
      return <DataAnalysisPage />;
    case "chat":
      return <ChatAnalysisPage />;
    case "agents":
      return <AgentManagementPage />;
    case "knowledge_base":
      return <KnowledgeBasePage />;
    case "tasks_reports":
      return <TasksReportsPage />;
    case "settings":
      return <SettingsPage />;
  }
}

export function App() {
  const [activePage, setActivePage] = useState<PageKey>("data_sources");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "后端服务连接失败");
      });
  }, []);

  const activeMeta = useMemo(() => pageMeta[activePage], [activePage]);

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Activity size={18} /></div>
          <div>
            <strong>A 股交易智能体</strong>
            <span>Research Console</span>
          </div>
        </div>
        <nav className="nav-list">
          {navItems.map((item) => (
            <button
              className={activePage === item.key ? "nav-item active" : "nav-item"}
              key={item.key}
              onClick={() => setActivePage(item.key)}
              title={item.description}
              type="button"
            >
              {item.icon}
              <span>{item.name}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <SlidersHorizontal size={15} />
          <span>前后端分离 · 本地服务</span>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>{activeMeta.title}</h1>
            <p>{activeMeta.subtitle}</p>
          </div>
          <div className="topbar-actions">
            <StatusBadge tone={health ? "green" : error ? "red" : "amber"}>
              {health ? "后端在线" : error ? "后端异常" : "检查中"}
            </StatusBadge>
            <span className="topbar-meta">{health?.environment ?? "local"} · {health?.app_name ?? "Ashare Agent"}</span>
          </div>
        </header>
        {error ? <div className="notice error">{error}</div> : null}
        {renderPage(activePage)}
      </section>
    </main>
  );
}
