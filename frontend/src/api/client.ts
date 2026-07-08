export interface HealthResponse {
  status: string;
  app_name: string;
  environment: string;
  timestamp: string;
}

export interface ModuleItem {
  key: string;
  name: string;
  status: string;
}

export interface ModuleListResponse {
  items: ModuleItem[];
}

export interface AgentConfig {
  id: number;
  key: string;
  name: string;
  role: string;
  description: string;
  model: string;
  temperature: number;
  max_tokens: number;
  enabled: boolean;
  system_prompt: string;
  task_prompt: string;
  output_schema: string;
  variables: string[];
  tools: string[];
  current_version: number;
  updated_at: string;
}

export interface AgentListResponse {
  items: AgentConfig[];
}

export interface AgentUpdatePayload {
  name?: string;
  role?: string;
  description?: string;
  model?: string;
  temperature?: number;
  max_tokens?: number;
  enabled?: boolean;
  system_prompt?: string;
  task_prompt?: string;
  output_schema?: string;
  variables?: string[];
  tools?: string[];
  change_note?: string;
}

export interface AgentPromptVersion {
  id: number;
  agent_key: string;
  version: number;
  system_prompt: string;
  task_prompt: string;
  output_schema: string;
  variables: string[];
  tools: string[];
  change_note: string;
  created_at: string;
}

export interface AgentPromptVersionListResponse {
  items: AgentPromptVersion[];
}

export interface AgentRenderResponse {
  agent_key: string;
  rendered_system_prompt: string;
  rendered_task_prompt: string;
  output_schema: string;
  missing_variables: string[];
  tools: string[];
}

export interface AgentTestRunResponse {
  agent_key: string;
  status: string;
  rendered_prompt: AgentRenderResponse;
  model: string;
  estimated_tokens: number;
  output: string;
}

export interface AgentToolSpec {
  key: string;
  name: string;
  description: string;
  category: string;
  enabled: boolean;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
}

export interface AgentToolListResponse {
  items: AgentToolSpec[];
}

export interface AgentToolRunResponse {
  agent_key: string;
  tool_key: string;
  status: string;
  output: Record<string, unknown>;
  metadata: Record<string, unknown>;
}

export interface AgentRunStep {
  agent_key: string;
  agent_name: string;
  tool_key: string;
  status: string;
  params: Record<string, unknown>;
  output_preview: Record<string, unknown>;
  error: string;
}

export interface AgentRun {
  id: number;
  run_key: string;
  symbol: string;
  query: string;
  mode: string;
  status: string;
  agent_keys: string[];
  steps: AgentRunStep[];
  result: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface AgentRunListResponse {
  items: AgentRun[];
}

export interface AgentRunCreatePayload {
  symbol: string;
  query?: string;
  mode?: string;
  agent_keys?: string[];
  variables?: Record<string, string>;
  period?: string;
  limit?: number;
  include_report?: boolean;
}

export interface KnowledgeDocument {
  id: number;
  title: string;
  doc_type: string;
  source: string;
  summary: string;
  symbols: string[];
  tags: string[];
  metadata: Record<string, unknown>;
  status: string;
  enabled: boolean;
  chunk_count: number;
  published_at: string;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeDocumentDetail extends KnowledgeDocument {
  content: string;
  chunks: Array<{
    id: number;
    document_id: number;
    chunk_index: number;
    content: string;
    summary: string;
    token_count: number;
    metadata: Record<string, unknown>;
  }>;
}

export interface KnowledgeDocumentListResponse {
  items: KnowledgeDocument[];
}

export interface KnowledgeDocumentCreatePayload {
  title: string;
  content: string;
  doc_type?: string;
  source?: string;
  symbols?: string[];
  tags?: string[];
  metadata?: Record<string, unknown>;
  published_at?: string;
  enabled?: boolean;
}

export interface KnowledgeSearchItem {
  chunk_id: number;
  document_id: number;
  title: string;
  snippet: string;
  score: number;
  source: string;
  doc_type: string;
  symbols: string[];
  tags: string[];
  citation: string;
  metadata: Record<string, unknown>;
}

export interface KnowledgeSearchResponse {
  query: string;
  items: KnowledgeSearchItem[];
}

export interface DataProvider {
  id: number;
  key: string;
  name: string;
  type: string;
  enabled: boolean;
  auth_type: string;
  base_url: string;
  test_url: string;
  cache_ttl_seconds: number;
  health_status: string;
  last_success_at: string | null;
  last_failure_at: string | null;
}

export interface DataProviderListResponse {
  items: DataProvider[];
}

export interface DataProviderUpdatePayload {
  name?: string;
  enabled?: boolean;
  auth_type?: string;
  base_url?: string;
  test_url?: string;
  cache_ttl_seconds?: number;
  config?: Record<string, unknown>;
  rate_limit?: Record<string, unknown>;
}

export interface DataProviderCredential {
  provider_key: string;
  credential_type: string;
  configured: boolean;
  masked_value: string;
  last_verified_at: string | null;
  verification_status: string;
}

export interface DataProviderCredentialListResponse {
  items: DataProviderCredential[];
}

export interface DataRoute {
  id: number;
  data_category: string;
  tool_name: string;
  provider_chain: string[];
  enabled: boolean;
  fallback_policy: string;
}

export interface DataRouteListResponse {
  items: DataRoute[];
}

export interface DataFetchLog {
  id: number;
  provider_key: string;
  data_category: string;
  tool_name: string;
  symbol: string;
  status: string;
  http_status: number | null;
  latency_ms: number | null;
  cache_hit: boolean;
  fallback_used: boolean;
  error_type: string;
  error_message: string;
  fetched_at: string;
}

export interface DataFetchLogListResponse {
  items: DataFetchLog[];
}

export interface HealthCheckResult {
  provider_key: string;
  status: string;
  http_status: number | null;
  latency_ms: number | null;
  message: string;
}

export interface HealthCheckResponse {
  items: HealthCheckResult[];
}

export interface RealtimeQuote {
  symbol: string;
  name: string;
  price: number | null;
  pre_close: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
  change: number | null;
  change_percent: number | null;
  volume: number | null;
  amount: number | null;
  turnover_rate: number | null;
  pe_ttm: number | null;
  pb: number | null;
  market_cap: number | null;
  timestamp: string;
  provider_key: string;
}

export interface KlineBar {
  time: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
  amount: number;
  amplitude: number | null;
  change_percent: number | null;
  change: number | null;
  turnover_rate: number | null;
}

export interface KlineResponse {
  symbol: string;
  name: string;
  period: string;
  provider_key: string;
  items: KlineBar[];
}

export interface NewsItem {
  id: string;
  title: string;
  content: string;
  source: string;
  publish_time: string;
  level: string;
  related_stocks: string[];
  url: string;
}

export interface NewsResponse {
  provider_key: string;
  items: NewsItem[];
}

export interface AnnouncementItem {
  id: string;
  symbol: string;
  title: string;
  publish_time: string;
  category: string;
  source: string;
  url: string;
}

export interface AnnouncementResponse {
  symbol: string;
  provider_key: string;
  items: AnnouncementItem[];
}

export interface FundamentalMetric {
  key: string;
  label: string;
  value: number | string | null;
  unit: string;
}

export interface FundamentalResponse {
  symbol: string;
  name: string;
  provider_key: string;
  metrics: FundamentalMetric[];
}

export interface FinancialStatementRow {
  report_date: string;
  notice_date: string;
  values: Record<string, number | string | null>;
}

export interface FinancialStatementResponse {
  symbol: string;
  statement_type: string;
  provider_key: string;
  items: FinancialStatementRow[];
}

export interface FundFlowItem {
  date: string;
  main_net_inflow: number | null;
  small_net_inflow: number | null;
  medium_net_inflow: number | null;
  large_net_inflow: number | null;
  super_large_net_inflow: number | null;
}

export interface FundFlowResponse {
  symbol: string;
  name: string;
  provider_key: string;
  items: FundFlowItem[];
}

export interface SectorSnapshotItem {
  code: string;
  name: string;
  price: number | null;
  change_percent: number | null;
  main_net_inflow: number | null;
  main_net_ratio: number | null;
  sector_type: string;
}

export interface SectorSnapshotResponse {
  provider_key: string;
  items: SectorSnapshotItem[];
}

export interface NorthboundFlowItem {
  trade_date: string;
  mutual_type: string;
  net_deal_amount: number | null;
  buy_amount: number | null;
  sell_amount: number | null;
  deal_amount: number | null;
  lead_stock_code: string;
  lead_stock_name: string;
}

export interface NorthboundFlowResponse {
  provider_key: string;
  items: NorthboundFlowItem[];
}

export interface ResearchReportItem {
  id: string;
  title: string;
  stock_code: string;
  stock_name: string;
  org_name: string;
  publish_date: string;
  rating: string;
  author: string;
  url: string;
}

export interface ResearchReportResponse {
  symbol: string;
  provider_key: string;
  items: ResearchReportItem[];
}

export interface DragonTigerItem {
  trade_date: string;
  symbol: string;
  name: string;
  reason: string;
  close_price: number | null;
  change_percent: number | null;
  buy_amount: number | null;
  sell_amount: number | null;
  net_amount: number | null;
  deal_amount: number | null;
  explanation: string;
}

export interface DragonTigerResponse {
  symbol: string;
  provider_key: string;
  items: DragonTigerItem[];
}

export interface LockupExpiryItem {
  free_date: string;
  symbol: string;
  name: string;
  shares: number | null;
  market_cap: number | null;
  free_ratio: number | null;
  share_type: string;
}

export interface LockupExpiryResponse {
  symbol: string;
  provider_key: string;
  items: LockupExpiryItem[];
}

export interface MarginTradingItem {
  date: string;
  symbol: string;
  name: string;
  financing_balance: number | null;
  securities_lending_balance: number | null;
  margin_balance: number | null;
  financing_buy_amount: number | null;
  financing_net_buy_amount: number | null;
  short_selling_volume: number | null;
}

export interface MarginTradingResponse {
  symbol: string;
  provider_key: string;
  items: MarginTradingItem[];
}

export interface MacroIndicatorItem {
  report_date: string;
  time_label: string;
  values: Record<string, number | string | null>;
}

export interface MacroIndicatorResponse {
  indicator: string;
  provider_key: string;
  items: MacroIndicatorItem[];
}

export interface DataQualityItem {
  provider_key: string;
  health_status: string;
  score: number;
  recent_total: number;
  recent_failures: number;
  cache_hits: number;
  last_message: string;
}

export interface DataQualityResponse {
  items: DataQualityItem[];
}

export interface DataAlertItem {
  provider_key: string;
  severity: string;
  message: string;
  status: string;
  fetched_at: string | null;
}

export interface DataAlertListResponse {
  items: DataAlertItem[];
}

export interface WatchlistItem {
  id: number;
  symbol: string;
  name: string;
  sort_order: number;
  note: string;
}

export interface WatchlistListResponse {
  items: WatchlistItem[];
}

export interface IndicatorSeries {
  name: string;
  values: Array<number | null>;
}

export interface IndicatorResponse {
  symbol: string;
  period: string;
  source: string;
  items: IndicatorSeries[];
}

export interface DataSnapshot {
  id: number;
  symbol: string;
  period: string;
  snapshot_type: string;
  snapshot_json: string;
  created_at: string;
}

export interface CacheClearResponse {
  cleared: boolean;
  message: string;
}

export interface ScheduledTask {
  key: string;
  name: string;
  interval_seconds: number;
  enabled: boolean;
  last_status: string | null;
  last_message: string | null;
  last_started_at: string | null;
  last_finished_at: string | null;
}

export interface ScheduledTaskListResponse {
  items: ScheduledTask[];
}

export interface ScheduledTaskRun {
  id: number;
  task_key: string;
  status: string;
  message: string;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
}

export interface ScheduledTaskRunListResponse {
  items: ScheduledTaskRun[];
}

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`请求失败：${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    throw new Error(`请求失败：${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function patchJson<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    throw new Error(`请求失败：${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function fetchHealth(): Promise<HealthResponse> {
  return getJson<HealthResponse>("/api/health");
}

export function fetchModules(): Promise<ModuleListResponse> {
  return getJson<ModuleListResponse>("/api/modules");
}

export function fetchAgents(): Promise<AgentListResponse> {
  return getJson<AgentListResponse>("/api/agents");
}

export function updateAgent(agentKey: string, payload: AgentUpdatePayload): Promise<AgentConfig> {
  return patchJson<AgentConfig>(`/api/agents/${encodeURIComponent(agentKey)}`, payload);
}

export function fetchAgentVersions(agentKey: string): Promise<AgentPromptVersionListResponse> {
  return getJson<AgentPromptVersionListResponse>(`/api/agents/${encodeURIComponent(agentKey)}/versions`);
}

export function rollbackAgent(agentKey: string, version: number): Promise<AgentConfig> {
  return postJson<AgentConfig>(`/api/agents/${encodeURIComponent(agentKey)}/rollback`, { version });
}

export function renderAgentPrompt(
  agentKey: string,
  variables: Record<string, string>
): Promise<AgentRenderResponse> {
  return postJson<AgentRenderResponse>(`/api/agents/${encodeURIComponent(agentKey)}/render`, { variables });
}

export function testRunAgent(
  agentKey: string,
  inputText: string,
  variables: Record<string, string>
): Promise<AgentTestRunResponse> {
  return postJson<AgentTestRunResponse>(`/api/agents/${encodeURIComponent(agentKey)}/test-run`, {
    input_text: inputText,
    variables
  });
}

export function fetchAgentTools(): Promise<AgentToolListResponse> {
  return getJson<AgentToolListResponse>("/api/agent-tools");
}

export function runAgentTool(
  agentKey: string,
  toolKey: string,
  params: Record<string, unknown>
): Promise<AgentToolRunResponse> {
  return postJson<AgentToolRunResponse>(
    `/api/agent-tools/${encodeURIComponent(agentKey)}/${encodeURIComponent(toolKey)}/run`,
    { params }
  );
}

export function createAgentRun(payload: AgentRunCreatePayload): Promise<AgentRun> {
  return postJson<AgentRun>("/api/agent-runs", payload);
}

export function fetchAgentRuns(limit = 20): Promise<AgentRunListResponse> {
  return getJson<AgentRunListResponse>(`/api/agent-runs?limit=${limit}`);
}

export function fetchAgentRun(runKey: string): Promise<AgentRun> {
  return getJson<AgentRun>(`/api/agent-runs/${encodeURIComponent(runKey)}`);
}

export function fetchKnowledgeDocuments(q = "", limit = 50): Promise<KnowledgeDocumentListResponse> {
  const params = new URLSearchParams({ q, limit: String(limit) });
  return getJson<KnowledgeDocumentListResponse>(`/api/knowledge/documents?${params}`);
}

export function createKnowledgeDocument(payload: KnowledgeDocumentCreatePayload): Promise<KnowledgeDocumentDetail> {
  return postJson<KnowledgeDocumentDetail>("/api/knowledge/documents", payload);
}

export function searchKnowledge(payload: {
  query: string;
  symbols?: string[];
  doc_types?: string[];
  tags?: string[];
  top_k?: number;
  require_citations?: boolean;
}): Promise<KnowledgeSearchResponse> {
  return postJson<KnowledgeSearchResponse>("/api/knowledge/search", payload);
}

export function fetchDataProviders(): Promise<DataProviderListResponse> {
  return getJson<DataProviderListResponse>("/api/data/providers");
}

export function updateDataProvider(
  providerKey: string,
  payload: DataProviderUpdatePayload
): Promise<DataProvider> {
  return patchJson<DataProvider>(`/api/data/providers/${encodeURIComponent(providerKey)}`, payload);
}

export function fetchProviderCredentials(
  providerKey: string
): Promise<DataProviderCredentialListResponse> {
  return getJson<DataProviderCredentialListResponse>(
    `/api/data/providers/${encodeURIComponent(providerKey)}/credentials`
  );
}

export function saveProviderCredential(
  providerKey: string,
  credentialType: string,
  value: string
): Promise<DataProviderCredential> {
  return postJson<DataProviderCredential>(`/api/data/providers/${encodeURIComponent(providerKey)}/credentials`, {
    credential_type: credentialType,
    value
  });
}

export function fetchDataRoutes(): Promise<DataRouteListResponse> {
  return getJson<DataRouteListResponse>("/api/data/routes");
}

export function fetchDataFetchLogs(): Promise<DataFetchLogListResponse> {
  return getJson<DataFetchLogListResponse>("/api/data/fetch-logs");
}

export function runDataHealthCheck(providerKey?: string): Promise<HealthCheckResponse> {
  return postJson<HealthCheckResponse>("/api/data/health-check", {
    provider_key: providerKey ?? null
  });
}

export function fetchRealtimeQuote(symbol: string): Promise<RealtimeQuote> {
  return getJson<RealtimeQuote>(`/api/data/quote/${encodeURIComponent(symbol)}`);
}

export function fetchKlines(
  symbol: string,
  period = "daily",
  limit = 80
): Promise<KlineResponse> {
  const params = new URLSearchParams({ period, limit: String(limit) });
  return getJson<KlineResponse>(`/api/data/klines/${encodeURIComponent(symbol)}?${params}`);
}

export function fetchMarketNews(limit = 20): Promise<NewsResponse> {
  return getJson<NewsResponse>(`/api/data/news?limit=${limit}`);
}

export function fetchStockAnnouncements(symbol: string, limit = 20): Promise<AnnouncementResponse> {
  return getJson<AnnouncementResponse>(`/api/stocks/${encodeURIComponent(symbol)}/announcements?limit=${limit}`);
}

export function fetchStockFundamentals(symbol: string): Promise<FundamentalResponse> {
  return getJson<FundamentalResponse>(`/api/stocks/${encodeURIComponent(symbol)}/fundamentals`);
}

export function fetchFinancialStatements(
  symbol: string,
  statementType = "income",
  limit = 4
): Promise<FinancialStatementResponse> {
  const params = new URLSearchParams({ statement_type: statementType, limit: String(limit) });
  return getJson<FinancialStatementResponse>(`/api/stocks/${encodeURIComponent(symbol)}/financial-statements?${params}`);
}

export function fetchStockFundFlow(symbol: string, limit = 20): Promise<FundFlowResponse> {
  return getJson<FundFlowResponse>(`/api/stocks/${encodeURIComponent(symbol)}/fund-flow?limit=${limit}`);
}

export function fetchResearchReports(symbol: string, limit = 10): Promise<ResearchReportResponse> {
  return getJson<ResearchReportResponse>(`/api/stocks/${encodeURIComponent(symbol)}/research-reports?limit=${limit}`);
}

export function fetchDragonTiger(symbol: string, limit = 10): Promise<DragonTigerResponse> {
  return getJson<DragonTigerResponse>(`/api/stocks/${encodeURIComponent(symbol)}/dragon-tiger?limit=${limit}`);
}

export function fetchLockupExpiry(symbol: string, limit = 10): Promise<LockupExpiryResponse> {
  return getJson<LockupExpiryResponse>(`/api/stocks/${encodeURIComponent(symbol)}/lockup-expiry?limit=${limit}`);
}

export function fetchMarginTrading(symbol: string, limit = 10): Promise<MarginTradingResponse> {
  return getJson<MarginTradingResponse>(`/api/stocks/${encodeURIComponent(symbol)}/margin-trading?limit=${limit}`);
}

export function fetchSectorSnapshots(sectorType = "industry", limit = 10): Promise<SectorSnapshotResponse> {
  const params = new URLSearchParams({ sector_type: sectorType, limit: String(limit) });
  return getJson<SectorSnapshotResponse>(`/api/sectors/snapshots?${params}`);
}

export function fetchNorthboundFlow(limit = 10): Promise<NorthboundFlowResponse> {
  return getJson<NorthboundFlowResponse>(`/api/market/northbound-flow?limit=${limit}`);
}

export function fetchMacroIndicator(indicator = "cpi", limit = 12): Promise<MacroIndicatorResponse> {
  const params = new URLSearchParams({ indicator, limit: String(limit) });
  return getJson<MacroIndicatorResponse>(`/api/market/macro?${params}`);
}

export function fetchDataQuality(): Promise<DataQualityResponse> {
  return getJson<DataQualityResponse>("/api/data/quality");
}

export function fetchDataAlerts(limit = 20): Promise<DataAlertListResponse> {
  return getJson<DataAlertListResponse>(`/api/data/alerts?limit=${limit}`);
}

export function clearDataCache(): Promise<CacheClearResponse> {
  return postJson<CacheClearResponse>("/api/data/cache/clear", {});
}

export function fetchWatchlist(): Promise<WatchlistListResponse> {
  return getJson<WatchlistListResponse>("/api/data/watchlist");
}

export function addWatchlistItem(symbol: string): Promise<WatchlistItem> {
  return postJson<WatchlistItem>("/api/data/watchlist", { symbol });
}

export async function deleteWatchlistItem(symbol: string): Promise<WatchlistListResponse> {
  const response = await fetch(`/api/data/watchlist/${encodeURIComponent(symbol)}`, {
    method: "DELETE"
  });
  if (!response.ok) {
    throw new Error(`请求失败：${response.status}`);
  }
  return response.json() as Promise<WatchlistListResponse>;
}

export function reorderWatchlist(symbols: string[]): Promise<WatchlistListResponse> {
  return postJson<WatchlistListResponse>("/api/data/watchlist/reorder", { symbols });
}

export function fetchStockIndicators(
  symbol: string,
  names: string[],
  period = "daily",
  limit = 80
): Promise<IndicatorResponse> {
  const params = new URLSearchParams({
    names: names.join(","),
    period,
    limit: String(limit)
  });
  return getJson<IndicatorResponse>(`/api/stocks/${encodeURIComponent(symbol)}/indicators?${params}`);
}

export function createDataSnapshot(symbol: string, period = "daily", limit = 120): Promise<DataSnapshot> {
  return postJson<DataSnapshot>("/api/data/snapshots", {
    symbol,
    period,
    limit,
    news_limit: 10
  });
}

export function fetchScheduledTasks(): Promise<ScheduledTaskListResponse> {
  return getJson<ScheduledTaskListResponse>("/api/data/scheduled-tasks");
}

export function runScheduledTask(taskKey: string): Promise<ScheduledTaskRun> {
  return postJson<ScheduledTaskRun>(`/api/data/scheduled-tasks/${encodeURIComponent(taskKey)}/run`, {});
}

export function fetchScheduledTaskRuns(limit = 20): Promise<ScheduledTaskRunListResponse> {
  return getJson<ScheduledTaskRunListResponse>(`/api/data/scheduled-task-runs?limit=${limit}`);
}
