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
  createKnowledgeBase,
  deleteKnowledgeDocument,
  fetchAgentRuns,
  fetchAgentVersions,
  fetchAgentTools,
  fetchAgents,
  fetchHealth,
  fetchKnowledgeBases,
  fetchKnowledgeDocument,
  fetchKnowledgeFaissStatus,
  fetchKnowledgeDocuments,
  fetchKnowledgeImportTasks,
  queueKnowledgeDocumentImport,
  reindexAllKnowledgeDocuments,
  reindexKnowledgeDocument,
  rechunkKnowledgeDocument,
  rebuildKnowledgeFaissIndex,
  renderAgentPrompt,
  rollbackAgent,
  runAgentTool,
  searchKnowledge,
  testRunAgent,
  updateAgent,
  updateKnowledgeBase,
  updateKnowledgeChunk,
  type AgentConfig,
  type AgentPromptVersion,
  type AgentRenderResponse,
  type AgentRun,
  type AgentTestRunResponse,
  type AgentToolRunResponse,
  type AgentToolSpec,
  type HealthResponse,
  type KnowledgeBase,
  type KnowledgeChunk,
  type KnowledgeDocument,
  type KnowledgeDocumentDetail,
  type KnowledgeFaissStatus,
  type KnowledgeImportTask,
  type KnowledgeSearchItem
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
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [selectedBaseId, setSelectedBaseId] = useState<number>(1);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [importTasks, setImportTasks] = useState<KnowledgeImportTask[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<KnowledgeDocumentDetail | null>(null);
  const [matches, setMatches] = useState<KnowledgeSearchItem[]>([]);
  const [faissStatus, setFaissStatus] = useState<KnowledgeFaissStatus | null>(null);
  const [docQuery, setDocQuery] = useState("");
  const [newBaseName, setNewBaseName] = useState("");
  const [newBaseDescription, setNewBaseDescription] = useState("");
  const [chunkingStrategy, setChunkingStrategy] = useState("paragraph");
  const [chunkSize, setChunkSize] = useState(900);
  const [chunkOverlap, setChunkOverlap] = useState(120);
  const [separatorsText, setSeparatorsText] = useState("\\n\\n|\\n|。|；");
  const [searchQuery, setSearchQuery] = useState("宁德时代储能业务的增长驱动是什么？");
  const [searchDocTypes, setSearchDocTypes] = useState("");
  const [searchTags, setSearchTags] = useState("");
  const [searchTopK, setSearchTopK] = useState(8);
  const [symbols, setSymbols] = useState("300750");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [message, setMessage] = useState("");
  const [uploadingFiles, setUploadingFiles] = useState(false);
  const [rebuildingFaiss, setRebuildingFaiss] = useState(false);
  const [reindexingAll, setReindexingAll] = useState(false);
  const [savingBaseConfig, setSavingBaseConfig] = useState(false);
  const [rechunkingDocument, setRechunkingDocument] = useState(false);

  const selectedBase = useMemo(
    () => knowledgeBases.find((item) => item.id === selectedBaseId) ?? knowledgeBases[0] ?? null,
    [knowledgeBases, selectedBaseId]
  );

  async function loadKnowledgeBases(nextSelectedId = selectedBaseId) {
    const result = await fetchKnowledgeBases();
    setKnowledgeBases(result.items);
    const selected = result.items.find((item) => item.id === nextSelectedId) ?? result.items[0];
    if (selected) {
      setSelectedBaseId(selected.id);
      setChunkingStrategy(selected.chunking_strategy);
      setChunkSize(selected.chunk_size);
      setChunkOverlap(selected.chunk_overlap);
      setSeparatorsText(selected.separators.map(escapeSeparatorForInput).join("|"));
    }
    return selected;
  }

  async function loadDocuments(query = docQuery, knowledgeBaseId = selectedBaseId) {
    const result = await fetchKnowledgeDocuments(query, 80, knowledgeBaseId);
    setDocuments(result.items);
  }

  async function loadImportTasks(knowledgeBaseId = selectedBaseId) {
    const result = await fetchKnowledgeImportTasks(knowledgeBaseId, 30);
    setImportTasks(result.items);
  }

  async function loadFaissStatus() {
    const result = await fetchKnowledgeFaissStatus();
    setFaissStatus(result);
  }

  useEffect(() => {
    async function bootstrap() {
      const base = await loadKnowledgeBases();
      const baseId = base?.id ?? selectedBaseId;
      await Promise.all([loadDocuments("", baseId), loadImportTasks(baseId), loadFaissStatus()]);
    }
    bootstrap().catch((err: unknown) => {
      setMessage(err instanceof Error ? err.message : "知识库加载失败");
    });
  }, []);

  useEffect(() => {
    const hasRunningTask = importTasks.some((task) => task.status === "queued" || task.status === "processing");
    if (!hasRunningTask) {
      return;
    }
    const timer = window.setInterval(() => {
      loadImportTasks(selectedBaseId)
        .then(() => loadDocuments(docQuery, selectedBaseId))
        .catch((err: unknown) => {
          setMessage(err instanceof Error ? err.message : "导入任务刷新失败");
        });
    }, 2000);
    return () => window.clearInterval(timer);
  }, [docQuery, importTasks, selectedBaseId]);

  async function switchKnowledgeBase(nextBaseId: number) {
    const nextBase = knowledgeBases.find((item) => item.id === nextBaseId);
    setSelectedBaseId(nextBaseId);
    setSelectedDocument(null);
    setDocuments([]);
    if (nextBase) {
      setChunkingStrategy(nextBase.chunking_strategy);
      setChunkSize(nextBase.chunk_size);
      setChunkOverlap(nextBase.chunk_overlap);
      setSeparatorsText(nextBase.separators.map(escapeSeparatorForInput).join("|"));
    }
    await Promise.all([loadDocuments("", nextBaseId), loadImportTasks(nextBaseId)]);
  }

  async function createBase() {
    if (!newBaseName.trim()) {
      setMessage("请输入知识库名称");
      return;
    }
    try {
      const created = await createKnowledgeBase({
        name: newBaseName.trim(),
        description: newBaseDescription.trim(),
        chunking_strategy: chunkingStrategy,
        chunk_size: chunkSize,
        chunk_overlap: chunkOverlap,
        separators: parseSeparators(separatorsText)
      });
      setNewBaseName("");
      setNewBaseDescription("");
      await loadKnowledgeBases(created.id);
      await Promise.all([loadDocuments("", created.id), loadImportTasks(created.id)]);
      setSelectedDocument(null);
      setMessage(`已创建知识库：${created.name}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "知识库创建失败");
    }
  }

  async function saveBaseConfig() {
    if (!selectedBase) {
      setMessage("请先选择知识库");
      return;
    }
    setSavingBaseConfig(true);
    try {
      const updated = await updateKnowledgeBase(selectedBase.id, {
        name: selectedBase.name,
        description: selectedBase.description,
        chunking_strategy: chunkingStrategy,
        chunk_size: chunkSize,
        chunk_overlap: chunkOverlap,
        separators: parseSeparators(separatorsText)
      });
      await loadKnowledgeBases(updated.id);
      setMessage(`已保存知识库配置：${updated.name}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "知识库配置保存失败");
    } finally {
      setSavingBaseConfig(false);
    }
  }

  async function uploadSelectedFiles() {
    if (selectedFiles.length === 0) {
      setMessage("请选择要导入的资料文件");
      return;
    }
    setUploadingFiles(true);
    try {
      const queued: KnowledgeImportTask[] = [];
      for (const file of selectedFiles) {
        queued.push(await queueKnowledgeDocumentImport(file, {
          knowledge_base_id: selectedBaseId,
          chunking_strategy: chunkingStrategy,
          chunk_size: chunkSize,
          chunk_overlap: chunkOverlap,
          separators: parseSeparators(separatorsText)
        }));
      }
      setMessage(`已提交 ${queued.length} 个导入任务，后台正在解析和索引`);
      setSelectedFiles([]);
      await loadDocuments("", selectedBaseId);
      await loadKnowledgeBases(selectedBaseId);
      await loadImportTasks(selectedBaseId);
      await loadFaissStatus();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "文件导入失败");
    } finally {
      setUploadingFiles(false);
    }
  }

  async function rebuildFaissIndex() {
    setRebuildingFaiss(true);
    try {
      const result = await rebuildKnowledgeFaissIndex();
      setFaissStatus(result);
      setMessage(result.message || "FAISS 索引已重建");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "FAISS 索引重建失败");
    } finally {
      setRebuildingFaiss(false);
    }
  }

  async function reindexAllDocuments() {
    setReindexingAll(true);
    try {
      const result = await reindexAllKnowledgeDocuments();
      setFaissStatus(result.faiss);
      setMessage(`全量重建完成：${result.reindexed}/${result.total} 篇，失败 ${result.failed} 篇`);
      await loadDocuments(docQuery, selectedBaseId);
      await loadImportTasks(selectedBaseId);
      if (selectedDocument) {
        setSelectedDocument(await fetchKnowledgeDocument(selectedDocument.id));
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "全量重建失败");
    } finally {
      setReindexingAll(false);
    }
  }

  async function openDocument(documentId: number) {
    try {
      const detail = await fetchKnowledgeDocument(documentId);
      setSelectedDocument(detail);
      setMessage(`已打开：${detail.title}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "文档详情加载失败");
    }
  }

  async function reindexSingleDocument(documentId: number) {
    try {
      const detail = await reindexKnowledgeDocument(documentId);
      setSelectedDocument(detail);
      setMessage(`已重建：${detail.title}，${detail.chunk_count} 个 chunks`);
      await loadDocuments(docQuery, selectedBaseId);
      await loadImportTasks(selectedBaseId);
      await loadFaissStatus();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "文档重建失败");
    }
  }

  async function rechunkSelectedDocument() {
    if (!selectedDocument) {
      setMessage("请先打开一篇文档");
      return;
    }
    setRechunkingDocument(true);
    try {
      const detail = await rechunkKnowledgeDocument(selectedDocument.id, {
        chunking_strategy: chunkingStrategy,
        chunk_size: chunkSize,
        chunk_overlap: chunkOverlap,
        separators: parseSeparators(separatorsText)
      });
      setSelectedDocument(detail);
      setMessage(`已重新切分：${detail.title}，${detail.chunk_count} 个 chunks`);
      await loadDocuments(docQuery, selectedBaseId);
      await loadImportTasks(selectedBaseId);
      await loadFaissStatus();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "文档重新切分失败");
    } finally {
      setRechunkingDocument(false);
    }
  }

  async function removeDocument(documentId: number) {
    try {
      const removed = await deleteKnowledgeDocument(documentId);
      if (selectedDocument?.id === documentId) {
        setSelectedDocument(null);
      }
      setMessage(`已删除：${removed.title}`);
      await loadDocuments(docQuery, selectedBaseId);
      await loadKnowledgeBases(selectedBaseId);
      await loadImportTasks(selectedBaseId);
      await loadFaissStatus();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "文档删除失败");
    }
  }

  async function runKnowledgeSearch() {
    try {
      const result = await searchKnowledge({
        query: searchQuery,
        symbols: splitCsv(symbols),
        doc_types: splitCsv(searchDocTypes),
        tags: splitCsv(searchTags),
        top_k: searchTopK,
        require_citations: true
      });
      setMatches(result.items);
      setMessage(`检索完成：${result.items.length} 条引用片段`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "检索失败");
    }
  }

  async function saveChunk(chunk: KnowledgeChunk, content: string, tagsText: string) {
    try {
      const updated = await updateKnowledgeChunk(chunk.id, {
        content,
        tags: splitCsv(tagsText)
      });
      setSelectedDocument((current) => {
        if (!current) {
          return current;
        }
        return {
          ...current,
          chunks: current.chunks.map((item) => item.id === updated.id ? updated : item)
        };
      });
      setMessage(`已保存 chunk:${updated.id}`);
      await loadFaissStatus();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "分块保存失败");
    }
  }

  return (
    <div className="page-grid knowledge-layout">
      <div className="main-column">
        {message ? <div className="notice">{message}</div> : null}
        <Panel
          title="资料导入"
          description="上传研报、公告、纪要、策略文档等资料，系统自动解析标题、正文、类型和标签并建立索引。"
          actions={<button className="btn btn-primary" disabled={uploadingFiles} onClick={uploadSelectedFiles} type="button">{uploadingFiles ? "导入中..." : "上传并索引"}</button>}
        >
          <div className="form-grid compact">
            <label>目标知识库
              <select className="input" value={selectedBaseId} onChange={(event) => switchKnowledgeBase(Number(event.target.value))}>
                {knowledgeBases.map((item) => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
              </select>
            </label>
            <label>分块方式
              <select className="input" value={chunkingStrategy} onChange={(event) => setChunkingStrategy(event.target.value)}>
                <option value="paragraph">段落窗口</option>
                <option value="characters">字符数</option>
                <option value="separators">特殊符号</option>
              </select>
            </label>
            <label>字符上限
              <input className="input mono" min={100} max={8000} type="number" value={chunkSize} onChange={(event) => setChunkSize(Number(event.target.value) || 900)} />
            </label>
            <label>重叠字符
              <input className="input mono" min={0} max={2000} type="number" value={chunkOverlap} onChange={(event) => setChunkOverlap(Number(event.target.value) || 0)} />
            </label>
          </div>
          <div className="form-stack tight">
            <label>特殊分隔符
              <input className="input mono" value={separatorsText} onChange={(event) => setSeparatorsText(event.target.value)} />
            </label>
            <div className="button-stack inline">
              <button className="btn btn-secondary" disabled={savingBaseConfig} onClick={saveBaseConfig} type="button">
                {savingBaseConfig ? "保存中..." : "保存为知识库默认配置"}
              </button>
              <button className="btn btn-secondary" disabled={!selectedDocument || rechunkingDocument} onClick={rechunkSelectedDocument} type="button">
                {rechunkingDocument ? "切分中..." : "按当前配置重新切分文档"}
              </button>
            </div>
          </div>
          <div className="upload-zone">
            <input
              multiple
              type="file"
              accept=".txt,.md,.csv,.json,.html,.htm,.pdf,.docx,text/*,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={(event) => setSelectedFiles(Array.from(event.target.files ?? []))}
            />
            <div>
              <strong>{selectedFiles.length ? `已选择 ${selectedFiles.length} 个文件` : "选择资料文件"}</strong>
              <span>支持 TXT、Markdown、CSV、JSON、HTML；PDF 和 Word 会走专用解析器。</span>
            </div>
          </div>
          <div className="file-list">
            {selectedFiles.map((file) => (
              <div key={`${file.name}-${file.size}`}>
                <span>{file.name}</span>
                <small className="mono">{Math.ceil(file.size / 1024)} KB</small>
              </div>
            ))}
            {selectedFiles.length === 0 ? <div className="empty-hint">请选择要导入到“{selectedBase?.name ?? "知识库"}”的资料文件</div> : null}
          </div>
        </Panel>

        <Panel
          title="文档库"
          actions={
            <button className="btn btn-secondary" disabled={reindexingAll} onClick={reindexAllDocuments} type="button">
              {reindexingAll ? "重建中..." : "全量重建"}
            </button>
          }
        >
          <div className="toolbar">
            <input className="input" placeholder="搜索标题、标签、来源" value={docQuery} onChange={(event) => setDocQuery(event.target.value)} />
            <button className="btn btn-secondary" onClick={() => loadDocuments(docQuery, selectedBaseId)} type="button">搜索</button>
            <button className="btn btn-secondary" onClick={() => loadDocuments("", selectedBaseId)} type="button">刷新</button>
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>标题</th><th>类型</th><th>分块</th><th>标签</th><th>状态</th><th>Chunks</th><th>操作</th></tr></thead>
              <tbody>
                {documents.map((document) => (
                  <tr key={document.id}>
                    <td>{document.title}</td>
                    <td>{document.doc_type}</td>
                    <td className="mono">{document.chunking_strategy}</td>
                    <td><StatusBadge>{document.tags.join(",") || "未标注"}</StatusBadge></td>
                    <td><StatusBadge tone={document.status === "indexed" ? "green" : "amber"}>{document.status}</StatusBadge></td>
                    <td className="mono">{document.chunk_count}</td>
                    <td>
                      <div className="row-actions">
                        <button className="btn btn-table" onClick={() => setSearchQuery(document.title)} type="button">检索</button>
                        <button className="btn btn-table" onClick={() => openDocument(document.id)} type="button">详情</button>
                        <button className="btn btn-table" onClick={() => reindexSingleDocument(document.id)} type="button">重建</button>
                        <button className="btn btn-table danger" onClick={() => removeDocument(document.id)} type="button">删除</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {documents.length === 0 ? <div className="empty-hint">暂无文档，请先上传文件</div> : null}
          </div>
        </Panel>

        <Panel title="文档详情">
          {selectedDocument ? (
            <div className="document-detail">
              <div className="report-block">
                <div>
                  <span className="label">{selectedDocument.doc_type} · {selectedDocument.source} · {selectedDocument.chunking_strategy}</span>
                  <h3>{selectedDocument.title}</h3>
                  <p>{selectedDocument.summary || "暂无摘要"}</p>
                  <small className="mono">
                    chunk config: {selectedDocument.chunk_size}/{selectedDocument.chunk_overlap} · {selectedDocument.separators.map(escapeSeparatorForInput).join("|")}
                  </small>
                </div>
                <StatusBadge tone={selectedDocument.enabled ? "green" : "amber"}>
                  {selectedDocument.enabled ? "enabled" : "disabled"}
                </StatusBadge>
              </div>
              <div className="reference-list">
                {selectedDocument.symbols.map((item) => <button key={item} type="button">{item}</button>)}
                {selectedDocument.tags.map((item) => <button key={item} type="button">{item}</button>)}
              </div>
              <div className="chunk-list">
                {selectedDocument.chunks.map((chunk) => (
                  <ChunkEditor chunk={chunk} key={chunk.id} onSave={saveChunk} />
                ))}
              </div>
            </div>
          ) : <div className="empty-hint">选择一篇文档查看正文分块和 citation 来源</div>}
        </Panel>
      </div>

      <div className="side-column">
        <Panel title="知识库">
          <div className="knowledge-base-list">
            {knowledgeBases.map((item) => (
              <button
                className={`knowledge-base-row ${item.id === selectedBaseId ? "active" : ""}`}
                key={item.id}
                onClick={() => switchKnowledgeBase(item.id)}
                type="button"
              >
                <strong>{item.name}</strong>
                <span>{item.document_count} docs · {item.chunking_strategy} · {item.chunk_size}/{item.chunk_overlap}</span>
              </button>
            ))}
          </div>
          <div className="form-stack">
            <label>新知识库名称<input className="input" value={newBaseName} onChange={(event) => setNewBaseName(event.target.value)} /></label>
            <label>描述<input className="input" value={newBaseDescription} onChange={(event) => setNewBaseDescription(event.target.value)} /></label>
            <button className="btn btn-primary full" onClick={createBase} type="button">创建知识库</button>
          </div>
        </Panel>
        <Panel
          title="导入任务"
          actions={<button className="btn btn-secondary" onClick={() => loadImportTasks(selectedBaseId)} type="button">刷新</button>}
        >
          <div className="import-task-list">
            {importTasks.map((task) => (
              <button
                className="import-task-row"
                disabled={!task.document_id}
                key={task.id}
                onClick={() => task.document_id ? openDocument(task.document_id) : undefined}
                type="button"
              >
                <div>
                  <strong>{task.filename}</strong>
                  <span>{task.stage} · {task.message}</span>
                </div>
                <StatusBadge tone={task.status === "completed" ? "green" : task.status === "failed" ? "red" : "amber"}>
                  {task.status}
                </StatusBadge>
                <small className="mono">{Math.ceil(task.file_size / 1024)} KB · {task.chunk_count} chunks</small>
              </button>
            ))}
            {importTasks.length === 0 ? <div className="empty-hint">暂无导入任务</div> : null}
          </div>
        </Panel>
        <Panel
          title="向量索引维护"
          description="FAISS 是可选加速层；不可用时会自动回退到 SQLite 向量扫描和 FTS。"
          actions={<button className="btn btn-secondary" onClick={loadFaissStatus} type="button">刷新</button>}
        >
          <div className="metrics-grid">
            <div className="metric">
              <span>运行状态</span>
              <strong>{faissStatus?.enabled ? "已启用" : "未启用"}</strong>
              <small>{faissStatus?.available ? "runtime available" : "optional fallback"}</small>
            </div>
            <div className="metric">
              <span>索引状态</span>
              <strong>{faissStatus?.indexed ? "已构建" : "未构建"}</strong>
              <small>{faissStatus?.vector_count ?? 0} vectors · {faissStatus?.dimension ?? 0} dims</small>
            </div>
          </div>
          <div className="form-stack">
            <label>Embedding 模型<input className="input mono" value={faissStatus?.model ?? ""} readOnly /></label>
            <button className="btn btn-primary full" disabled={rebuildingFaiss} onClick={rebuildFaissIndex} type="button">
              {rebuildingFaiss ? "重建中..." : "重建 FAISS 索引"}
            </button>
            <div className="empty-hint">{faissStatus?.message ?? "加载索引状态中"}</div>
          </div>
        </Panel>

        <Panel title="检索测试">
          <textarea className="textarea" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} />
          <div className="form-grid compact">
            <label>股票代码<input className="input mono" value={symbols} onChange={(event) => setSymbols(event.target.value)} /></label>
            <label>文档类型<input className="input" placeholder="note,research" value={searchDocTypes} onChange={(event) => setSearchDocTypes(event.target.value)} /></label>
            <label>标签<input className="input" placeholder="储能,风控" value={searchTags} onChange={(event) => setSearchTags(event.target.value)} /></label>
            <label>Top K<input className="input mono" min={1} max={50} type="number" value={searchTopK} onChange={(event) => setSearchTopK(Number(event.target.value) || 8)} /></label>
          </div>
          <button className="btn btn-primary full" onClick={runKnowledgeSearch} type="button">运行检索</button>
          <div className="match-list">
            {matches.map((item) => (
              <div className="match" key={item.citation}>
                <StatusBadge tone="green">score {item.score.toFixed(2)}</StatusBadge>
                <p>{item.snippet}</p>
                <small className="mono">{item.citation} · {item.title}</small>
              </div>
            ))}
            {matches.length === 0 ? <div className="empty-hint">检索结果会显示 citation，可被 Agent 引用</div> : null}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function ChunkEditor({
  chunk,
  onSave
}: {
  chunk: KnowledgeChunk;
  onSave: (chunk: KnowledgeChunk, content: string, tagsText: string) => Promise<void>;
}) {
  const [content, setContent] = useState(chunk.content);
  const [tagsText, setTagsText] = useState(chunk.tags.join(","));
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setContent(chunk.content);
    setTagsText(chunk.tags.join(","));
  }, [chunk]);

  async function save() {
    setSaving(true);
    try {
      await onSave(chunk, content, tagsText);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="chunk-item">
      <div className="chunk-head">
        <strong className="mono">chunk:{chunk.id} · #{chunk.chunk_index + 1} · {chunk.token_count} tokens</strong>
        <button className="btn btn-table" disabled={saving} onClick={save} type="button">{saving ? "保存中" : "保存"}</button>
      </div>
      <textarea className="textarea chunk-textarea" value={content} onChange={(event) => setContent(event.target.value)} />
      <label className="chunk-tags">标签
        <input className="input" value={tagsText} onChange={(event) => setTagsText(event.target.value)} />
      </label>
    </div>
  );
}

function splitCsv(value: string): string[] {
  return value.split(/[,，\s]+/).map((item) => item.trim()).filter(Boolean);
}

function parseSeparators(value: string): string[] {
  return value
    .split("|")
    .map((item) => item.replace(/\\n/g, "\n").replace(/\\t/g, "\t"))
    .filter(Boolean);
}

function escapeSeparatorForInput(value: string): string {
  return value.replace(/\n/g, "\\n").replace(/\t/g, "\\t");
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
