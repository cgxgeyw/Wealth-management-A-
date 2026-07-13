import {
  Activity,
  BarChart3,
  Bot,
  BrainCircuit,
  CalendarClock,
  ChevronLeft,
  ChevronRight,
  Database,
  FileText,
  History,
  LibraryBig,
  MessageSquareText,
  Play,
  Plus,
  Puzzle,
  Save,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Trash2,
  Upload,
  Wrench,
  X
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  analysisTaskReportDownloadUrl,
  analysisTaskEventsUrl,
  clearFinishedAnalysisTasks,
  createAnalysisTask,
  createModelConfig,
  deleteAgentVersion,
  deleteKnowledgeBase,
  deleteModelConfig,
  createKnowledgeBase,
  deleteAnalysisTask,
  deleteKnowledgeDocument,
  fetchAnalysisTask,
  fetchAnalysisTaskExecution,
  fetchAnalysisTaskReport,
  fetchAnalysisTasks,
  fetchAnalysisTaskTemplates,
  fetchAgentRun,
  fetchAgentVersions,
  fetchAgentTools,
  fetchAgents,
  fetchDataSnapshot,
  fetchHealth,
  fetchKnowledgeBases,
  fetchKnowledgeDocument,
  fetchKnowledgeFaissStatus,
  fetchKnowledgeDocuments,
  fetchKnowledgeImportTasks,
  fetchModelConfigs,
  fetchPremarketRecommendations,
  fetchScheduledTasks,
  queueKnowledgeDocumentImport,
  reindexAllKnowledgeDocuments,
  reindexKnowledgeDocument,
  rechunkKnowledgeDocument,
  rebuildKnowledgeFaissIndex,
  renderAgentPrompt,
  rollbackAgent,
  runAgentTool,
  runScheduledTask,
  searchKnowledge,
  sendAgentChat,
  updateAgent,
  updateModelConfig,
  updateKnowledgeBase,
  updateKnowledgeChunk,
  updateKnowledgeDocument,
  updateScheduledTask,
  type AgentConfig,
  type AgentPromptVersion,
  type AgentRenderResponse,
  type AgentRun,
  type AgentChatMessage,
  type AgentChatResponse,
  type AgentChatToolCall,
  type AgentToolRunResponse,
  type AgentToolSpec,
  type AnalysisTask,
  type AnalysisTaskExecutionEvent,
  type AnalysisTaskReportResponse,
  type AnalysisTaskTemplate,
  type DataSnapshot,
  type HealthResponse,
  type KnowledgeBase,
  type KnowledgeChunk,
  type KnowledgeDocument,
  type KnowledgeDocumentDetail,
  type KnowledgeFaissStatus,
  type KnowledgeImportTask,
  type KnowledgeSearchItem,
  type ModelCapability,
  type ModelConfig,
  type PremarketRecommendationResponse,
  type ScheduledTask
} from "./api/client";
import { DataAnalysisPage } from "./pages/DataAnalysisPage";
import { DataSourcesPage } from "./pages/DataSourcesPage";
import { SkillManagementPage } from "./pages/SkillManagementPage";
import { ToolManagementPage } from "./pages/ToolManagementPage";
import { useConfirmDialog } from "./components/ConfirmDialog";

type PageKey =
  | "data_sources"
  | "data_analysis"
  | "chat"
  | "multi_agent"
  | "agents"
  | "tools"
  | "skills"
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
  { key: "chat", name: "Agent 对话", description: "单 Agent 问答、工具引用与追问", icon: <MessageSquareText size={17} /> },
  { key: "multi_agent", name: "智能辅助分析", description: "独立工作流、阶段产物与分析报告", icon: <BrainCircuit size={17} /> },
  { key: "agents", name: "智能体管理", description: "提示词、工具权限与版本", icon: <Bot size={17} /> },
  { key: "tools", name: "工具管理", description: "工具注册表、Schema 与 Agent 授权关系", icon: <Wrench size={17} /> },
  { key: "skills", name: "Skill 管理", description: "可复用工作方法与 Agent 分配", icon: <Puzzle size={17} /> },
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
    title: "Agent 对话",
    subtitle: ""
  },
  multi_agent: {
    title: "智能辅助分析",
    subtitle: "选择独立分析工作流，填写本次需求，跟踪阶段产物并查看最终报告。"
  },
  agents: {
    title: "智能体管理",
    subtitle: "前端可编辑所有发送给 Agent 的系统提示词、任务提示词和输出格式。"
  },
  tools: {
    title: "工具管理",
    subtitle: "审阅后端真实工具注册表、执行状态、输入输出 Schema 与 Agent 授权关系。"
  },
  skills: {
    title: "Skill 管理",
    subtitle: "维护可复用的研究方法，并将其注入指定 Agent 的模型上下文。"
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

function isTaskActive(task: AnalysisTask | null): boolean {
  return task ? ["pending", "running"].includes(task.status) : false;
}

type ChatDisplayMessage = AgentChatMessage & {
  conversationId?: string;
  turnId?: string;
  modelStatus?: string;
  toolCalls?: AgentChatToolCall[];
};

type ChatConversation = {
  id: string;
  title: string;
  agentKey: string;
  backendConversationId?: string;
  messages: ChatDisplayMessage[];
  latestResponse: AgentChatResponse | null;
};

function ChatAnalysisPage() {
  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [selectedKey, setSelectedKey] = useState("technical");
  const [input, setInput] = useState("300750 现在技术面怎么看？");
  const [conversations, setConversations] = useState<ChatConversation[]>([{
    id: "local-draft",
    title: "新对话",
    agentKey: "technical",
    messages: [],
    latestResponse: null,
  }]);
  const [activeConversationId, setActiveConversationId] = useState("local-draft");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);

  async function loadChatAgents() {
    const result = await fetchAgents();
    const enabled = result.items.filter((agent) => agent.enabled);
    setAgents(enabled);
    setSelectedKey((current) => enabled.some((agent) => agent.key === current) ? current : enabled[0]?.key ?? "");
  }

  useEffect(() => {
    loadChatAgents().catch((err: unknown) => {
      setMessage(err instanceof Error ? err.message : "Agent 加载失败");
    });
  }, []);

  const activeConversation = conversations.find((item) => item.id === activeConversationId) ?? conversations[0];
  const messages = activeConversation?.messages ?? [];
  const latestResponse = activeConversation?.latestResponse ?? null;

  function createConversation() {
    if (!activeConversation || activeConversation.messages.length === 0) {
      setInput("");
      setMessage("");
      return;
    }
    const id = `local-${Date.now()}`;
    setConversations((items) => [...items, {
      id,
      title: "新对话",
      agentKey: selectedKey,
      messages: [],
      latestResponse: null,
    }]);
    setActiveConversationId(id);
    setInput("");
    setMessage("");
  }

  function selectAgent(agentKey: string) {
    setSelectedKey(agentKey);
    setConversations((items) => items.map((item) => item.id === activeConversationId ? { ...item, agentKey } : item));
  }

  async function sendMessage() {
    const text = input.trim();
    if (!text || !selectedKey) {
      return;
    }
    const userMessage: ChatDisplayMessage = { role: "user", content: text };
    const nextHistory = [...messages, userMessage];
    setConversations((items) => items.map((item) => item.id === activeConversationId ? {
      ...item,
      agentKey: selectedKey,
      title: item.messages.length === 0 ? text.slice(0, 28) : item.title,
      messages: nextHistory,
    } : item));
    setInput("");
    setSending(true);
    setMessage("");
    try {
      const response = await sendAgentChat(selectedKey, {
        message: text,
        variables: { period: "daily" },
        history: messages,
        conversation_id: activeConversation?.backendConversationId,
        max_tool_calls: 4
      });
      const assistantMessage: ChatDisplayMessage = {
        role: "assistant",
        content: response.content,
        conversationId: response.conversation_id,
        turnId: response.turn_id,
        modelStatus: response.model_status,
        toolCalls: response.tool_calls,
      };
      setConversations((items) => items.map((item) => item.id === activeConversationId ? {
        ...item,
        backendConversationId: response.conversation_id,
        latestResponse: response,
        messages: [...nextHistory, assistantMessage],
      } : item));
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Agent 对话失败");
      setConversations((items) => items.map((item) => item.id === activeConversationId ? {
        ...item,
        messages: [...nextHistory, { role: "assistant", content: "这次对话失败了，请检查 Agent 配置、模型配置或数据源状态后再试。" }],
      } : item));
    } finally {
      setSending(false);
    }
  }

  const selectedAgent = agents.find((agent) => agent.key === selectedKey) ?? null;

  return (
    <div className="chat-layout">
      <aside className="conversation-sidebar">
        <div className="conversation-sidebar-head"><strong>对话</strong><button className="icon-btn" onClick={createConversation} title="新建对话" type="button"><Plus size={15} /></button></div>
        <div className="conversation-list">
          {conversations.map((conversation) => (
            <button className={conversation.id === activeConversationId ? "active" : ""} key={conversation.id} onClick={() => { setActiveConversationId(conversation.id); setSelectedKey(conversation.agentKey); }} type="button">
              <MessageSquareText size={14} /><span>{conversation.title}</span><small>{conversation.messages.length}</small>
            </button>
          ))}
        </div>
      </aside>

      <Panel
        title={selectedAgent ? `${selectedAgent.name} 对话` : "Agent 对话"}
        actions={<div className="chat-toolbar"><label><Bot size={15} /><select aria-label="选择智能体" value={selectedKey} onChange={(event) => selectAgent(event.target.value)}>{agents.map((agent) => <option key={agent.key} value={agent.key}>{agent.name} · {agent.role || agent.key}</option>)}</select></label><button className="btn btn-secondary" onClick={() => setConversations((items) => items.map((item) => item.id === activeConversationId ? { ...item, messages: [], latestResponse: null } : item))} type="button">清空</button></div>}
      >
        {message ? <div className="notice error">{message}</div> : null}
        <div className="message-list chat-thread">
          {messages.map((item, index) => (
            <div className={`msg ${item.role === "user" ? "user" : "agent"}`} key={`${item.role}-${index}`}>
              <p>{item.content}</p>
              {item.role === "assistant" && item.turnId ? (
                <div className="chat-turn-meta">
                  <code>{item.conversationId}</code>
                  <span>{item.modelStatus}</span>
                  <span>{item.toolCalls?.length ?? 0} tools</span>
                </div>
              ) : null}
            </div>
          ))}
          {messages.length === 0 ? <div className="empty-hint">暂无消息</div> : null}
          {sending ? <div className="msg agent muted"><p>正在回复...</p></div> : null}
        </div>
        <div className="composer">
          <input
            className="input"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && sendMessage()}
            placeholder="问当前 Agent，例如：这只股票的主要风险是什么？"
          />
          <button className="btn btn-primary" disabled={sending || !selectedKey} onClick={sendMessage} type="button">
            {sending ? "发送中" : "发送"}
          </button>
        </div>
      </Panel>

      <Panel title="知识库命中">
        <div className="snapshot-list knowledge-hit-list">
          {latestResponse?.knowledge_hits.map((hit) => (
            <div key={hit.citation}>
              <span className="mono">{hit.citation}</span>
              <strong>{hit.title}</strong>
              <p>{hit.snippet}</p>
            </div>
          )) ?? <div className="empty-hint">暂无命中</div>}
        </div>
      </Panel>
    </div>
  );
}

function AgentManagementPage() {
  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [modelConfigs, setModelConfigs] = useState<ModelConfig[]>([]);
  const [selectedKey, setSelectedKey] = useState("");
  const [form, setForm] = useState<AgentConfig | null>(null);
  const [versions, setVersions] = useState<AgentPromptVersion[]>([]);
  const [rendered, setRendered] = useState<AgentRenderResponse | null>(null);
  const [toolSpecs, setToolSpecs] = useState<AgentToolSpec[]>([]);
  const [toolSearch, setToolSearch] = useState("");
  const [activeDialog, setActiveDialog] = useState<"versions" | "tools" | null>(null);
  const [message, setMessage] = useState("");
  const [grantingAllTools, setGrantingAllTools] = useState(false);
  const { requestConfirmation, confirmDialog } = useConfirmDialog();

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
    fetchModelConfigs()
      .then((result) => setModelConfigs(result.items))
      .catch((err: unknown) => {
        setMessage(err instanceof Error ? err.message : "模型配置加载失败");
      });
  }, []);

  async function selectAgent(key: string) {
    setSelectedKey(key);
    const selected = agents.find((item) => item.key === key) ?? null;
    setForm(selected ? { ...selected } : null);
    setRendered(null);
    const versionResult = await fetchAgentVersions(key);
    setVersions(versionResult.items);
  }

  async function saveAgent() {
    if (!form) return;
    const configuredModel = modelConfigs.find(
      (item) => item.capability === "chat" && (item.key === form.model || item.model === form.model)
    );
    try {
      const updated = await updateAgent(form.key, {
        name: form.name,
        role: form.role,
        description: form.description,
        model: configuredModel?.key ?? form.model,
        temperature: Number(form.temperature),
        max_tokens: Number(form.max_tokens),
        enabled: form.enabled,
        system_prompt: form.system_prompt,
        task_prompt: form.task_prompt,
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

  async function rollback(version: number) {
    if (!form) return;
    const updated = await rollbackAgent(form.key, version);
    setMessage(`已回滚并生成 v${updated.current_version}`);
    await loadAgents(updated.key);
  }

  async function deleteVersion(version: number) {
    if (!form || version === form.current_version) return;
    if (!await requestConfirmation({ title: "删除提示词版本", description: `确定删除 v${version} 吗？此操作不可恢复。`, confirmLabel: "删除版本" })) return;
    try {
      await deleteAgentVersion(form.key, version);
      setVersions((items) => items.filter((item) => item.version !== version));
      setMessage(`已删除 v${version}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "删除版本失败");
    }
  }

  function updateTool(tool: string, checked: boolean) {
    if (!form) return;
    const nextTools = checked ? Array.from(new Set([...form.tools, tool])) : form.tools.filter((item) => item !== tool);
    setForm({ ...form, tools: nextTools });
  }

  async function grantAllTools() {
    if (!form) return;
    const toolKeys = toolSpecs.filter((tool) => tool.enabled).map((tool) => tool.key);
    if (toolKeys.length === 0) {
      setMessage("没有可授权的已启用工具");
      return;
    }
    setGrantingAllTools(true);
    try {
      const updated = await updateAgent(form.key, {
        tools: toolKeys,
        change_note: "一键授权全部已启用工具"
      });
      setForm(updated);
      setAgents((items) => items.map((item) => item.key === updated.key ? updated : item));
      setVersions((await fetchAgentVersions(updated.key)).items);
      setMessage(`已向 ${updated.name} 授权 ${toolKeys.length} 项工具`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "全部工具授权失败");
    } finally {
      setGrantingAllTools(false);
    }
  }

  const selectedAgent = form;
  const chatModels = modelConfigs.filter((item) => item.capability === "chat" && item.enabled);
  const defaultChatModel = chatModels.find((item) => item.is_default);
  const selectedConfiguredModel = chatModels.find(
    (item) => item.key === form?.model || item.model === form?.model
  );
  const selectableChatModels = chatModels.filter((item) => !item.is_default);
  const modelSelectValue = selectedConfiguredModel?.is_default ? "" : selectedConfiguredModel?.key ?? form?.model ?? "";
  const hasLegacyModel = Boolean(form?.model && !selectedConfiguredModel);
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
  const enabledToolCount = toolSpecs.filter((tool) => tool.enabled).length;
  const hasAllEnabledTools = enabledToolCount > 0 && toolSpecs.filter((tool) => tool.enabled).every((tool) => form?.tools.includes(tool.key));

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
        <div className="agent-editor-toolbar">
          <div>
            <h2>{selectedAgent ? `${selectedAgent.name} Agent` : "Agent 配置"}</h2>
            <p>{selectedAgent?.description ?? "前端可编辑所有实际发送给 Agent 的提示词配置。"}</p>
          </div>
          <div className="panel-actions">
            <button className="btn btn-secondary" onClick={() => setActiveDialog("versions")} type="button"><History size={15} />版本管理</button>
            <button className="btn btn-secondary" onClick={() => setActiveDialog("tools")} type="button"><ShieldCheck size={15} />工具权限{form ? ` (${form.tools.length})` : ""}</button>
            <button className="btn btn-secondary" onClick={previewPrompt} type="button">预览变量</button>
            <button className="btn btn-primary" onClick={saveAgent} type="button">保存提示词</button>
          </div>
        </div>
        {message ? <div className="notice">{message}</div> : null}
        <Panel>
          {form ? (
            <>
              <div className="form-grid">
                <label>名称<input className="input" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
                <label>模型
                  <select className="input" value={modelSelectValue} onChange={(event) => setForm({ ...form, model: event.target.value })}>
                    <option value="">{defaultChatModel ? `跟随系统默认（${defaultChatModel.model}）` : "跟随系统默认"}</option>
                    {hasLegacyModel ? <option disabled value={form.model}>当前配置：{form.model}（未在模型列表中）</option> : null}
                    {selectableChatModels.map((item) => <option key={item.key} value={item.key}>{item.name} · {item.model}</option>)}
                  </select>
                </label>
                <label>Temperature<input className="input mono" type="number" step="0.01" value={form.temperature} onChange={(event) => setForm({ ...form, temperature: Number(event.target.value) })} /></label>
                <label>Max Tokens<input className="input mono" type="number" value={form.max_tokens} onChange={(event) => setForm({ ...form, max_tokens: Number(event.target.value) })} /></label>
                <label>启用状态<select className="input" value={form.enabled ? "enabled" : "disabled"} onChange={(event) => setForm({ ...form, enabled: event.target.value === "enabled" })}><option value="enabled">启用</option><option value="disabled">停用</option></select></label>
                <label>角色<input className="input" value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })} /></label>
              </div>
              <div className="agent-prompt-stack">
                <label>系统提示词<textarea className="textarea prompt-textarea system-prompt" value={form.system_prompt} onChange={(event) => setForm({ ...form, system_prompt: event.target.value })} /></label>
                <label>任务提示词<textarea className="textarea prompt-textarea task-prompt" value={form.task_prompt} onChange={(event) => setForm({ ...form, task_prompt: event.target.value })} /></label>
              </div>
              <div className="chip-row">
                {form.variables.map((item) => (
                  <button className="chip-btn" key={item} type="button">{item}</button>
                ))}
              </div>
            </>
          ) : <div className="empty-hint">暂无 Agent 配置</div>}
        </Panel>

        {rendered ? (
          <Panel title="渲染后 Prompt">
            <div className="prompt-preview-stack">
              <label>System<textarea className="textarea" readOnly value={rendered.rendered_system_prompt} /></label>
              <label>Task<textarea className="textarea" readOnly value={rendered.rendered_task_prompt} /></label>
              <label>缺失变量<textarea className="textarea mono" readOnly value={rendered.missing_variables.join("\n") || "无"} /></label>
            </div>
          </Panel>
        ) : null}
      </div>
      {activeDialog === "versions" ? (
        <div className="agent-dialog-backdrop" role="presentation" onMouseDown={() => setActiveDialog(null)}>
          <section className="agent-dialog versions-dialog" aria-modal="true" aria-labelledby="versions-title" role="dialog" onMouseDown={(event) => event.stopPropagation()}>
            <div className="agent-dialog-header">
              <div><h2 id="versions-title">版本管理</h2><p>当前 Agent：{form?.name ?? "未选择"}</p></div>
              <button className="icon-btn" onClick={() => setActiveDialog(null)} title="关闭" type="button"><X size={16} /></button>
            </div>
            <div className="agent-dialog-body versions-body">
              <div className="version-list">
                {versions.map((version) => {
                  const isCurrent = version.version === selectedAgent?.current_version;
                  return (
                    <div className="version-row" key={version.id}>
                      <div><strong>v{version.version}</strong><small>{isCurrent ? "当前版本" : version.change_note || "历史版本"}</small></div>
                      {isCurrent ? <StatusBadge tone="green">当前</StatusBadge> : <><button className="btn btn-secondary" onClick={() => rollback(version.version)} type="button">回滚</button><button className="btn btn-danger" onClick={() => deleteVersion(version.version)} type="button"><Trash2 size={14} />删除</button></>}
                    </div>
                  );
                })}
                {versions.length === 0 ? <div className="empty-hint">暂无可用版本</div> : null}
              </div>
            </div>
          </section>
        </div>
      ) : null}
      {activeDialog === "tools" ? (
        <div className="agent-dialog-backdrop" role="presentation" onMouseDown={() => setActiveDialog(null)}>
          <section className="agent-dialog tools-dialog" aria-modal="true" aria-labelledby="tool-permission-title" role="dialog" onMouseDown={(event) => event.stopPropagation()}>
            <div className="agent-dialog-header">
              <div><h2 id="tool-permission-title">工具权限</h2><p>{form?.tools.length ?? 0} 项已授权</p></div>
              <div className="panel-actions"><button className="btn btn-secondary" disabled={grantingAllTools || hasAllEnabledTools || !form} onClick={() => void grantAllTools()} type="button">{grantingAllTools ? "授权中" : hasAllEnabledTools ? "已授权全部" : "一键授权全部"}</button><button className="icon-btn" onClick={() => setActiveDialog(null)} title="关闭" type="button"><X size={16} /></button></div>
            </div>
            <div className="tool-search">
              <input className="input" placeholder="搜索工具名、tool_key 或描述" value={toolSearch} onChange={(event) => setToolSearch(event.target.value)} />
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
          </section>
        </div>
      ) : null}
      {confirmDialog}
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
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [uploadingFiles, setUploadingFiles] = useState(false);
  const [rebuildingFaiss, setRebuildingFaiss] = useState(false);
  const [reindexingAll, setReindexingAll] = useState(false);
  const [savingBaseConfig, setSavingBaseConfig] = useState(false);
  const [rechunkingDocument, setRechunkingDocument] = useState(false);
  const [deletingBaseId, setDeletingBaseId] = useState<number | null>(null);
  const { requestConfirmation, confirmDialog } = useConfirmDialog();

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

  async function removeKnowledgeBase(base: KnowledgeBase) {
    if (base.id === 1) {
      setMessage("默认知识库不能删除");
      return;
    }
    if (!await requestConfirmation({ title: "删除知识库", description: `删除“${base.name}”及其中 ${base.document_count} 篇文档、全部分块和索引？此操作无法撤销。`, confirmLabel: "删除知识库" })) {
      return;
    }
    setDeletingBaseId(base.id);
    try {
      await deleteKnowledgeBase(base.id);
      const nextBase = knowledgeBases.find((item) => item.id !== base.id) ?? null;
      setSelectedDocument(null);
      setDocuments([]);
      setImportTasks([]);
      if (nextBase) {
        await switchKnowledgeBase(nextBase.id);
      } else {
        await loadKnowledgeBases(1);
      }
      await loadFaissStatus();
      setMessage(`已删除知识库：${base.name}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "知识库删除失败");
    } finally {
      setDeletingBaseId(null);
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
      setImportDialogOpen(false);
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
      setChunkingStrategy(detail.chunking_strategy);
      setChunkSize(detail.chunk_size);
      setChunkOverlap(detail.chunk_overlap);
      setSeparatorsText(detail.separators.map(escapeSeparatorForInput).join("|"));
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
    if (!await requestConfirmation({ title: "删除文档", description: "删除这篇文档及其全部分块和向量索引？此操作无法撤销。", confirmLabel: "删除文档" })) {
      return;
    }
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

  async function saveDocument(
    document: KnowledgeDocumentDetail,
    payload: { title: string; content: string; docType: string; source: string; symbolsText: string; tagsText: string; enabled: boolean }
  ) {
    try {
      const updated = await updateKnowledgeDocument(document.id, {
        title: payload.title,
        content: payload.content,
        doc_type: payload.docType,
        source: payload.source,
        symbols: splitCsv(payload.symbolsText),
        tags: splitCsv(payload.tagsText),
        enabled: payload.enabled
      });
      setSelectedDocument(updated);
      setMessage(`已保存：${updated.title}${payload.content !== document.content ? "，并已重新分块索引" : ""}`);
      await Promise.all([loadDocuments(docQuery, selectedBaseId), loadKnowledgeBases(selectedBaseId), loadFaissStatus()]);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "文档保存失败");
    }
  }

  return (
    <div className="page-grid knowledge-layout">
      <div className="main-column">
        {message ? <div className="notice">{message}</div> : null}
        <Panel
          title={selectedBase ? `${selectedBase.name}（${selectedBase.document_count} 篇文档）` : "知识库"}
          actions={
            <>
              <button className="btn btn-secondary" disabled={reindexingAll} onClick={reindexAllDocuments} type="button">{reindexingAll ? "重建中..." : "全量重建"}</button>
              <button className="btn btn-primary" onClick={() => setImportDialogOpen(true)} type="button"><Upload size={15} />上传资料</button>
            </>
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

        {selectedDocument ? <Panel className="detail-modal document-detail-modal" title="文档详情" actions={<button className="icon-btn" onClick={() => setSelectedDocument(null)} title="关闭" type="button"><X size={16} /></button>}>
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
              <DocumentEditor document={selectedDocument} onSave={saveDocument} />
              <div className="chunking-control-bar">
                <strong>分块设置</strong>
                <label>方式<select className="input" value={chunkingStrategy} onChange={(event) => setChunkingStrategy(event.target.value)}><option value="paragraph">段落窗口</option><option value="characters">字符数</option><option value="separators">特殊符号</option></select></label>
                <label>上限<input className="input mono" min={100} max={8000} onChange={(event) => setChunkSize(Number(event.target.value) || 900)} type="number" value={chunkSize} /></label>
                <label>重叠<input className="input mono" min={0} max={2000} onChange={(event) => setChunkOverlap(Number(event.target.value) || 0)} type="number" value={chunkOverlap} /></label>
                <label className="chunk-separators">分隔符<input className="input mono" onChange={(event) => setSeparatorsText(event.target.value)} value={separatorsText} /></label>
                <button className="btn btn-secondary" disabled={rechunkingDocument} onClick={rechunkSelectedDocument} type="button">{rechunkingDocument ? "重新切分中" : "重新切分"}</button>
              </div>
              <div className="chunk-list">
                {selectedDocument.chunks.map((chunk) => (
                  <ChunkEditor chunk={chunk} key={chunk.id} onSave={saveChunk} />
                ))}
              </div>
            </div>
          ) : <div className="empty-hint">选择一篇文档查看正文分块和 citation 来源</div>}
        </Panel> : null}
      </div>

      <div className="side-column">
        <Panel title="知识库">
          <div className="knowledge-base-list">
            {knowledgeBases.map((item) => (
              <div className="knowledge-base-entry" key={item.id}>
                <button
                  className={`knowledge-base-row ${item.id === selectedBaseId ? "active" : ""}`}
                  onClick={() => switchKnowledgeBase(item.id)}
                  type="button"
                >
                  <strong>{item.name}</strong>
                  <span>{item.document_count} docs · {item.chunking_strategy} · {item.chunk_size}/{item.chunk_overlap}</span>
                </button>
                <button className="icon-btn knowledge-base-delete" disabled={item.id === 1 || deletingBaseId === item.id} onClick={() => removeKnowledgeBase(item)} title={item.id === 1 ? "默认知识库不能删除" : "删除知识库"} type="button"><Trash2 size={15} /></button>
              </div>
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
      {importDialogOpen ? (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setImportDialogOpen(false)}>
          <section className="modal-dialog knowledge-import-dialog" aria-modal="true" aria-labelledby="knowledge-import-title" role="dialog" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-dialog-header">
              <div><h2 id="knowledge-import-title">上传并索引</h2><p>系统会解析文件，并按当前分块设置建立索引。</p></div>
              <button className="icon-btn" onClick={() => setImportDialogOpen(false)} title="关闭" type="button"><X size={16} /></button>
            </div>
            <div className="modal-dialog-body knowledge-import-body">
              <div className="form-grid compact">
                <label>目标知识库
                  <select className="input" value={selectedBaseId} onChange={(event) => switchKnowledgeBase(Number(event.target.value))}>
                    {knowledgeBases.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <label>分块方式
                  <select className="input" value={chunkingStrategy} onChange={(event) => setChunkingStrategy(event.target.value)}>
                    <option value="paragraph">段落窗口</option>
                    <option value="characters">字符数</option>
                    <option value="separators">特殊符号</option>
                  </select>
                </label>
                <label>字符上限<input className="input mono" min={100} max={8000} type="number" value={chunkSize} onChange={(event) => setChunkSize(Number(event.target.value) || 900)} /></label>
                <label>重叠字符<input className="input mono" min={0} max={2000} type="number" value={chunkOverlap} onChange={(event) => setChunkOverlap(Number(event.target.value) || 0)} /></label>
              </div>
              <div className="form-stack tight">
                <label>特殊分隔符<input className="input mono" value={separatorsText} onChange={(event) => setSeparatorsText(event.target.value)} /></label>
                <div className="button-stack inline">
                  <button className="btn btn-secondary" disabled={savingBaseConfig} onClick={saveBaseConfig} type="button">{savingBaseConfig ? "保存中..." : "保存为知识库默认配置"}</button>
                </div>
              </div>
              <div className="upload-zone">
                <input multiple type="file" accept=".txt,.md,.csv,.json,.html,.htm,.pdf,.docx,text/*,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => setSelectedFiles(Array.from(event.target.files ?? []))} />
                <div><strong>{selectedFiles.length ? `已选择 ${selectedFiles.length} 个文件` : "选择资料文件"}</strong><span>支持 TXT、Markdown、CSV、JSON、HTML；PDF 和 Word 会走专用解析器。</span></div>
              </div>
              <div className="file-list">
                {selectedFiles.map((file) => <div key={`${file.name}-${file.size}`}><span>{file.name}</span><small className="mono">{Math.ceil(file.size / 1024)} KB</small></div>)}
                {selectedFiles.length === 0 ? <div className="empty-hint">请选择要导入到“{selectedBase?.name ?? "知识库"}”的资料文件</div> : null}
              </div>
            </div>
            <div className="modal-dialog-footer">
              <button className="btn btn-secondary" onClick={() => setImportDialogOpen(false)} type="button">取消</button>
              <button className="btn btn-primary" disabled={uploadingFiles || selectedFiles.length === 0} onClick={uploadSelectedFiles} type="button"><Upload size={15} />{uploadingFiles ? "导入中..." : "上传并索引"}</button>
            </div>
          </section>
        </div>
      ) : null}
      {confirmDialog}
    </div>
  );
}

function DocumentEditor({
  document,
  onSave
}: {
  document: KnowledgeDocumentDetail;
  onSave: (
    document: KnowledgeDocumentDetail,
    payload: { title: string; content: string; docType: string; source: string; symbolsText: string; tagsText: string; enabled: boolean }
  ) => Promise<void>;
}) {
  const [title, setTitle] = useState(document.title);
  const [content, setContent] = useState(document.content);
  const [docType, setDocType] = useState(document.doc_type);
  const [source, setSource] = useState(document.source);
  const [symbolsText, setSymbolsText] = useState(document.symbols.join(","));
  const [tagsText, setTagsText] = useState(document.tags.join(","));
  const [enabled, setEnabled] = useState(document.enabled);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setTitle(document.title);
    setContent(document.content);
    setDocType(document.doc_type);
    setSource(document.source);
    setSymbolsText(document.symbols.join(","));
    setTagsText(document.tags.join(","));
    setEnabled(document.enabled);
  }, [document]);

  async function save() {
    if (!title.trim() || !content.trim()) {
      return;
    }
    setSaving(true);
    try {
      await onSave(document, { title: title.trim(), content: content.trim(), docType: docType.trim(), source: source.trim(), symbolsText, tagsText, enabled });
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="document-editor">
      <div className="document-editor-head"><strong>文档内容</strong><button className="btn btn-primary" disabled={saving || !title.trim() || !content.trim()} onClick={save} type="button">{saving ? "保存中" : "保存文档"}</button></div>
      <div className="form-grid compact">
        <label>标题<input className="input" onChange={(event) => setTitle(event.target.value)} value={title} /></label>
        <label>类型<input className="input" onChange={(event) => setDocType(event.target.value)} value={docType} /></label>
        <label>来源<input className="input" onChange={(event) => setSource(event.target.value)} value={source} /></label>
        <label>股票代码<input className="input mono" onChange={(event) => setSymbolsText(event.target.value)} placeholder="300750,000001" value={symbolsText} /></label>
        <label>标签<input className="input" onChange={(event) => setTagsText(event.target.value)} placeholder="储能,基本面" value={tagsText} /></label>
        <label className="check-line"><input checked={enabled} onChange={(event) => setEnabled(event.target.checked)} type="checkbox" /><span>参与检索</span></label>
      </div>
      <label className="document-content-field">正文<textarea className="textarea document-content-textarea" onChange={(event) => setContent(event.target.value)} value={content} /></label>
    </section>
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

function SnapshotDetail({ snapshot }: { snapshot: DataSnapshot | null }) {
  if (!snapshot) {
    return <div className="empty-hint">选择数据快照后查看行情、指标、新闻和知识库引用</div>;
  }
  const data = parseSnapshotJson(snapshot.snapshot_json);
  const quote = asRecord(data.quote);
  const indicators = asRecord(data.indicators);
  const marketNews = asRecord(data.market_news);
  const knowledge = asRecord(data.knowledge_context);
  const warnings = asArray(data.warnings);
  const indicatorItems = asArray(indicators.items);
  const newsItems = asArray(marketNews.items);
  const knowledgeItems = asArray(knowledge.items);

  return (
    <div className="snapshot-detail">
      <div className="snapshot-head">
        <div>
          <span className="label">数据快照</span>
          <strong className="mono">#{snapshot.id} · {snapshot.symbol} · {snapshot.period}</strong>
        </div>
        <StatusBadge tone={warnings.length ? "amber" : "green"}>{warnings.length ? `${warnings.length} warnings` : "ready"}</StatusBadge>
      </div>
      <div className="metrics-grid four">
        <div className="metric"><span>最新价</span><strong>{formatSnapshotValue(quote.price)}</strong><small>{String(quote.provider_key ?? "-")}</small></div>
        <div className="metric"><span>涨跌幅</span><strong>{formatSnapshotValue(quote.change_percent)}%</strong><small>{String(quote.timestamp ?? "-")}</small></div>
        <div className="metric"><span>指标</span><strong>{indicatorItems.length}</strong><small>MA / MACD / RSI / KDJ / BOLL</small></div>
        <div className="metric"><span>新闻</span><strong>{newsItems.length}</strong><small>{String(marketNews.provider_key ?? "-")}</small></div>
      </div>
      <div className="snapshot-section">
        <strong>指标序列</strong>
        <div className="reference-list compact">
          {indicatorItems.slice(0, 10).map((item, index) => {
            const row = asRecord(item);
            const values = asArray(row.values);
            return <button key={`${String(row.name)}-${index}`} type="button">{String(row.name ?? "indicator")} · latest {formatSnapshotValue(values[values.length - 1])}</button>;
          })}
          {indicatorItems.length === 0 ? <button type="button">暂无指标</button> : null}
        </div>
      </div>
      <div className="snapshot-section">
        <strong>新闻引用</strong>
        <div className="snapshot-list">
          {newsItems.slice(0, 5).map((item, index) => {
            const row = asRecord(item);
            return <div key={`${String(row.id ?? index)}-${index}`}><span>{String(row.source ?? "news")}</span><p>{String(row.title ?? "")}</p></div>;
          })}
          {newsItems.length === 0 ? <div className="empty-hint">暂无新闻</div> : null}
        </div>
      </div>
      <div className="snapshot-section">
        <strong>知识库引用</strong>
        <div className="snapshot-list">
          {knowledgeItems.slice(0, 5).map((item, index) => {
            const row = asRecord(item);
            return <div key={`${String(row.citation ?? index)}-${index}`}><span className="mono">{String(row.citation ?? "citation")}</span><p>{String(row.snippet ?? "")}</p></div>;
          })}
          {knowledgeItems.length === 0 ? <div className="empty-hint">暂无知识库引用</div> : null}
        </div>
      </div>
      {warnings.length ? (
        <div className="snapshot-section">
          <strong>Warnings</strong>
          <div className="snapshot-list">
            {warnings.map((item, index) => {
              const row = asRecord(item);
              return <div key={`${String(row.stage ?? index)}-${index}`}><span>{String(row.stage ?? "warning")}</span><p>{String(row.message ?? "")}</p></div>;
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function parseSnapshotJson(value: string): Record<string, unknown> {
  try {
    const parsed = JSON.parse(value) as unknown;
    return asRecord(parsed);
  } catch {
    return {};
  }
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function formatSnapshotValue(value: unknown): string {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value.toFixed(2).replace(/\.00$/, "") : "-";
  }
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return String(value);
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

type AnalysisGroupKey = string;

interface AnalysisPreset {
  key: string;
  group: AnalysisGroupKey;
  groupName?: string;
  name: string;
  description: string;
  agentKeys: string[];
  includeReport: boolean;
  defaultQuery: string;
  isCustomized?: boolean;
}

const agentLabelMap: Record<string, string> = {
  data_steward: "数据管家",
  technical: "技术面",
  news: "新闻",
  fundamental: "基本面",
  policy_industry: "政策行业",
  capital_flow: "资金",
  bull: "多方",
  bear: "空方",
  risk: "风控",
  research_director: "投研总监"
};

function mapAnalysisTaskTemplate(template: AnalysisTaskTemplate): AnalysisPreset {
  return {
    key: template.key,
    group: template.group as AnalysisGroupKey,
    groupName: template.group_name,
    name: template.name,
    description: template.description,
    agentKeys: template.agent_keys,
    includeReport: template.include_report,
    defaultQuery: template.default_prompt,
    isCustomized: template.is_customized
  };
}

function AssistedAnalysisPage() {
  const [templates, setTemplates] = useState<AnalysisPreset[]>([]);
  const [scheduledTasks, setScheduledTasks] = useState<ScheduledTask[]>([]);
  const [recommendations, setRecommendations] = useState<PremarketRecommendationResponse>({
    scan_date: "",
    generated_at: null,
    source: "watchlist_premarket_scan",
    source_label: "当前自选股候选池",
    candidate_count: 0,
    items: []
  });
  const [presetKey, setPresetKey] = useState("");
  const [groupKey, setGroupKey] = useState("");
  const [query, setQuery] = useState("");
  const [task, setTask] = useState<AnalysisTask | null>(null);
  const [run, setRun] = useState<AgentRun | null>(null);
  const [executionEvents, setExecutionEvents] = useState<AnalysisTaskExecutionEvent[]>([]);
  const [report, setReport] = useState<AnalysisTaskReportResponse | null>(null);
  const [message, setMessage] = useState("");
  const [running, setRunning] = useState(false);
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [scheduleEnabled, setScheduleEnabled] = useState(true);
  const [scheduleTime, setScheduleTime] = useState("08:30");
  const [loadingTemplates, setLoadingTemplates] = useState(true);

  const preset = templates.find((item) => item.key === presetKey) ?? null;
  const scheduledTask = scheduledTasks.find((item) => `scheduled:${item.key}` === presetKey) ?? null;
  const groupedPresets = templates.filter((item) => item.group === groupKey);
  const groupedScheduledTasks = groupKey === "scheduled" ? scheduledTasks : [];
  const workflowGroups = Array.from(
    templates.reduce((groups, item) => {
      if (!groups.has(item.group)) groups.set(item.group, item.groupName || item.group);
      return groups;
    }, new Map<string, string>())
  );
  if (scheduledTasks.length > 0 && !workflowGroups.some(([key]) => key === "scheduled")) {
    workflowGroups.push(["scheduled", "定时任务"]);
  }
  const workflowGroupItems = workflowGroups.map(([key, name]) => ({ key, name }));

  useEffect(() => {
    Promise.all([fetchAnalysisTaskTemplates(), fetchScheduledTasks(), fetchPremarketRecommendations()])
      .then(([templateResult, scheduledResult, recommendationResult]) => {
        const nextTemplates = templateResult.items.map(mapAnalysisTaskTemplate);
        const nextScheduledTasks = scheduledResult.items.filter((item) => item.category === "analysis");
        if (nextTemplates.length === 0) {
          setMessage("没有可用的分析工作流");
        }
        setTemplates(nextTemplates);
        setScheduledTasks(nextScheduledTasks);
        setRecommendations(recommendationResult);
        const standard = nextTemplates.find((item) => item.key === "standard") ?? nextTemplates[0];
        if (standard) {
          setPresetKey(standard.key);
          setGroupKey(standard.group);
        } else if (nextScheduledTasks[0]) {
          setPresetKey(`scheduled:${nextScheduledTasks[0].key}`);
          setGroupKey("scheduled");
        }
      })
      .catch((err: unknown) => setMessage(err instanceof Error ? err.message : "分析工作流加载失败"))
      .finally(() => setLoadingTemplates(false));
  }, []);

  function selectGroup(nextGroupKey: string) {
    setGroupKey(nextGroupKey);
    const firstPreset = templates.find((item) => item.group === nextGroupKey);
    if (firstPreset) {
      selectPreset(firstPreset);
      return;
    }
    if (nextGroupKey === "scheduled" && scheduledTasks[0]) {
      selectScheduledTask(scheduledTasks[0]);
    }
  }

  function selectPreset(nextPreset: AnalysisPreset) {
    setPresetKey(nextPreset.key);
    setTask(null);
    setRun(null);
    setExecutionEvents([]);
    setReport(null);
    setMessage("");
  }

  function selectScheduledTask(nextTask: ScheduledTask) {
    setPresetKey(`scheduled:${nextTask.key}`);
    setTask(null);
    setRun(null);
    setExecutionEvents([]);
    setReport(null);
    setScheduleEnabled(nextTask.enabled);
    setScheduleTime(nextTask.daily_time || "08:30");
    setMessage("");
  }

  async function refreshScheduledTask(taskKey: string) {
    const [scheduledResult, recommendationResult] = await Promise.all([
      fetchScheduledTasks(),
      fetchPremarketRecommendations()
    ]);
    const nextScheduledTasks = scheduledResult.items.filter((item) => item.category === "analysis");
    setScheduledTasks(nextScheduledTasks);
    setRecommendations(recommendationResult);
    const refreshed = nextScheduledTasks.find((item) => item.key === taskKey);
    if (refreshed) {
      setScheduleEnabled(refreshed.enabled);
      setScheduleTime(refreshed.daily_time || "08:30");
    }
  }

  async function saveSchedule() {
    if (!scheduledTask) return;
    setSavingSchedule(true);
    setMessage("");
    try {
      const updated = await updateScheduledTask(scheduledTask.key, {
        enabled: scheduleEnabled,
        daily_time: scheduledTask.configurable ? scheduleTime : null
      });
      setScheduledTasks((items) => items.map((item) => item.key === updated.key ? updated : item));
      setMessage("定时设置已保存");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "定时设置保存失败");
    } finally {
      setSavingSchedule(false);
    }
  }

  async function runScheduledAnalysis() {
    if (!scheduledTask) return;
    setRunning(true);
    setMessage("");
    try {
      const result = await runScheduledTask(scheduledTask.key);
      await refreshScheduledTask(scheduledTask.key);
      setMessage(result.status === "success" ? result.message : `执行失败：${result.message}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "定时任务执行失败");
    } finally {
      setRunning(false);
    }
  }

  useEffect(() => {
    if (!task || !isTaskActive(task)) {
      return undefined;
    }
    const events = new EventSource(analysisTaskEventsUrl(task.task_key));
    events.addEventListener("task", (event) => {
      const nextTask = JSON.parse((event as MessageEvent).data) as AnalysisTask;
      setTask(nextTask);
      fetchAnalysisTaskExecution(nextTask.task_key)
        .then((result) => setExecutionEvents(result.items))
        .catch(() => undefined);
    });
    events.addEventListener("done", () => {
      events.close();
      fetchAnalysisTask(task.task_key)
        .then(async (nextTask) => {
          setTask(nextTask);
          if (nextTask.run_key) {
            setRun(await fetchAgentRun(nextTask.run_key));
          }
          setExecutionEvents((await fetchAnalysisTaskExecution(nextTask.task_key)).items);
          if (nextTask.report_path) {
            setReport(await fetchAnalysisTaskReport(nextTask.task_key));
          }
        })
        .catch((err: unknown) => setMessage(err instanceof Error ? err.message : "任务刷新失败"));
    });
    events.onerror = () => events.close();
    return () => events.close();
  }, [task?.task_key, task?.status]);

  async function startTask() {
    if (!preset) {
      setMessage("请选择分析工作流");
      return;
    }
    if (!query.trim()) {
      setMessage("请填写分析需求");
      return;
    }
    setRunning(true);
    setMessage("");
    setRun(null);
    setExecutionEvents([]);
    setReport(null);
    try {
      const created = await createAnalysisTask({
        query: query.trim(),
        mode: preset.key,
      });
      setTask(created);
      setMessage(`任务 ${created.task_key} 已创建`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "任务创建失败");
    } finally {
      setRunning(false);
    }
  }

  const frozenAgents = Array.isArray(task?.workflow.agents) ? task.workflow.agents.filter(isWorkflowAgent) : [];
  const stageAgents = frozenAgents.length > 0 ? frozenAgents.map((agent) => agent.key) : preset?.agentKeys ?? [];
  const completedEvents = executionEvents.filter((event) => event.event_type === "agent_completed");

  function stageState(agentKey: string): { status: string; summary: string } {
    const completed = [...completedEvents].reverse().find((event) => event.agent_key === agentKey);
    if (completed) {
      const envelope = completed.payload.artifact as Record<string, unknown> | undefined;
      const artifact = envelope?.artifact as Record<string, unknown> | undefined;
      return { status: completed.status || "completed", summary: String(artifact?.summary ?? "阶段产物已生成") };
    }
    const started = [...executionEvents].reverse().find((event) => event.event_type === "agent_started" && event.agent_key === agentKey);
    return started ? { status: "running", summary: "正在调用模型与工具" } : { status: "pending", summary: "等待上游阶段" };
  }

  return (
    <div className="assistant-analysis-page">
      {message ? <div className="notice">{message}</div> : null}
      <section className="assistant-workbench">
        <aside className="workflow-navigator" aria-label="分析工作流">
          <div className="workbench-section-heading"><strong>任务工作流</strong><span>{templates.length + scheduledTasks.length} 项</span></div>
          {loadingTemplates ? <div className="empty-hint">正在加载工作流</div> : (
            <>
              <div className="workflow-group-tabs" role="tablist" aria-label="任务分组">
                {workflowGroupItems.map((group) => <button aria-selected={groupKey === group.key} className={groupKey === group.key ? "active" : ""} key={group.key} onClick={() => selectGroup(group.key)} role="tab" type="button"><span>{group.name}</span><small>{templates.filter((item) => item.group === group.key).length + (group.key === "scheduled" ? scheduledTasks.length : 0)}</small></button>)}
              </div>
              <div className="workflow-list">
                {groupedPresets.map((item) => <button className={presetKey === item.key ? "active" : ""} disabled={isTaskActive(task)} key={item.key} onClick={() => selectPreset(item)} type="button"><div><strong>{item.name}</strong><span>{item.description}</span></div><ChevronRight size={15} /></button>)}
                {groupedScheduledTasks.map((item) => <button className={presetKey === `scheduled:${item.key}` ? "active" : ""} key={item.key} onClick={() => selectScheduledTask(item)} type="button"><div><strong>{item.name}</strong><span>{item.description}</span></div><CalendarClock size={15} /></button>)}
              </div>
            </>
          )}
        </aside>

        <main className="analysis-task-surface">
          {scheduledTask ? (
            <>
              <header className="selected-workflow-header">
                <div><span>定时任务</span><h2>{scheduledTask.name}</h2><p>{scheduledTask.description}</p></div>
                <StatusBadge tone={!scheduledTask.enabled ? "neutral" : scheduledTask.last_status === "failed" ? "red" : scheduledTask.last_status === "success" ? "green" : "amber"}>{!scheduledTask.enabled ? "已停用" : scheduledTask.last_status === "failed" ? "上次失败" : scheduledTask.last_status === "success" ? "运行正常" : "等待首跑"}</StatusBadge>
              </header>
              <div className="scheduled-task-config">
                <div className="scheduled-config-heading"><div><CalendarClock size={18} /><div><strong>执行计划</strong><span>{scheduledTask.schedule}</span></div></div><button className="btn btn-primary" disabled={running} onClick={runScheduledAnalysis} type="button"><Play size={15} />{running ? "正在执行" : "立即执行"}</button></div>
                <div className="scheduled-config-controls">
                  <label className="switch-row"><input checked={scheduleEnabled} onChange={(event) => setScheduleEnabled(event.target.checked)} type="checkbox" /><span><strong>启用自动执行</strong><small>关闭后仍可手动执行</small></span></label>
                  <label className="schedule-time-field"><span>盘前执行时间</span><input disabled={!scheduleEnabled || !scheduledTask.configurable} type="time" value={scheduleTime} onChange={(event) => setScheduleTime(event.target.value)} /></label>
                  <button className="btn" disabled={savingSchedule || !scheduleTime} onClick={saveSchedule} type="button"><Save size={15} />{savingSchedule ? "保存中" : "保存设置"}</button>
                </div>
              </div>
              <section className="scheduled-run-status">
                <div className="workbench-section-heading"><strong>最近执行</strong><span>{scheduledTask.last_finished_at ? formatDateTime(scheduledTask.last_finished_at) : "尚未执行"}</span></div>
                <dl>
                  <div><dt>候选来源</dt><dd>{recommendations.source_label}</dd></div>
                  <div><dt>任务状态</dt><dd>{scheduledTask.last_status || "等待首跑"}</dd></div>
                  <div><dt>执行结果</dt><dd>{scheduledTask.last_message || "尚无执行记录"}</dd></div>
                  <div><dt>结果日期</dt><dd>{recommendations.scan_date || "尚未生成"}</dd></div>
                </dl>
              </section>
            </>
          ) : preset ? (
            <>
              <header className="selected-workflow-header">
                <div><span>{preset.groupName || preset.group}</span><h2>{preset.name}</h2><p>{preset.description}</p></div>
                <StatusBadge tone={isTaskActive(task) ? "amber" : task?.status === "completed" ? "green" : task?.status === "failed" ? "red" : "neutral"}>{isTaskActive(task) ? "执行中" : task?.status === "completed" ? "已完成" : task?.status === "failed" ? "失败" : "可执行"}</StatusBadge>
              </header>
              <div className="workflow-route" aria-label="工作流阶段">
                {stageAgents.map((agentKey, index) => <div key={`${agentKey}-${index}`}><span>{index + 1}</span><strong>{agentLabelMap[agentKey] ?? agentKey}</strong>{index < stageAgents.length - 1 ? <ChevronRight size={14} /> : null}</div>)}
              </div>
              <div className="analysis-request-editor">
                <label htmlFor="analysis-requirement">本次分析需求</label>
                <textarea autoFocus className="textarea task-request-textarea" disabled={isTaskActive(task)} id="analysis-requirement" placeholder="描述你希望解决的问题、关注的事实和需要明确的风险。" value={query} onChange={(event) => setQuery(event.target.value)} />
                <div className="request-editor-footer"><span>{query.trim().length} 字</span><button className="btn btn-primary" disabled={running || isTaskActive(task) || !query.trim()} onClick={startTask} type="button"><BrainCircuit size={15} />{isTaskActive(task) ? "分析执行中" : running ? "正在创建" : "启动工作流"}</button></div>
              </div>
              <section className="live-stage-section">
                <div className="workbench-section-heading"><strong>执行阶段</strong>{task ? <span className="mono">{task.task_key}</span> : <span>等待启动</span>}</div>
                {task ? <div className="task-progress-overview"><div><span style={{ width: `${task.progress}%` }} /></div><strong>{task.progress}%</strong><small>{task.stage}</small></div> : null}
                <div className="workflow-stage-list">
                  {stageAgents.map((agentKey, index) => {
                    const state = stageState(agentKey);
                    return <div className={`workflow-stage-row ${state.status}`} key={`${agentKey}-${index}`}><span className="stage-index">{index + 1}</span><div><strong>{agentLabelMap[agentKey] ?? agentKey}</strong><p>{state.summary}</p></div><StatusBadge tone={state.status === "completed" ? "green" : state.status === "failed" ? "red" : state.status === "running" ? "amber" : "neutral"}>{state.status === "completed" ? "完成" : state.status === "failed" ? "失败" : state.status === "running" ? "执行中" : "等待"}</StatusBadge></div>;
                  })}
                </div>
              </section>
            </>
          ) : <div className="empty-hint">选择一个任务工作流开始分析</div>}
        </main>

        <aside className="analysis-result-pane">
          <div className="workbench-section-heading"><strong>{scheduledTask ? "盘前推荐结果" : "分析结果"}</strong>{scheduledTask ? <span>{recommendations.items.length} 只</span> : run ? <StatusBadge tone={run.status === "completed" ? "green" : "amber"}>{run.status}</StatusBadge> : null}</div>
          {scheduledTask ? (recommendations.items.length > 0 ? <div className="scheduled-recommendation-list"><div className="recommendation-result-meta"><strong>{recommendations.scan_date}</strong><span>{recommendations.generated_at ? formatDateTime(recommendations.generated_at) : ""}</span></div>{recommendations.items.map((item) => <div className="scheduled-recommendation-row" key={item.symbol}><span className="recommendation-rank">{item.rank}</span><div><strong>{item.name}<small>{item.symbol}</small></strong><p>{item.reason}</p></div><span className="recommendation-score">{item.score}</span></div>)}</div> : <div className="result-empty"><CalendarClock size={28} /><strong>尚未生成盘前推荐</strong><span>到达设定时间后自动执行，也可以点击“立即执行”生成结果。</span></div>) : report ? <div className="inline-report"><div className="inline-report-meta"><FileText size={16} /><span>{report.task_key}</span><a href={analysisTaskReportDownloadUrl(report.task_key)}>下载</a></div><pre>{report.content}</pre></div> : run ? <div className="result-summary"><span>最终结论</span><h3>{String(run.result.conclusion || "分析已完成")}</h3><p>{String(run.result.summary || "报告正在归档")}</p><div><strong>{String(run.result.confidence ?? 0)}%</strong><span>置信度</span></div></div> : <div className="result-empty"><FileText size={28} /><strong>报告将在这里生成</strong><span>阶段结果会先实时出现，最终报告通过质量校验后原位展示。</span></div>}
        </aside>
      </section>
    </div>
  );
}

function TasksReportsPage() {
  const [tasks, setTasks] = useState<AnalysisTask[]>([]);
  const [workflowNames, setWorkflowNames] = useState<Record<string, string>>({});
  const [selectedRun, setSelectedRun] = useState<AgentRun | null>(null);
  const [selectedTask, setSelectedTask] = useState<AnalysisTask | null>(null);
  const [taskDetailOpen, setTaskDetailOpen] = useState(false);
  const [executionEvents, setExecutionEvents] = useState<AnalysisTaskExecutionEvent[]>([]);
  const [snapshotDetail, setSnapshotDetail] = useState<DataSnapshot | null>(null);
  const [reportDetail, setReportDetail] = useState<AnalysisTaskReportResponse | null>(null);
  const [reportTask, setReportTask] = useState<AnalysisTask | null>(null);
  const [reportDialogOpen, setReportDialogOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [deletingTaskKey, setDeletingTaskKey] = useState("");
  const [clearingTasks, setClearingTasks] = useState(false);
  const { requestConfirmation, confirmDialog } = useConfirmDialog();

  async function loadTasks(openFirst = false) {
    const result = await fetchAnalysisTasks(30);
    setTasks(result.items);
    const nextTask = selectedTask
      ? result.items.find((item) => item.task_key === selectedTask.task_key) ?? selectedTask
      : result.items[0] ?? null;
    setSelectedTask(nextTask);
    if (openFirst && nextTask?.run_key) {
      await openTask(nextTask, { resetReport: false });
    }
  }

  useEffect(() => {
    loadTasks().catch((err: unknown) => {
      setMessage(err instanceof Error ? err.message : "任务加载失败");
    });
    fetchAnalysisTaskTemplates()
      .then((result) => setWorkflowNames(Object.fromEntries(result.items.map((item) => [item.key, item.name]))))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!tasks.some((task) => isTaskActive(task))) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      loadTasks(false).catch((err: unknown) => {
        setMessage(err instanceof Error ? err.message : "任务刷新失败");
      });
    }, 2500);
    return () => window.clearInterval(timer);
  }, [tasks, selectedTask?.task_key]);

  useEffect(() => {
    if (!selectedTask || !isTaskActive(selectedTask)) {
      return undefined;
    }
    const taskKey = selectedTask.task_key;
    const events = new EventSource(analysisTaskEventsUrl(taskKey));
    events.addEventListener("task", (event) => {
      const nextTask = JSON.parse((event as MessageEvent).data) as AnalysisTask;
      setSelectedTask(nextTask);
      setTasks((current) => current.map((item) => item.task_key === nextTask.task_key ? nextTask : item));
      fetchAnalysisTaskExecution(taskKey).then((result) => setExecutionEvents(result.items)).catch(() => undefined);
    });
    events.addEventListener("done", () => {
      events.close();
      loadTasks(true).catch((err: unknown) => {
        setMessage(err instanceof Error ? err.message : "任务刷新失败");
      });
    });
    events.onerror = () => {
      events.close();
    };
    return () => events.close();
  }, [selectedTask?.task_key, selectedTask?.status]);

  useEffect(() => {
    if (selectedRun?.snapshot_id) {
      openSnapshot(selectedRun.snapshot_id).catch((err: unknown) => {
        setMessage(err instanceof Error ? err.message : "快照详情加载失败");
      });
    }
  }, [selectedRun?.snapshot_id]);

  async function openTask(task: AnalysisTask, options: { resetReport?: boolean } = {}) {
    const { resetReport = true } = options;
    setSelectedTask(task);
    setTaskDetailOpen(true);
    if (resetReport) {
      setReportDetail(null);
    }
    try {
      const execution = await fetchAnalysisTaskExecution(task.task_key);
      setExecutionEvents(execution.items);
      if (task.run_key) {
        const run = await fetchAgentRun(task.run_key);
        setSelectedRun(run);
        if (run.snapshot_id) {
          await openSnapshot(run.snapshot_id);
        }
      } else {
        setSelectedRun(null);
        setSnapshotDetail(null);
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "运行详情加载失败");
    }
  }

  async function openReport(task: AnalysisTask) {
    if (!task.report_path) {
      setMessage("该任务还没有生成 Markdown 报告");
      return;
    }
    try {
      const report = await fetchAnalysisTaskReport(task.task_key);
      setReportDetail(report);
      setReportTask(task);
      setReportDialogOpen(true);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "报告读取失败");
    }
  }

  async function removeTask(task: AnalysisTask) {
    if (isTaskActive(task)) {
      setMessage("正在执行的任务不能删除");
      return;
    }
    if (!await requestConfirmation({ title: "删除任务记录", description: `删除“${taskDisplayName(task)}”？关联执行步骤和 Markdown 报告也会删除。`, confirmLabel: "删除任务" })) {
      return;
    }
    setDeletingTaskKey(task.task_key);
    try {
      await deleteAnalysisTask(task.task_key);
      setTasks((current) => current.filter((item) => item.task_key !== task.task_key));
      if (selectedTask?.task_key === task.task_key) {
        setSelectedTask(null);
        setSelectedRun(null);
        setExecutionEvents([]);
        setReportDetail(null);
        setReportTask(null);
        setReportDialogOpen(false);
        setTaskDetailOpen(false);
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "任务删除失败");
    } finally {
      setDeletingTaskKey("");
    }
  }

  async function clearFinishedTasks() {
    const finishedCount = tasks.filter((item) => !isTaskActive(item)).length;
    if (!finishedCount) {
      setMessage("没有可清空的已结束任务");
      return;
    }
    if (!await requestConfirmation({ title: "清空任务记录", description: `清空 ${finishedCount} 条已结束任务记录？关联执行步骤和 Markdown 报告也会删除，正在执行的任务会保留。`, confirmLabel: "清空记录" })) {
      return;
    }
    setClearingTasks(true);
    try {
      const result = await clearFinishedAnalysisTasks();
      setMessage(`已清空 ${result.deleted_count} 条任务记录`);
      setSelectedTask(null);
      setSelectedRun(null);
      setExecutionEvents([]);
      setReportDetail(null);
      setReportTask(null);
      setReportDialogOpen(false);
      setTaskDetailOpen(false);
      await loadTasks();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "任务清空失败");
    } finally {
      setClearingTasks(false);
    }
  }

  async function openSnapshot(snapshotId: number) {
    if (!snapshotId) {
      return;
    }
    try {
      setSnapshotDetail(await fetchDataSnapshot(snapshotId));
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "快照详情加载失败");
    }
  }

  return (
    <div className="page-grid reports-layout">
      <div className="main-column">
        {message ? <div className="notice">{message}</div> : null}
        <Panel
          title="分析任务队列"
          actions={
            <div className="row-actions">
              <button className="btn btn-danger" disabled={clearingTasks || !tasks.some((item) => !isTaskActive(item))} onClick={clearFinishedTasks} type="button">{clearingTasks ? "清空中" : "清空已结束"}</button>
              <button className="btn btn-primary" onClick={() => loadTasks()} type="button">刷新</button>
            </div>
          }
        >
          <div className="table-wrap">
            <table>
              <thead><tr><th>任务</th><th>分析问题</th><th>工作流</th><th>状态</th><th>阶段</th><th>进度</th><th>操作</th></tr></thead>
              <tbody>
                {tasks.map((task) => (
                  <tr className={selectedTask?.task_key === task.task_key ? "row-active" : ""} key={task.task_key} onClick={() => openTask(task)}>
                    <td className="mono">{task.task_key}</td>
                    <td>{taskDisplayName(task)}</td>
                    <td>{workflowNames[task.mode] ?? task.mode}</td>
                    <td><StatusBadge tone={task.status === "completed" ? "green" : task.status === "running" ? "amber" : "red"}>{task.status}</StatusBadge></td>
                    <td>{task.stage}</td>
                    <td>
                      <div className="progress-cell"><span style={{ width: `${task.progress}%` }} /></div>
                    </td>
                    <td>
                      <div className="row-actions">
                        <button className="btn btn-table" onClick={(event) => { event.stopPropagation(); openTask(task); }} type="button">详情</button>
                        <button className="btn btn-table" disabled={!task.snapshot_id} onClick={(event) => { event.stopPropagation(); task.snapshot_id && openSnapshot(task.snapshot_id); }} type="button">快照</button>
                        <button className="icon-btn danger" disabled={isTaskActive(task) || deletingTaskKey === task.task_key} onClick={(event) => { event.stopPropagation(); removeTask(task); }} title={isTaskActive(task) ? "任务执行中，暂不能删除" : "删除任务记录"} type="button"><Trash2 size={15} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {tasks.length === 0 ? <div className="empty-hint">暂无分析任务</div> : null}
          </div>
        </Panel>

        {taskDetailOpen ? <div className="modal-backdrop" role="presentation" onMouseDown={() => setTaskDetailOpen(false)}>
          <section className="modal-dialog task-detail-dialog" aria-modal="true" aria-labelledby="task-detail-title" role="dialog" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-dialog-header">
              <div><h2 id="task-detail-title">{selectedTask ? taskDisplayName(selectedTask) : "任务详情"}</h2><p className="mono">{selectedTask?.task_key ?? ""}</p></div>
              <button className="icon-btn" onClick={() => setTaskDetailOpen(false)} title="关闭" type="button"><X size={16} /></button>
            </div>
            <div className="modal-dialog-body task-detail-dialog-body">
          {selectedRun ? (
            <>
              <div className="report-block">
                <div>
                  <span className="label">最终结论</span>
                  <h3>{String(selectedRun.result.conclusion ?? "工具编排完成")}</h3>
                  <p>成功工具 {String(selectedRun.result.tool_success_count ?? 0)} 个，失败工具 {String(selectedRun.result.tool_failed_count ?? 0)} 个。运行编号 {selectedRun.run_key}。</p>
                  <button className="link-button mono" onClick={() => openSnapshot(selectedRun.snapshot_id)} type="button">
                    snapshot #{selectedRun.snapshot_id} · {String(selectedRun.result.snapshot_summary ?? "")}
                  </button>
                </div>
                <StatusBadge tone={Number(selectedRun.result.confidence ?? 0) >= 80 ? "green" : "amber"}>置信度 {String(selectedRun.result.confidence ?? 0)}%</StatusBadge>
              </div>
              {selectedTask ? (
                <div className="task-summary task-detail-summary">
                  <div><span>任务编号</span><strong className="mono">{selectedTask.task_key}</strong></div>
                  <div><span>状态阶段</span><strong>{selectedTask.status} · {selectedTask.stage}</strong></div>
                  <div><span>报告文件</span><strong>{selectedTask.report_path ? "Markdown 已生成" : "未生成"}</strong></div>
                  <div className="task-question"><span>分析问题</span><strong>{selectedTask.query || "未提供分析问题"}</strong></div>
                </div>
              ) : null}
              {selectedTask?.error_message ? <div className="notice error">任务错误：{selectedTask.error_message}</div> : null}
              {selectedTask ? <TaskExecutionTree workflow={selectedTask.workflow} events={executionEvents} /> : null}
              <SnapshotDetail snapshot={snapshotDetail} />
            </>
          ) : selectedTask ? <TaskExecutionTree workflow={selectedTask.workflow} events={executionEvents} /> : <div className="empty-hint">点击任务的“详情”查看执行计划、阶段记录和结果</div>}
            </div>
          </section>
        </div> : null}
      </div>

      <Panel title="报告归档">
        {tasks.filter((item) => item.report_path).slice(0, 8).map((item) => (
          <div className="archive-row" key={item.task_key}>
            <strong>{taskDisplayName(item)} · {workflowNames[item.mode] ?? item.mode}</strong>
            <span>{formatDateTime(item.created_at)} · {item.status} · snapshot #{item.snapshot_id || "-"}</span>
            <div>
              <button className="btn btn-secondary" onClick={() => openReport(item)} type="button">Markdown</button>
              <button className="btn btn-secondary" disabled type="button">PDF</button>
            </div>
          </div>
        ))}
        {tasks.filter((item) => item.report_path).length === 0 ? <div className="empty-hint">生成报告后会出现在这里</div> : null}
      </Panel>
      {reportDialogOpen && reportDetail ? (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setReportDialogOpen(false)}>
          <section className="modal-dialog markdown-report-dialog" aria-modal="true" aria-labelledby="markdown-report-title" role="dialog" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-dialog-header">
              <div><h2 id="markdown-report-title">{reportTask ? taskDisplayName(reportTask) : "分析报告"}</h2><p>{reportDetail.task_key} · Markdown</p></div>
              <div className="panel-actions"><a className="btn btn-secondary" href={analysisTaskReportDownloadUrl(reportDetail.task_key)}>下载</a><button className="icon-btn" onClick={() => setReportDialogOpen(false)} title="关闭" type="button"><X size={16} /></button></div>
            </div>
            <div className="modal-dialog-body markdown-report-body"><pre>{reportDetail.content}</pre></div>
          </section>
        </div>
      ) : null}
      {confirmDialog}
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

function taskDisplayName(task: AnalysisTask): string {
  const firstLine = task.query.split("\n").map((line) => line.trim()).find(Boolean);
  return firstLine || "未命名分析任务";
}

function formatStepPayload(value: Record<string, unknown>): string {
  return Object.keys(value).length > 0 ? JSON.stringify(value, null, 2) : "无";
}

function TaskExecutionTree({ workflow, events }: { workflow: Record<string, unknown>; events: AnalysisTaskExecutionEvent[] }) {
  const agents = Array.isArray(workflow.agents) ? workflow.agents.filter(isWorkflowAgent) : [];
  const agentByKey = new Map(agents.map((agent) => [agent.key, agent]));
  const planSteps = Array.isArray(workflow.steps)
    ? workflow.steps.filter(isWorkflowPlanStep).sort((left, right) => left.order - right.order)
    : [];
  const stages = (planSteps.length > 0
    ? planSteps
    : agents.map((agent, index) => ({
        order: index + 1,
        agent_key: agent.key,
        phase: agent.phase ?? "specialist_analysis",
        depends_on: [] as string[],
        output_contract: "",
      }))
  ).map((step) => ({
    step,
    agent: agentByKey.get(step.agent_key) ?? {
      key: step.agent_key,
      name: step.agent_key,
      model: "",
      prompt_version: 0,
      tools: [],
      phase: step.phase,
    },
    events: events.filter((event) => event.agent_key === step.agent_key),
  }));
  const plannedKeys = new Set(stages.map((stage) => stage.agent.key));
  const lifecycleEvents = events.filter((event) => !event.agent_key);
  const unmatchedEvents = events.filter((event) => event.agent_key && !plannedKeys.has(event.agent_key));
  const completedStages = stages.filter((stage) => stageExecutionState(stage.events).status === "completed").length;

  if (stages.length === 0 && events.length === 0) {
    return <div className="empty-hint">执行计划和阶段记录将在任务启动后显示。</div>;
  }

  return (
    <section className="task-execution-tree" aria-label="执行计划与记录">
      <div className="task-trace-header">
        <strong>执行计划与记录</strong>
        <span>配置版本 {String(workflow.version ?? 1)} · {completedStages}/{stages.length} 阶段完成 · {events.length} 条记录</span>
      </div>

      {lifecycleEvents.length > 0 ? (
        <details className="execution-tree-lifecycle" open={lifecycleEvents.some((event) => event.status === "failed")}>
          <summary>
            <span className="execution-tree-marker">0</span>
            <span className="task-step-name"><strong>任务生命周期</strong><small>启动、报告归档和任务终态</small></span>
            <span>{lifecycleEvents.length} 条</span>
          </summary>
          <div className="execution-tree-events">
            {lifecycleEvents.map((event) => <TaskExecutionEventNode event={event} key={event.id} />)}
          </div>
        </details>
      ) : null}

      <div className="execution-tree-stages">
        {stages.map(({ step, agent, events: stageEvents }) => {
          const state = stageExecutionState(stageEvents);
          const dependencyText = step.depends_on.length > 0 ? `依赖：${step.depends_on.map((key) => agentByKey.get(key)?.name || key).join("、")}` : "起始阶段";
          return (
            <details className={`execution-tree-stage ${state.status}`} key={`${step.order}-${agent.key}`} open={state.status === "failed" || state.status === "running"}>
              <summary>
                <span className="execution-tree-marker">{step.order}</span>
                <span className="task-step-name">
                  <strong>{agent.name || agent.key}</strong>
                  <small>{dependencyText} · Prompt v{agent.prompt_version || "-"} · {agent.model || "默认模型"} · {stageEvents.length} 条记录</small>
                </span>
                <StatusBadge tone={executionStatusTone(state.status)}>{state.label}</StatusBadge>
              </summary>
              <div className="execution-stage-plan">
                <span>{step.phase === "final_synthesis" ? "最终汇总" : "专业分析"}</span>
                <span>{agent.tools.length} 项授权工具</span>
                <span className="mono">{step.output_contract || "stage_artifact"}</span>
              </div>
              <div className="execution-tree-events">
                {stageEvents.map((event) => <TaskExecutionEventNode event={event} key={event.id} />)}
                {stageEvents.length === 0 ? <div className="empty-hint">该阶段尚未开始执行。</div> : null}
              </div>
            </details>
          );
        })}
      </div>

      {unmatchedEvents.length > 0 ? (
        <details className="execution-tree-lifecycle">
          <summary>
            <span className="execution-tree-marker">+</span>
            <span className="task-step-name"><strong>计划外记录</strong><small>未匹配到冻结执行计划的历史事件</small></span>
            <span>{unmatchedEvents.length} 条</span>
          </summary>
          <div className="execution-tree-events">
            {unmatchedEvents.map((event) => <TaskExecutionEventNode event={event} key={event.id} />)}
          </div>
        </details>
      ) : null}
    </section>
  );
}

function TaskExecutionEventNode({ event }: { event: AnalysisTaskExecutionEvent }) {
  return (
    <details className={event.status === "failed" ? "task-event failed" : "task-event"} open={event.status === "failed"}>
      <summary>
        <span className="task-step-number">{event.sequence}</span>
        <span className="task-step-name">
          <strong>{executionEventLabel(event)}</strong>
          <small>{event.tool_key || event.agent_name || "任务"} · {formatDateTime(event.created_at)}</small>
        </span>
        {event.status ? <StatusBadge tone={executionStatusTone(event.status)}>{event.status}</StatusBadge> : null}
      </summary>
      {event.event_type === "agent_context"
        ? <TaskAgentContext payload={event.payload} />
        : Object.keys(event.payload).length > 0 ? <pre>{formatStepPayload(event.payload)}</pre> : null}
    </details>
  );
}

function TaskAgentContext({ payload }: { payload: Record<string, unknown> }) {
  const systemPrompt = String(payload.system_prompt ?? "");
  const stepGoal = String(payload.current_step_goal ?? "");
  const requirement = String(payload.user_requirement ?? "");
  const allowedTools = Array.isArray(payload.allowed_tools) ? payload.allowed_tools.map(String) : [];
  return (
    <div className="task-agent-context">
      <div><span>用户需求</span><pre>{requirement || "无"}</pre></div>
      <div><span>当前步骤目标</span><pre>{stepGoal || "无"}</pre></div>
      <div><span>实际系统提示词</span><pre>{systemPrompt || "无"}</pre></div>
      <div><span>可用工具</span><pre>{allowedTools.length ? allowedTools.join("\n") : "无"}</pre></div>
      <div><span>上游阶段产物</span><pre>{formatStepPayload({ prior_stage_artifacts: payload.prior_stage_artifacts ?? [] })}</pre></div>
    </div>
  );
}

function stageExecutionState(events: AnalysisTaskExecutionEvent[]): { status: string; label: string } {
  const completed = [...events].reverse().find((event) => event.event_type === "agent_completed");
  if (completed) {
    if (completed.status === "failed") return { status: "failed", label: "失败" };
    if (completed.status === "partial") return { status: "partial", label: "部分完成" };
    return { status: "completed", label: "已完成" };
  }
  if (events.some((event) => event.status === "failed")) return { status: "failed", label: "失败" };
  if (events.some((event) => event.event_type === "agent_started")) return { status: "running", label: "执行中" };
  return { status: "pending", label: "等待" };
}

function executionStatusTone(status: string): "green" | "amber" | "red" | "neutral" {
  if (status === "failed") return "red";
  if (status === "running" || status === "retrying" || status === "partial") return "amber";
  if (status === "completed" || status === "success" || status === "ready") return "green";
  return "neutral";
}

function isWorkflowPlanStep(value: unknown): value is { order: number; agent_key: string; phase: string; depends_on: string[]; output_contract: string } {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return typeof item.order === "number"
    && typeof item.agent_key === "string"
    && Array.isArray(item.depends_on);
}


function isWorkflowAgent(value: unknown): value is { key: string; name: string; model: string; prompt_version: number; tools: unknown[]; phase?: string } {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return typeof item.key === "string" && Array.isArray(item.tools);
}

function executionEventLabel(event: AnalysisTaskExecutionEvent): string {
  const labels: Record<string, string> = {
    task_started: "任务已启动",
    agent_started: "Agent 已启动",
    agent_context: "Agent 上下文与提示词",
    model_response: "模型响应",
    tool_started: "工具调用开始",
    tool_completed: "工具调用完成",
    agent_completed: "Agent 已完成",
    report_validated: "最终报告校验通过",
    report_saved: "最终报告已保存",
    task_completed: "任务已完成",
    task_failed: "任务失败"
  };
  return labels[event.event_type] ?? event.event_type;
}

function SettingsPage() {
  const [section, setSection] = useState<"home" | "general" | "models" | "data" | "security">("home");
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [modelSecrets, setModelSecrets] = useState<Record<string, string>>({});
  const [savingModels, setSavingModels] = useState(false);
  const [modelMessage, setModelMessage] = useState("");
  const { requestConfirmation, confirmDialog } = useConfirmDialog();

  useEffect(() => {
    fetchModelConfigs().then((result) => setModels(result.items)).catch((err: unknown) => setModelMessage(err instanceof Error ? err.message : "模型配置加载失败"));
  }, []);

  function updateModelRow(key: string, patch: Partial<ModelConfig>) {
    setModels((items) => items.map((item) => item.key === key ? { ...item, ...patch } : item));
  }

  function addModel(capability: ModelCapability) {
    const key = `${capability}_${Date.now()}`;
    setModels((items) => [...items, { id: 0, key, name: capability === "chat" ? "新对话模型" : capability === "embedding" ? "新 Embedding 模型" : "新 Rerank 模型", capability, model: "", base_url: "https://api.example.com/v1", api_key_configured: false, api_key_masked: "", timeout_seconds: capability === "chat" ? 45 : 30, enabled: true, is_default: !items.some((item) => item.capability === capability && item.is_default), created_at: "", updated_at: "" }]);
  }

  async function saveModels() {
    setSavingModels(true);
    setModelMessage("");
    try {
      const saved = await Promise.all(models.map((item) => {
        const payload = { name: item.name, model: item.model, base_url: item.base_url, api_key: modelSecrets[item.key] || undefined, timeout_seconds: Number(item.timeout_seconds), enabled: item.enabled, is_default: item.is_default };
        return item.id ? updateModelConfig(item.key, payload) : createModelConfig({ key: item.key, capability: item.capability, ...payload });
      }));
      setModels(saved);
      setModelSecrets({});
      setModelMessage("模型配置已保存，新的调用会立即使用默认配置。");
    } catch (err) {
      setModelMessage(err instanceof Error ? err.message : "模型配置保存失败");
    } finally {
      setSavingModels(false);
    }
  }

  async function removeModel(item: ModelConfig) {
    if (!item.id) { setModels((items) => items.filter((model) => model.key !== item.key)); return; }
    if (!await requestConfirmation({ title: "删除模型配置", description: `确定删除模型配置“${item.name}”吗？此操作不可恢复。`, confirmLabel: "删除模型" })) return;
    try { await deleteModelConfig(item.key); setModels((items) => items.filter((model) => model.key !== item.key)); } catch (err) { setModelMessage(err instanceof Error ? err.message : "模型配置删除失败"); }
  }
  const menuItems = [
    { key: "general" as const, title: "基础设置", description: "应用名称、运行环境、语言与时区" },
    { key: "models" as const, title: "模型设置", description: `${models.length} 个模型配置，含对话、Embedding 与 Rerank` },
    { key: "data" as const, title: "数据设置", description: "健康检查、缓存与数据回退" },
    { key: "security" as const, title: "安全与维护", description: "本地密钥与维护状态" }
  ];
  if (section === "home") {
    return <>{<div className="settings-menu">{menuItems.map((item) => <button className="settings-menu-row" key={item.key} onClick={() => setSection(item.key)} type="button"><div><strong>{item.title}</strong><span>{item.description}</span></div><ChevronRight size={17} /></button>)}</div>}{confirmDialog}</>;
  }
  return (
    <div className="settings-detail-page">
      <button className="btn btn-secondary settings-back" onClick={() => setSection("home")} type="button"><ChevronLeft size={15} />返回设置</button>
      {section === "general" ? <Panel title="基础设置">
        <div className="settings-list">
          <label>应用名称<input className="input" defaultValue="A 股交易智能体" /></label>
          <label>运行环境<select className="input" defaultValue="local-desktop"><option value="local-desktop">本地桌面</option><option value="development">开发环境</option></select></label>
          <label>语言<select className="input" defaultValue="zh-CN"><option value="zh-CN">简体中文</option></select></label>
          <label>时区<input className="input" defaultValue="Asia/Shanghai" /></label>
        </div>
      </Panel> : null}

      {section === "models" ? <Panel title="模型设置" description="每类模型可配置多个实例，勾选默认项后由 Agent、知识库检索和重排服务实际调用。" actions={<div className="panel-actions"><button className="btn btn-secondary" onClick={() => addModel("chat")} type="button">添加对话模型</button><button className="btn btn-secondary" onClick={() => addModel("embedding")} type="button">添加 Embedding</button><button className="btn btn-secondary" onClick={() => addModel("rerank")} type="button">添加 Rerank</button><button className="btn btn-primary" disabled={savingModels} onClick={() => void saveModels()} type="button">{savingModels ? "保存中" : "保存模型配置"}</button></div>}>
        {modelMessage ? <div className={modelMessage.startsWith("模型配置已") ? "notice success" : "notice error"}>{modelMessage}</div> : null}
        <div className="model-settings-list">
          {(["chat", "embedding", "rerank"] as ModelCapability[]).map((capability) => <section className="model-capability-group" key={capability}><div className="model-capability-head"><strong>{capability === "chat" ? "对话与 Tool Calling" : capability === "embedding" ? "Embedding 向量化" : "Rerank 重排"}</strong><span>{capability === "chat" ? "用于 Agent 对话与分析任务" : capability === "embedding" ? "用于知识库向量索引和语义召回" : "用于知识库召回结果重排，可选"}</span></div>{models.filter((item) => item.capability === capability).map((item) => <div className="model-settings-row expanded" key={item.key}><label>名称<input className="input" value={item.name} onChange={(event) => updateModelRow(item.key, { name: event.target.value })} /></label><label>模型 ID<input className="input mono" value={item.model} onChange={(event) => updateModelRow(item.key, { model: event.target.value })} /></label><label>API Base<input className="input mono" value={item.base_url} onChange={(event) => updateModelRow(item.key, { base_url: event.target.value })} /></label><label>API Key<input className="input" onChange={(event) => setModelSecrets((items) => ({ ...items, [item.key]: event.target.value }))} placeholder={item.api_key_configured ? `已配置：${item.api_key_masked}` : "输入密钥后保存"} type="password" value={modelSecrets[item.key] ?? ""} /></label><label>超时秒数<input className="input mono" min="5" onChange={(event) => updateModelRow(item.key, { timeout_seconds: Number(event.target.value) })} type="number" value={item.timeout_seconds} /></label><label className="check-line"><input checked={item.enabled} onChange={(event) => updateModelRow(item.key, { enabled: event.target.checked })} type="checkbox" /><span>启用</span></label><label className="check-line"><input checked={item.is_default} onChange={(event) => setModels((items) => items.map((model) => model.capability === capability ? { ...model, is_default: model.key === item.key ? event.target.checked : false } : model))} type="checkbox" /><span>默认</span></label><button className="icon-btn" onClick={() => void removeModel(item)} title="删除模型" type="button"><Trash2 size={15} /></button></div>)}</section>)}
        </div>
      </Panel> : null}

      {section === "data" ? <Panel title="数据设置">
        <div className="settings-list">
          <label className="check-line"><input defaultChecked type="checkbox" /><span>启动时自动健康检查数据源</span></label>
          <label className="check-line"><input defaultChecked type="checkbox" /><span>启用本地缓存和失败回退</span></label>
          <label className="check-line"><input type="checkbox" /><span>强制实时行情绕过缓存</span></label>
        </div>
      </Panel> : null}

      {section === "security" ? <Panel title="安全与维护">
        <div className="security-row">
          <ShieldCheck size={22} />
          <div>
            <strong>本地密钥加密已启用</strong>
            <span>不包含用户、角色或权限管理，仅维护本机运行配置。</span>
          </div>
        </div>
      </Panel> : null}
      {confirmDialog}
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
    case "multi_agent":
      return <AssistedAnalysisPage />;
    case "agents":
      return <AgentManagementPage />;
    case "tools":
      return <ToolManagementPage />;
    case "skills":
      return <SkillManagementPage />;
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
            {activeMeta.subtitle ? <p>{activeMeta.subtitle}</p> : null}
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
