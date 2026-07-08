import { CheckCircle2, ChevronDown, ChevronRight, Edit3, PlayCircle, RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  clearDataCache,
  fetchDataFetchLogs,
  fetchDataAlerts,
  fetchDataQuality,
  fetchDataProviders,
  fetchDataRoutes,
  fetchProviderCredentials,
  fetchScheduledTaskRuns,
  fetchScheduledTasks,
  saveProviderCredential,
  runScheduledTask,
  runDataHealthCheck,
  updateDataProvider,
  type DataAlertItem,
  type DataFetchLog,
  type DataProvider,
  type DataProviderCredential,
  type DataQualityItem,
  type DataRoute,
  type ScheduledTask,
  type ScheduledTaskRun
} from "../api/client";

const TIME_FORMATTER = new Intl.DateTimeFormat("zh-CN", {
  timeZone: "Asia/Shanghai",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false
});

function StatusBadge({ tone = "neutral", children }: { tone?: string; children: React.ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    healthy: "正常",
    degraded: "降级",
    rate_limited: "限流",
    auth_required: "需要密钥",
    auth_failed: "密钥错误",
    stale: "过期",
    schema_changed: "字段变化",
    disabled: "禁用",
    unavailable: "不可用",
    success: "成功",
    failed: "失败",
    unknown: "未知"
  };
  return labels[status] ?? status;
}

function statusTone(status: string): string {
  if (["healthy", "success"].includes(status)) return "green";
  if (["degraded", "rate_limited", "auth_required", "stale", "schema_changed", "disabled"].includes(status)) return "amber";
  if (["auth_failed", "unavailable", "failed"].includes(status)) return "red";
  return "neutral";
}

function formatTime(value: string | null): string {
  if (!value) return "-";
  const normalized = /[zZ]|[+-]\d{2}:\d{2}$/.test(value) ? value : `${value}Z`;
  return TIME_FORMATTER.format(new Date(normalized));
}

function formatInterval(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}min`;
  return `${Math.round(seconds / 3600)}h`;
}

function Metric({ label, value, meta }: { label: string; value: string; meta: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{meta}</small>
    </div>
  );
}

function Panel({
  title,
  description,
  actions,
  children
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panel-titlebar">
        <div>
          <h2>{title}</h2>
          {description ? <p>{description}</p> : null}
        </div>
        {actions ? <div className="panel-actions">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}

export function DataSourcesPage() {
  const [providers, setProviders] = useState<DataProvider[]>([]);
  const [routes, setRoutes] = useState<DataRoute[]>([]);
  const [logs, setLogs] = useState<DataFetchLog[]>([]);
  const [qualityItems, setQualityItems] = useState<DataQualityItem[]>([]);
  const [alerts, setAlerts] = useState<DataAlertItem[]>([]);
  const [scheduledTasks, setScheduledTasks] = useState<ScheduledTask[]>([]);
  const [scheduledRuns, setScheduledRuns] = useState<ScheduledTaskRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [runningTaskKey, setRunningTaskKey] = useState("");
  const [message, setMessage] = useState("");
  const [selectedKey, setSelectedKey] = useState("");
  const [showRoutes, setShowRoutes] = useState(false);
  const [credentials, setCredentials] = useState<DataProviderCredential[]>([]);
  const [providerForm, setProviderForm] = useState({
    name: "",
    enabled: true,
    auth_type: "none",
    base_url: "",
    test_url: "",
    cache_ttl_seconds: 60
  });
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [cookieInput, setCookieInput] = useState("");

  const loadData = useCallback(async () => {
    const [providerResult, routeResult, logResult, taskResult, runResult, qualityResult, alertResult] = await Promise.all([
      fetchDataProviders(),
      fetchDataRoutes(),
      fetchDataFetchLogs(),
      fetchScheduledTasks(),
      fetchScheduledTaskRuns(),
      fetchDataQuality(),
      fetchDataAlerts()
    ]);
    setProviders(providerResult.items);
    setRoutes(routeResult.items);
    setLogs(logResult.items);
    setScheduledTasks(taskResult.items);
    setScheduledRuns(runResult.items);
    setQualityItems(qualityResult.items);
    setAlerts(alertResult.items);
    setSelectedKey((current) => current || providerResult.items[0]?.key || "");
  }, []);

  useEffect(() => {
    loadData().catch((err: unknown) => {
      setMessage(err instanceof Error ? err.message : "数据加载失败");
    });
  }, [loadData]);

  const selectedProvider = providers.find((provider) => provider.key === selectedKey) ?? providers[0];

  useEffect(() => {
    if (!selectedProvider) return;
    setProviderForm({
      name: selectedProvider.name,
      enabled: selectedProvider.enabled,
      auth_type: selectedProvider.auth_type,
      base_url: selectedProvider.base_url,
      test_url: selectedProvider.test_url,
      cache_ttl_seconds: selectedProvider.cache_ttl_seconds
    });
    setApiKeyInput("");
    setCookieInput("");
  }, [selectedProvider]);

  useEffect(() => {
    if (!selectedKey) {
      setCredentials([]);
      return;
    }
    fetchProviderCredentials(selectedKey)
      .then((result) => setCredentials(result.items))
      .catch(() => setCredentials([]));
  }, [selectedKey]);

  const apiKeyCredential = credentials.find((item) => item.credential_type === "api_key");
  const cookieCredential = credentials.find((item) => item.credential_type === "cookie");

  const summary = useMemo(() => {
    const healthy = providers.filter((item) => item.health_status === "healthy").length;
    const abnormal = providers.filter((item) => item.health_status !== "healthy").length;
    const recentFailures = logs.filter((item) => ["failed", "unavailable", "auth_failed"].includes(item.status)).length;
    const cacheHits = logs.length ? Math.round((logs.filter((item) => item.cache_hit).length / logs.length) * 100) : 0;
    const activeTasks = scheduledTasks.filter((item) => item.enabled).length;
    return { healthy, abnormal, recentFailures, cacheHits, activeTasks };
  }, [logs, providers, scheduledTasks]);

  async function checkProvider(providerKey?: string) {
    setLoading(true);
    setMessage("");
    try {
      const result = await runDataHealthCheck(providerKey);
      setMessage(result.items.map((item) => `${item.provider_key}: ${statusLabel(item.status)}`).join("；"));
      await loadData();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "健康检查失败");
    } finally {
      setLoading(false);
    }
  }

  async function triggerScheduledTask(taskKey: string) {
    setRunningTaskKey(taskKey);
    setMessage("");
    try {
      const run = await runScheduledTask(taskKey);
      setMessage(`${taskKey}: ${statusLabel(run.status)}，${run.message || "已完成"}`);
      await loadData();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "定时任务执行失败");
    } finally {
      setRunningTaskKey("");
    }
  }

  async function saveProviderConfig() {
    if (!selectedProvider) return;
    setLoading(true);
    setMessage("");
    try {
      await updateDataProvider(selectedProvider.key, providerForm);
      if (apiKeyInput.trim()) {
        await saveProviderCredential(selectedProvider.key, "api_key", apiKeyInput.trim());
      }
      if (cookieInput.trim()) {
        await saveProviderCredential(selectedProvider.key, "cookie", cookieInput.trim());
      }
      setMessage("数据源配置已保存");
      await loadData();
      const credentialResult = await fetchProviderCredentials(selectedProvider.key);
      setCredentials(credentialResult.items);
      setApiKeyInput("");
      setCookieInput("");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "数据源配置保存失败");
    } finally {
      setLoading(false);
    }
  }

  async function clearCache() {
    setLoading(true);
    setMessage("");
    try {
      const result = await clearDataCache();
      setMessage(result.message || "缓存已清理");
      await loadData();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "缓存清理失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-grid data-source-layout">
      <div className="main-column">
        <div className="metrics-grid five">
          <Metric label="健康源" value={`${summary.healthy}`} meta="可直接用于任务调用" />
          <Metric label="异常源" value={`${summary.abnormal}`} meta="可能是缺密钥、网络波动或接口限流" />
          <Metric label="近期失败" value={`${summary.recentFailures}`} meta="来自最近采集日志" />
          <Metric label="缓存命中率" value={`${summary.cacheHits}%`} meta="按当前日志样本计算" />
          <Metric label="定时任务" value={`${summary.activeTasks}`} meta="全局后台采集任务" />
        </div>

        {message ? <div className="notice">{message}</div> : null}

        <Panel
          title="Provider 列表"
          description="这里是日常主要入口：看数据源是否可用、是否需要密钥、最近是否成功。"
          actions={
            <>
              <button className="btn btn-secondary" type="button">新增数据源</button>
              <button className="btn btn-primary" disabled={loading} onClick={() => checkProvider()} type="button">
                <RefreshCw size={14} />
                全部检查
              </button>
            </>
          }
        >
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>名称</th>
                  <th>Key</th>
                  <th>类型</th>
                  <th>状态</th>
                  <th>认证</th>
                  <th>TTL</th>
                  <th>最近成功</th>
                  <th>最近失败</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {providers.map((provider) => (
                  <tr className={selectedKey === provider.key ? "selected-row" : ""} key={provider.key}>
                    <td>{provider.name}</td>
                    <td className="mono">{provider.key}</td>
                    <td>{provider.type}</td>
                    <td><StatusBadge tone={statusTone(provider.health_status)}>{statusLabel(provider.health_status)}</StatusBadge></td>
                    <td>{provider.auth_type}</td>
                    <td className="mono">{provider.cache_ttl_seconds}s</td>
                    <td>{formatTime(provider.last_success_at)}</td>
                    <td>{formatTime(provider.last_failure_at)}</td>
                    <td>
                      <div className="table-actions">
                        <button className="btn btn-table" disabled={loading} onClick={() => checkProvider(provider.key)} type="button">检查</button>
                        <button className="btn btn-table" onClick={() => setSelectedKey(provider.key)} type="button">编辑</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel title="数据质量评分" description="基于健康状态、最近抓取失败、缓存命中情况自动计算。">
          <div className="table-wrap compact">
            <table>
              <thead>
                <tr>
                  <th>Provider</th>
                  <th>评分</th>
                  <th>状态</th>
                  <th>最近请求</th>
                  <th>失败</th>
                  <th>缓存命中</th>
                  <th>最近问题</th>
                </tr>
              </thead>
              <tbody>
                {qualityItems.map((item) => (
                  <tr key={item.provider_key}>
                    <td className="mono">{item.provider_key}</td>
                    <td><StatusBadge tone={item.score >= 80 ? "green" : item.score >= 60 ? "amber" : "red"}>{item.score}</StatusBadge></td>
                    <td>{statusLabel(item.health_status)}</td>
                    <td>{item.recent_total}</td>
                    <td>{item.recent_failures}</td>
                    <td>{item.cache_hits}</td>
                    <td>{item.last_message || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel
          title="定时任务"
          description="全局后台任务，不绑定用户。任务按固定间隔执行，行情刷新会避开非交易时段。"
          actions={
            <button className="btn btn-secondary" disabled={Boolean(runningTaskKey)} onClick={loadData} type="button">
              <RefreshCw size={14} />
              刷新状态
            </button>
          }
        >
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>任务</th>
                  <th>Key</th>
                  <th>间隔</th>
                  <th>启用</th>
                  <th>最近状态</th>
                  <th>最近完成</th>
                  <th>消息</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {scheduledTasks.map((task) => (
                  <tr key={task.key}>
                    <td>{task.name}</td>
                    <td className="mono">{task.key}</td>
                    <td className="mono">{formatInterval(task.interval_seconds)}</td>
                    <td>{task.enabled ? "是" : "否"}</td>
                    <td>
                      {task.last_status ? (
                        <StatusBadge tone={statusTone(task.last_status)}>{statusLabel(task.last_status)}</StatusBadge>
                      ) : "-"}
                    </td>
                    <td>{formatTime(task.last_finished_at)}</td>
                    <td>{task.last_message || "-"}</td>
                    <td>
                      <button
                        className="btn btn-table"
                        disabled={Boolean(runningTaskKey)}
                        onClick={() => triggerScheduledTask(task.key)}
                        type="button"
                      >
                        <PlayCircle size={13} />
                        {runningTaskKey === task.key ? "执行中" : "立即执行"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel title="采集日志" description="用于排查数据一致性、接口变更、限流和缓存命中情况。时间固定按东八区显示。">
          <div className="table-wrap compact">
            <table>
              <thead>
                <tr>
                  <th>时间</th>
                  <th>数据源</th>
                  <th>类别</th>
                  <th>标的</th>
                  <th>状态</th>
                  <th>HTTP</th>
                  <th>耗时</th>
                  <th>缓存</th>
                  <th>回退</th>
                  <th>错误</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td>{formatTime(log.fetched_at)}</td>
                    <td className="mono">{log.provider_key}</td>
                    <td>{log.data_category}</td>
                    <td className="mono">{log.symbol || "-"}</td>
                    <td><StatusBadge tone={statusTone(log.status)}>{statusLabel(log.status)}</StatusBadge></td>
                    <td>{log.http_status ?? "-"}</td>
                    <td>{log.latency_ms === null ? "-" : `${log.latency_ms}ms`}</td>
                    <td>{log.cache_hit ? "是" : "否"}</td>
                    <td>{log.fallback_used ? "是" : "否"}</td>
                    <td>{log.error_message || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        <section className="advanced-section">
          <button className="advanced-toggle" onClick={() => setShowRoutes((value) => !value)} type="button">
            {showRoutes ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
            高级：数据路由
            <span>只有调整主备源顺序、回退策略时才需要看</span>
          </button>
          {showRoutes ? (
            <div className="route-grid">
              {routes.map((route) => (
                <article className="route-card" key={route.id}>
                  <div className="route-title">
                    <strong>{route.data_category}</strong>
                    <StatusBadge tone={route.enabled ? "green" : "neutral"}>{route.enabled ? "启用" : "停用"}</StatusBadge>
                  </div>
                  <div className="route-tool">{route.tool_name}</div>
                  <div className="route-chain">{route.provider_chain.join(" -> ")}</div>
                  <div className="route-policy">{route.fallback_policy}</div>
                </article>
              ))}
            </div>
          ) : null}
        </section>
      </div>

      <aside className="side-column">
        <Panel title="数据源配置" description="保存后立即影响数据路由、健康检查和后台任务。">
          <div className="form-stack">
            <label>Key<input className="input mono" value={selectedProvider?.key ?? ""} readOnly /></label>
            <label>
              名称
              <input
                className="input"
                value={providerForm.name}
                onChange={(event) => setProviderForm((current) => ({ ...current, name: event.target.value }))}
              />
            </label>
            <label>
              Base URL
              <input
                className="input mono"
                value={providerForm.base_url}
                onChange={(event) => setProviderForm((current) => ({ ...current, base_url: event.target.value }))}
              />
            </label>
            <label>
              Test URL
              <input
                className="input mono"
                value={providerForm.test_url}
                onChange={(event) => setProviderForm((current) => ({ ...current, test_url: event.target.value }))}
              />
            </label>
            <label>
              认证方式
              <select
                className="input"
                value={providerForm.auth_type}
                onChange={(event) => setProviderForm((current) => ({ ...current, auth_type: event.target.value }))}
              >
                <option value="none">none</option>
                <option value="api_key">api_key</option>
                <option value="cookie">cookie</option>
              </select>
            </label>
            <label>
              API Key
              <input
                className="input"
                placeholder={apiKeyCredential?.configured ? `已配置：${apiKeyCredential.masked_value}` : "未配置，输入后保存"}
                value={apiKeyInput}
                onChange={(event) => setApiKeyInput(event.target.value)}
              />
            </label>
            <label>
              Cookie
              <input
                className="input"
                placeholder={cookieCredential?.configured ? `已配置：${cookieCredential.masked_value}` : "可选，适配需要会话的数据源"}
                value={cookieInput}
                onChange={(event) => setCookieInput(event.target.value)}
              />
            </label>
            <label>
              缓存 TTL
              <input
                className="input mono"
                min={0}
                max={86400}
                type="number"
                value={providerForm.cache_ttl_seconds}
                onChange={(event) => setProviderForm((current) => ({
                  ...current,
                  cache_ttl_seconds: Number(event.target.value)
                }))}
              />
            </label>
            <label className="check-line">
              <input
                checked={providerForm.enabled}
                type="checkbox"
                onChange={(event) => setProviderForm((current) => ({ ...current, enabled: event.target.checked }))}
              />
              <span>启用这个数据源</span>
            </label>
          </div>
          <div className="button-stack">
            <button className="btn btn-primary" disabled={loading || !selectedProvider} onClick={saveProviderConfig} type="button">
              <Edit3 size={14} />
              保存配置
            </button>
            <button className="btn btn-secondary" disabled={loading || !selectedProvider} onClick={() => selectedProvider && checkProvider(selectedProvider.key)} type="button">
              <CheckCircle2 size={14} />
              测试连接
            </button>
            <button className="btn btn-secondary" disabled={loading} onClick={clearCache} type="button">
              <Trash2 size={14} />
              清理缓存
            </button>
          </div>
        </Panel>

        <Panel title="异常告警" description="最近健康和抓取异常。">
          <div className="run-list">
            {alerts.length ? alerts.slice(0, 12).map((alert, index) => (
              <div className="run-item" key={`${alert.provider_key}-${alert.status}-${index}`}>
                <div className="run-item-title">
                  <span className="mono">{alert.provider_key}</span>
                  <StatusBadge tone={alert.severity === "high" ? "red" : "amber"}>{alert.severity}</StatusBadge>
                </div>
                <div className="run-item-meta">
                  <span>{alert.status || "-"}</span>
                  <span>{formatTime(alert.fetched_at)}</span>
                </div>
                <p>{alert.message}</p>
              </div>
            )) : (
              <div className="empty-hint">暂无异常告警</div>
            )}
          </div>
        </Panel>

        <Panel title="任务执行记录" description="最近 20 次后台任务运行结果。">
          <div className="run-list">
            {scheduledRuns.length ? scheduledRuns.map((run) => (
              <div className="run-item" key={run.id}>
                <div className="run-item-title">
                  <span className="mono">{run.task_key}</span>
                  <StatusBadge tone={statusTone(run.status)}>{statusLabel(run.status)}</StatusBadge>
                </div>
                <div className="run-item-meta">
                  <span>{formatTime(run.finished_at ?? run.started_at)}</span>
                  <span>{run.duration_ms === null ? "-" : `${run.duration_ms}ms`}</span>
                </div>
                <p>{run.message || "-"}</p>
              </div>
            )) : (
              <div className="empty-hint">还没有任务运行记录</div>
            )}
          </div>
        </Panel>
      </aside>
    </div>
  );
}
