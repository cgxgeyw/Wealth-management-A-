import { Braces, RefreshCw, Wrench } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { fetchAgents, fetchAgentToolAudit, fetchAgentTools, type AgentConfig, type AgentToolAudit, type AgentToolSpec } from "../api/client";

function StatusBadge({ tone, children }: { tone: "green" | "amber" | "neutral"; children: React.ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function ToolManagementPage() {
  const [tools, setTools] = useState<AgentToolSpec[]>([]);
  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [audit, setAudit] = useState<Record<string, AgentToolAudit>>({});
  const [category, setCategory] = useState("all");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  async function load() {
    setLoading(true);
    try {
      const [toolResult, agentResult, auditResult] = await Promise.all([fetchAgentTools(), fetchAgents(), fetchAgentToolAudit()]);
      setTools(toolResult.items);
      setAgents(agentResult.items);
      setAudit(Object.fromEntries(auditResult.items.map((item) => [item.tool_key, item])));
      setMessage("");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "工具注册表加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  const categories = useMemo(() => ["all", ...Array.from(new Set(tools.map((item) => item.category))).sort()], [tools]);
  const normalized = query.trim().toLowerCase();
  const visibleTools = tools.filter((tool) =>
    (category === "all" || tool.category === category)
    && (!normalized || `${tool.name} ${tool.key} ${tool.description}`.toLowerCase().includes(normalized))
  );

  return (
    <div className="page-grid tool-management-layout">
      <aside className="side-column">
        <section className="panel">
          <div className="panel-titlebar"><div><h2>工具分类</h2><p>{tools.length} 项已注册</p></div></div>
          <div className="management-filter-list">
            {categories.map((item) => <button className={category === item ? "active" : ""} key={item} onClick={() => setCategory(item)} type="button">{item === "all" ? "全部工具" : item}</button>)}
          </div>
        </section>
      </aside>
      <section className="panel tool-management-main">
        <div className="panel-titlebar">
          <div><h2>工具注册表</h2><p>工具执行器和 Schema 由后端注册，Agent 授权关系在此集中审阅。</p></div>
          <div className="panel-actions"><button className="icon-btn" disabled={loading} onClick={() => void load()} title="刷新注册表" type="button"><RefreshCw className={loading ? "spin" : ""} size={15} /></button></div>
        </div>
        <div className="tool-management-search"><input className="input" onChange={(event) => setQuery(event.target.value)} placeholder="搜索名称、tool_key 或说明" value={query} /></div>
        {message ? <div className="notice error">{message}</div> : null}
        <div className="tool-registry-list">
          {visibleTools.map((tool) => {
            const authorizedAgents = agents.filter((agent) => agent.tools.includes(tool.key));
            const toolAudit = audit[tool.key];
            return (
              <details className="tool-registry-row" key={tool.key}>
                <summary>
                  <span className="tool-registry-icon"><Wrench size={15} /></span>
                  <div><strong>{tool.name}</strong><small>{tool.key} · {tool.category}</small></div>
                  <StatusBadge tone={tool.enabled ? "green" : "amber"}>{tool.enabled ? "可执行" : "未启用"}</StatusBadge>
                  <span>{toolAudit ? `${toolAudit.total} 次调用 · ${toolAudit.failures} 失败` : `${authorizedAgents.length} 个 Agent`}</span>
                </summary>
                <div className="tool-registry-detail">
                  <p>{tool.description}</p>
                  <div className="tool-schema-grid">
                    <div><span>输入 Schema</span><pre>{JSON.stringify(tool.input_schema, null, 2)}</pre></div>
                    <div><span>输出 Schema</span><pre>{JSON.stringify(tool.output_schema, null, 2)}</pre></div>
                  </div>
                  <div className="tool-agent-grants"><span>已授权 Agent</span>{authorizedAgents.length ? authorizedAgents.map((agent) => <b key={agent.key}>{agent.name}</b>) : <small>暂无授权</small>}</div>
                  {toolAudit?.last_error ? <div className="notice error">最近错误：{toolAudit.last_error}</div> : null}
                </div>
              </details>
            );
          })}
          {!visibleTools.length ? <div className="empty-hint">没有匹配的工具</div> : null}
        </div>
      </section>
      <aside className="side-column">
        <section className="panel"><div className="panel-titlebar"><div><h2>管理边界</h2></div></div><div className="management-note"><Braces size={17} /><p>工具的执行代码与输入输出 Schema 必须随服务发布，避免在界面中创建无法执行的伪工具。</p></div></section>
      </aside>
    </div>
  );
}
