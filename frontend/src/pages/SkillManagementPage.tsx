import { Plus, RefreshCw, Save, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import {
  createAgentSkill,
  deleteAgentSkill,
  fetchAgents,
  fetchAgentSkills,
  updateAgentSkill,
  type AgentConfig,
  type AgentSkill
} from "../api/client";
import { useConfirmDialog } from "../components/ConfirmDialog";

type SkillForm = Pick<AgentSkill, "key" | "name" | "description" | "instruction" | "enabled" | "agent_keys">;

const emptySkill = (): SkillForm => ({ key: "", name: "", description: "", instruction: "", enabled: true, agent_keys: [] });

export function SkillManagementPage() {
  const [skills, setSkills] = useState<AgentSkill[]>([]);
  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [selectedKey, setSelectedKey] = useState("");
  const [form, setForm] = useState<SkillForm>(emptySkill());
  const [isNew, setIsNew] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const { requestConfirmation, confirmDialog } = useConfirmDialog();

  async function load(selected?: string) {
    try {
      const [skillResult, agentResult] = await Promise.all([fetchAgentSkills(), fetchAgents()]);
      setSkills(skillResult.items);
      setAgents(agentResult.items);
      const key = selected ?? selectedKey;
      const skill = skillResult.items.find((item) => item.key === key) ?? skillResult.items[0];
      if (skill) {
        setSelectedKey(skill.key);
        setForm({ key: skill.key, name: skill.name, description: skill.description, instruction: skill.instruction, enabled: skill.enabled, agent_keys: skill.agent_keys });
        setIsNew(false);
      } else {
        setSelectedKey("");
        setForm(emptySkill());
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Skill 加载失败");
    }
  }

  useEffect(() => { void load(); }, []);

  function selectSkill(skill: AgentSkill) {
    setSelectedKey(skill.key);
    setForm({ key: skill.key, name: skill.name, description: skill.description, instruction: skill.instruction, enabled: skill.enabled, agent_keys: skill.agent_keys });
    setIsNew(false);
    setMessage("");
  }

  function startNew() {
    setSelectedKey("");
    setForm(emptySkill());
    setIsNew(true);
    setMessage("");
  }

  async function save() {
    if (!form.key.trim() || !form.name.trim()) {
      setMessage("请填写 Skill key 和名称");
      return;
    }
    setSaving(true);
    try {
      const saved = isNew
        ? await createAgentSkill(form)
        : await updateAgentSkill(form.key, { name: form.name, description: form.description, instruction: form.instruction, enabled: form.enabled, agent_keys: form.agent_keys });
      setMessage(`已保存 ${saved.name}`);
      await load(saved.key);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Skill 保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (isNew || !selectedKey || !await requestConfirmation({ title: "删除 Skill", description: `确定删除 Skill “${form.name}”吗？此操作不可恢复。`, confirmLabel: "删除 Skill" })) return;
    try {
      await deleteAgentSkill(selectedKey);
      setMessage("Skill 已删除");
      await load("");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Skill 删除失败");
    }
  }

  function toggleAgent(agentKey: string, checked: boolean) {
    setForm((current) => ({ ...current, agent_keys: checked ? [...new Set([...current.agent_keys, agentKey])] : current.agent_keys.filter((key) => key !== agentKey) }));
  }

  return (
    <div className="page-grid skill-management-layout">
      <aside className="side-column">
        <section className="panel">
          <div className="panel-titlebar"><div><h2>Skill 列表</h2><p>{skills.length} 项可复用能力</p></div><div className="panel-actions"><button className="icon-btn" onClick={() => void load()} title="刷新" type="button"><RefreshCw size={15} /></button><button className="icon-btn" onClick={startNew} title="新建 Skill" type="button"><Plus size={15} /></button></div></div>
          <div className="skill-list">{skills.map((skill) => <button className={selectedKey === skill.key && !isNew ? "active" : ""} key={skill.key} onClick={() => selectSkill(skill)} type="button"><strong>{skill.name}</strong><span>{skill.key}</span><small>{skill.enabled ? "已启用" : "已停用"} · {skill.agent_keys.length} 个 Agent · 已使用 {skill.usage_count} 次</small></button>)}{!skills.length ? <div className="empty-hint">暂无 Skill</div> : null}</div>
        </section>
      </aside>
      <section className="panel skill-editor">
        <div className="panel-titlebar"><div><h2>{isNew ? "新建 Skill" : form.name || "Skill 配置"}</h2><p>Skill 会作为可复用行为约束注入已分配 Agent 的模型上下文。</p></div><div className="panel-actions">{!isNew ? <button className="icon-btn" onClick={() => void remove()} title="删除 Skill" type="button"><Trash2 size={15} /></button> : null}<button className="btn btn-primary" disabled={saving} onClick={() => void save()} type="button"><Save size={15} />{saving ? "保存中" : "保存"}</button></div></div>
        {message ? <div className={message.startsWith("已") ? "notice success" : "notice error"}>{message}</div> : null}
        <div className="skill-form">
          <div className="form-grid two"><label>Skill key<input className="input mono" disabled={!isNew} onChange={(event) => setForm({ ...form, key: event.target.value })} placeholder="例如 evidence_first" value={form.key} /></label><label>名称<input className="input" onChange={(event) => setForm({ ...form, name: event.target.value })} value={form.name} /></label></div>
          <label>说明<textarea className="textarea" onChange={(event) => setForm({ ...form, description: event.target.value })} value={form.description} /></label>
          <label>执行指令<textarea className="textarea skill-instruction" onChange={(event) => setForm({ ...form, instruction: event.target.value })} placeholder="写入模型必须遵守的工作方法、证据标准和输出要求。" value={form.instruction} /></label>
          <label className="check-line"><input checked={form.enabled} onChange={(event) => setForm({ ...form, enabled: event.target.checked })} type="checkbox" /><span>启用此 Skill</span></label>
          <div className="skill-assignment"><strong>分配给 Agent</strong><div>{agents.map((agent) => <label className="check-line" key={agent.key}><input checked={form.agent_keys.includes(agent.key)} onChange={(event) => toggleAgent(agent.key, event.target.checked)} type="checkbox" /><span>{agent.name}</span><small>{agent.key}</small></label>)}</div></div>
        </div>
      </section>
      {confirmDialog}
    </div>
  );
}
