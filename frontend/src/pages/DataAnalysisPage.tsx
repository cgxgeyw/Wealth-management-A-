import { ArrowDown, ArrowLeft, ArrowUp, GripVertical, Plus, RefreshCw, Search, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  addWatchlistItem,
  createAnalysisTask,
  createDataSnapshot,
  deleteWatchlistItem,
  fetchDragonTiger,
  fetchFinancialStatements,
  fetchKlines,
  fetchLockupExpiry,
  fetchMacroIndicator,
  fetchMarginTrading,
  fetchMarketNews,
  fetchNorthboundFlow,
  fetchRealtimeQuote,
  fetchResearchReports,
  fetchSectorSnapshots,
  fetchStockAnnouncements,
  fetchStockFundFlow,
  fetchStockFundamentals,
  fetchStockIndicators,
  fetchWatchlist,
  reorderWatchlist,
  type AnalysisTask,
  type AnnouncementResponse,
  type DragonTigerResponse,
  type FinancialStatementResponse,
  type FundamentalResponse,
  type FundFlowResponse,
  type IndicatorResponse,
  type KlineBar,
  type KlineResponse,
  type LockupExpiryResponse,
  type MacroIndicatorResponse,
  type MarginTradingResponse,
  type NorthboundFlowResponse,
  type NewsResponse,
  type RealtimeQuote,
  type ResearchReportResponse,
  type SectorSnapshotItem,
  type SectorSnapshotResponse,
  type WatchlistItem
} from "../api/client";

type OverviewTab = "watchlist" | "recommended" | "market";
type ViewMode = "overview" | "detail";

interface StockSeed {
  symbol: string;
  name: string;
  reason?: string;
  score?: number;
}

interface IndicatorLine {
  key: string;
  label: string;
  color: string;
  points: string;
}

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

const recommendedSeeds: StockSeed[] = [
  { symbol: "300750", name: "宁德时代", reason: "新能源龙头，量价修复", score: 86 },
  { symbol: "002475", name: "立讯精密", reason: "消费电子链景气回暖", score: 82 },
  { symbol: "000333", name: "美的集团", reason: "现金流稳定，估值分位合理", score: 78 },
  { symbol: "601012", name: "隆基绿能", reason: "低位反弹，但仍需验证", score: 72 }
];

const marketRows = [
  ["上证指数", "强弱分化", "+0.18%", "成交额维持高位，权重股托底"],
  ["深证成指", "震荡", "-0.06%", "成长板块轮动加快"],
  ["创业板指", "修复", "+0.41%", "新能源与医药贡献主要弹性"],
  ["科创 50", "偏弱", "-0.32%", "半导体分化，资金等待新催化"]
];

const indicators = ["MA", "MACD", "KDJ", "RSI", "BOLL", "成交量"];
const newsPageSize = 5;

function StatusBadge({ tone = "neutral", children }: { tone?: string; children: React.ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
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

function Metric({ label, value, meta, tone = "neutral" }: { label: string; value: string; meta: string; tone?: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong className={tone}>{value}</strong>
      <small>{meta}</small>
    </div>
  );
}

function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return value.toLocaleString("zh-CN", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits
  });
}

function formatOptional(value: number | null | undefined, suffix = "", digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return `${formatNumber(value, digits)}${suffix}`;
}

function formatLargeMoney(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  const abs = Math.abs(value);
  if (abs >= 100000000) return `${formatNumber(value / 100000000, 2)}亿`;
  if (abs >= 10000) return `${formatNumber(value / 10000, 2)}万`;
  return formatNumber(value, 0);
}

function metricValue(data: FundamentalResponse | null, key: string): number | string | null {
  return data?.metrics.find((item) => item.key === key)?.value ?? null;
}

function numericMetric(data: FundamentalResponse | null, key: string): number | null {
  const value = metricValue(data, key);
  if (value === null || value === "") return null;
  const numberValue = Number(value);
  return Number.isNaN(numberValue) ? null : numberValue;
}

function formatQuoteTime(value: string): string {
  if (!value) return "-";
  if (/^\d{14}$/.test(value)) {
    return `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)} ${value.slice(8, 10)}:${value.slice(10, 12)}:${value.slice(12, 14)}`;
  }
  const normalized = /[zZ]|[+-]\d{2}:\d{2}$/.test(value) ? value : `${value}Z`;
  return TIME_FORMATTER.format(new Date(normalized));
}

function formatNewsTime(value: string): string {
  if (!value) return "-";
  const normalized = /[zZ]|[+-]\d{2}:\d{2}$/.test(value) ? value : `${value}Z`;
  return TIME_FORMATTER.format(new Date(normalized));
}

function normalizeSymbolInput(value: string): string {
  const match = value.match(/\d{6}/);
  return match ? match[0] : value.trim();
}

function barHeight(bar: KlineBar, minLow: number, maxHigh: number): number {
  const range = Math.max(maxHigh - minLow, 1);
  return 24 + ((bar.high - bar.low) / range) * 116;
}

function linePoints(values: Array<number | null>, mapValue: (value: number) => number): string {
  const lastIndex = Math.max(values.length - 1, 1);
  return values
    .map((value, index) => {
      if (value === null || Number.isNaN(value)) return "";
      return `${(index / lastIndex) * 100},${mapValue(value)}`;
    })
    .filter(Boolean)
    .join(" ");
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function movingAverage(bars: KlineBar[], period: number): Array<number | null> {
  return bars.map((_, index) => {
    if (index + 1 < period) return null;
    const slice = bars.slice(index + 1 - period, index + 1);
    return slice.reduce((sum, item) => sum + item.close, 0) / period;
  });
}

function standardDeviation(values: number[]): number {
  const average = values.reduce((sum, value) => sum + value, 0) / values.length;
  const variance = values.reduce((sum, value) => sum + (value - average) ** 2, 0) / values.length;
  return Math.sqrt(variance);
}

function exponentialAverage(values: number[], period: number): number[] {
  const factor = 2 / (period + 1);
  return values.reduce<number[]>((items, value, index) => {
    items.push(index === 0 ? value : value * factor + items[index - 1] * (1 - factor));
    return items;
  }, []);
}

function relativeStrengthIndex(bars: KlineBar[], period = 14): Array<number | null> {
  return bars.map((_, index) => {
    if (index < period) return null;
    let gains = 0;
    let losses = 0;
    for (let cursor = index - period + 1; cursor <= index; cursor += 1) {
      const change = bars[cursor].close - bars[cursor - 1].close;
      if (change >= 0) gains += change;
      else losses += Math.abs(change);
    }
    if (losses === 0) return 100;
    const rs = gains / losses;
    return 100 - 100 / (1 + rs);
  });
}

function stochasticKdj(bars: KlineBar[], period = 9): {
  k: Array<number | null>;
  d: Array<number | null>;
  j: Array<number | null>;
} {
  let previousK = 50;
  let previousD = 50;
  const k: Array<number | null> = [];
  const d: Array<number | null> = [];
  const j: Array<number | null> = [];
  bars.forEach((bar, index) => {
    if (index + 1 < period) {
      k.push(null);
      d.push(null);
      j.push(null);
      return;
    }
    const slice = bars.slice(index + 1 - period, index + 1);
    const low = Math.min(...slice.map((item) => item.low));
    const high = Math.max(...slice.map((item) => item.high));
    const rsv = high === low ? 50 : ((bar.close - low) / (high - low)) * 100;
    previousK = (2 / 3) * previousK + (1 / 3) * rsv;
    previousD = (2 / 3) * previousD + (1 / 3) * previousK;
    k.push(previousK);
    d.push(previousD);
    j.push(3 * previousK - 2 * previousD);
  });
  return { k, d, j };
}

function macdLines(bars: KlineBar[]): {
  dif: number[];
  dea: number[];
} {
  const closes = bars.map((item) => item.close);
  const ema12 = exponentialAverage(closes, 12);
  const ema26 = exponentialAverage(closes, 26);
  const dif = closes.map((_, index) => ema12[index] - ema26[index]);
  const dea = exponentialAverage(dif, 9);
  return { dif, dea };
}

function buildIndicatorLines(
  bars: KlineBar[],
  selectedIndicators: string[],
  minLow: number,
  maxHigh: number,
  indicatorData: IndicatorResponse | null
): IndicatorLine[] {
  if (!bars.length) return [];
  const range = Math.max(maxHigh - minLow, 1);
  const mapPrice = (value: number) => 92 - ((value - minLow) / range) * 82;
  const mapPercent = (value: number) => 88 - (Math.max(Math.min(value, 100), 0) / 100) * 70;
  const lines: IndicatorLine[] = [];
  const backendSeries = new Map((indicatorData?.items ?? []).map((item) => [item.name, item.values]));

  function series(name: string, fallback: Array<number | null>): Array<number | null> {
    return backendSeries.get(name) ?? fallback;
  }

  if (selectedIndicators.includes("MA")) {
    lines.push(
      { key: "ma5", label: "MA5", color: "#2563eb", points: linePoints(series("MA5", movingAverage(bars, 5)), mapPrice) },
      { key: "ma10", label: "MA10", color: "#7c3aed", points: linePoints(series("MA10", movingAverage(bars, 10)), mapPrice) }
    );
  }

  if (selectedIndicators.includes("BOLL")) {
    const middle = movingAverage(bars, 20);
    const upper = bars.map((_, index) => {
      if (index + 1 < 20) return null;
      const closes = bars.slice(index + 1 - 20, index + 1).map((item) => item.close);
      return (middle[index] ?? 0) + standardDeviation(closes) * 2;
    });
    const lower = bars.map((_, index) => {
      if (index + 1 < 20) return null;
      const closes = bars.slice(index + 1 - 20, index + 1).map((item) => item.close);
      return (middle[index] ?? 0) - standardDeviation(closes) * 2;
    });
    lines.push(
      { key: "boll-mid", label: "BOLL-M", color: "#0f766e", points: linePoints(series("BOLL_MIDDLE", middle), mapPrice) },
      { key: "boll-up", label: "BOLL-U", color: "#0891b2", points: linePoints(series("BOLL_UPPER", upper), mapPrice) },
      { key: "boll-low", label: "BOLL-L", color: "#0891b2", points: linePoints(series("BOLL_LOWER", lower), mapPrice) }
    );
  }

  if (selectedIndicators.includes("RSI")) {
    lines.push({ key: "rsi14", label: "RSI14", color: "#ea580c", points: linePoints(series("RSI14", relativeStrengthIndex(bars)), mapPercent) });
  }

  if (selectedIndicators.includes("KDJ")) {
    const kdj = stochasticKdj(bars);
    lines.push(
      { key: "kdj-k", label: "K", color: "#16a34a", points: linePoints(series("K", kdj.k), mapPercent) },
      { key: "kdj-d", label: "D", color: "#ca8a04", points: linePoints(series("D", kdj.d), mapPercent) },
      { key: "kdj-j", label: "J", color: "#dc2626", points: linePoints(series("J", kdj.j), mapPercent) }
    );
  }

  if (selectedIndicators.includes("MACD")) {
    const macd = macdLines(bars);
    const dif = series("DIF", macd.dif);
    const dea = series("DEA", macd.dea);
    const maxAbs = Math.max(...dif.map((value, index) => Math.max(Math.abs(value ?? 0), Math.abs(dea[index] ?? 0))), 0.01);
    const mapMacd = (value: number) => clamp(74 - (value / maxAbs) * 26, 48, 94);
    lines.push(
      { key: "macd-dif", label: "DIF", color: "#2563eb", points: linePoints(dif, mapMacd) },
      { key: "macd-dea", label: "DEA", color: "#dc2626", points: linePoints(dea, mapMacd) }
    );
  }

  return lines.filter((line) => line.points);
}

function toneByChange(value: number | null | undefined): string {
  if ((value ?? 0) > 0) return "up";
  if ((value ?? 0) < 0) return "down";
  return "neutral";
}

export function DataAnalysisPage() {
  const [viewMode, setViewMode] = useState<ViewMode>("overview");
  const [activeTab, setActiveTab] = useState<OverviewTab>("watchlist");
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [draggingSymbol, setDraggingSymbol] = useState("");
  const [symbolInput, setSymbolInput] = useState("300750");
  const [symbol, setSymbol] = useState("300750");
  const [period, setPeriod] = useState("daily");
  const [selectedIndicators, setSelectedIndicators] = useState<string[]>(["MACD"]);
  const [overviewQuotes, setOverviewQuotes] = useState<Record<string, RealtimeQuote>>({});
  const [quote, setQuote] = useState<RealtimeQuote | null>(null);
  const [klines, setKlines] = useState<KlineResponse | null>(null);
  const [indicatorData, setIndicatorData] = useState<IndicatorResponse | null>(null);
  const [news, setNews] = useState<NewsResponse | null>(null);
  const [announcements, setAnnouncements] = useState<AnnouncementResponse | null>(null);
  const [fundamentals, setFundamentals] = useState<FundamentalResponse | null>(null);
  const [financials, setFinancials] = useState<FinancialStatementResponse | null>(null);
  const [fundFlow, setFundFlow] = useState<FundFlowResponse | null>(null);
  const [researchReports, setResearchReports] = useState<ResearchReportResponse | null>(null);
  const [dragonTiger, setDragonTiger] = useState<DragonTigerResponse | null>(null);
  const [lockupExpiry, setLockupExpiry] = useState<LockupExpiryResponse | null>(null);
  const [marginTrading, setMarginTrading] = useState<MarginTradingResponse | null>(null);
  const [sectorSnapshots, setSectorSnapshots] = useState<SectorSnapshotResponse | null>(null);
  const [conceptSnapshots, setConceptSnapshots] = useState<SectorSnapshotResponse | null>(null);
  const [northboundFlow, setNorthboundFlow] = useState<NorthboundFlowResponse | null>(null);
  const [macroCpi, setMacroCpi] = useState<MacroIndicatorResponse | null>(null);
  const [macroPmi, setMacroPmi] = useState<MacroIndicatorResponse | null>(null);
  const [snapshotId, setSnapshotId] = useState<number | null>(null);
  const [latestTask, setLatestTask] = useState<AnalysisTask | null>(null);
  const [newsPage, setNewsPage] = useState(0);
  const [loadingOverview, setLoadingOverview] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState("");

  const loadOverview = useCallback(async () => {
    setLoadingOverview(true);
    setError("");
    try {
      const [watchlistResult, sectorResult, conceptResult, northboundResult, cpiResult, pmiResult] = await Promise.allSettled([
        fetchWatchlist(),
        fetchSectorSnapshots("industry", 6),
        fetchSectorSnapshots("concept", 6),
        fetchNorthboundFlow(6),
        fetchMacroIndicator("cpi", 3),
        fetchMacroIndicator("pmi", 3)
      ]);
      if (watchlistResult.status !== "fulfilled") {
        throw watchlistResult.reason;
      }
      setWatchlist(watchlistResult.value.items);
      setSectorSnapshots(sectorResult.status === "fulfilled" ? sectorResult.value : null);
      setConceptSnapshots(conceptResult.status === "fulfilled" ? conceptResult.value : null);
      setNorthboundFlow(northboundResult.status === "fulfilled" ? northboundResult.value : null);
      setMacroCpi(cpiResult.status === "fulfilled" ? cpiResult.value : null);
      setMacroPmi(pmiResult.status === "fulfilled" ? pmiResult.value : null);
      const symbols = Array.from(new Set([...watchlistResult.value.items, ...recommendedSeeds].map((item) => item.symbol)));
      const results = await Promise.allSettled(symbols.map((item) => fetchRealtimeQuote(item)));
      const nextQuotes: Record<string, RealtimeQuote> = {};
      results.forEach((result) => {
        if (result.status === "fulfilled") {
          nextQuotes[result.value.symbol] = result.value;
        }
      });
      setOverviewQuotes(nextQuotes);
    } catch (err) {
      setError(err instanceof Error ? err.message : "概览数据加载失败");
    } finally {
      setLoadingOverview(false);
    }
  }, []);

  const loadDetail = useCallback(async (nextSymbol: string, nextPeriod: string) => {
    setLoadingDetail(true);
    setError("");
    try {
      const [quoteResult, klineResult, indicatorResult, newsResult, announcementResult] = await Promise.all([
        fetchRealtimeQuote(nextSymbol),
        fetchKlines(nextSymbol, nextPeriod, 80),
        fetchStockIndicators(nextSymbol, ["ma", "macd", "rsi", "kdj", "boll"], nextPeriod, 80),
        fetchMarketNews(30),
        fetchStockAnnouncements(nextSymbol, 10)
      ]);
      setQuote(quoteResult);
      setKlines(klineResult);
      setIndicatorData(indicatorResult);
      setNews(newsResult);
      setAnnouncements(announcementResult);
      setNewsPage(0);
      const enhancedResults = await Promise.allSettled([
        fetchStockFundamentals(nextSymbol),
        fetchFinancialStatements(nextSymbol, "income", 4),
        fetchStockFundFlow(nextSymbol, 10),
        fetchResearchReports(nextSymbol, 5),
        fetchDragonTiger(nextSymbol, 5),
        fetchLockupExpiry(nextSymbol, 5),
        fetchMarginTrading(nextSymbol, 5)
      ]);
      setFundamentals(enhancedResults[0].status === "fulfilled" ? enhancedResults[0].value : null);
      setFinancials(enhancedResults[1].status === "fulfilled" ? enhancedResults[1].value : null);
      setFundFlow(enhancedResults[2].status === "fulfilled" ? enhancedResults[2].value : null);
      setResearchReports(enhancedResults[3].status === "fulfilled" ? enhancedResults[3].value : null);
      setDragonTiger(enhancedResults[4].status === "fulfilled" ? enhancedResults[4].value : null);
      setLockupExpiry(enhancedResults[5].status === "fulfilled" ? enhancedResults[5].value : null);
      setMarginTrading(enhancedResults[6].status === "fulfilled" ? enhancedResults[6].value : null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "详情数据加载失败");
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  useEffect(() => {
    loadOverview();
  }, [loadOverview]);

  useEffect(() => {
    if (viewMode === "detail") {
      loadDetail(symbol, period);
    }
  }, [loadDetail, period, symbol, viewMode]);

  const bars = klines?.items ?? [];
  const chartStats = useMemo(() => {
    if (!bars.length) return { minLow: 0, maxHigh: 1 };
    const minLow = Math.min(...bars.map((item) => item.low));
    const maxHigh = Math.max(...bars.map((item) => item.high));
    const padding = Math.max((maxHigh - minLow) * 0.06, 0.01);
    return {
      minLow: minLow - padding,
      maxHigh: maxHigh + padding
    };
  }, [bars]);
  const indicatorLines = useMemo(
    () => buildIndicatorLines(bars, selectedIndicators, chartStats.minLow, chartStats.maxHigh, indicatorData),
    [bars, chartStats.maxHigh, chartStats.minLow, indicatorData, selectedIndicators]
  );

  const newsItems = news?.items ?? [];
  const newsPageCount = Math.max(Math.ceil(newsItems.length / newsPageSize), 1);
  const visibleNews = newsItems.slice(newsPage * newsPageSize, newsPage * newsPageSize + newsPageSize);

  function openDetail(nextSymbol: string) {
    setSymbol(nextSymbol);
    setSymbolInput(nextSymbol);
    setViewMode("detail");
  }

  function submitSearch() {
    const nextSymbol = normalizeSymbolInput(symbolInput);
    if (!nextSymbol) return;
    openDetail(nextSymbol);
  }

  async function addWatchStock() {
    const input = window.prompt("输入股票代码，例如 300750");
    const nextSymbol = normalizeSymbolInput(input ?? "");
    if (!nextSymbol || watchlist.some((item) => item.symbol === nextSymbol)) return;
    try {
      await addWatchlistItem(nextSymbol);
      await loadOverview();
    } catch (err) {
      setError(err instanceof Error ? err.message : "添加自选失败");
    }
  }

  async function removeWatchStock(symbolToRemove: string) {
    try {
      const result = await deleteWatchlistItem(symbolToRemove);
      setWatchlist(result.items);
      setOverviewQuotes((current) => {
        const next = { ...current };
        delete next[symbolToRemove];
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除自选失败");
    }
  }

  async function moveWatchStock(targetSymbol: string) {
    if (!draggingSymbol || draggingSymbol === targetSymbol) return;
    const fromIndex = watchlist.findIndex((item) => item.symbol === draggingSymbol);
    const toIndex = watchlist.findIndex((item) => item.symbol === targetSymbol);
    if (fromIndex < 0 || toIndex < 0) return;
    const next = [...watchlist];
    const [moved] = next.splice(fromIndex, 1);
    next.splice(toIndex, 0, moved);
    setWatchlist(next);
    setDraggingSymbol("");
    try {
      const result = await reorderWatchlist(next.map((item) => item.symbol));
      setWatchlist(result.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "自选股排序保存失败");
      await loadOverview();
    }
  }

  async function createSnapshot() {
    try {
      const snapshot = await createDataSnapshot(symbol, period, 80);
      setSnapshotId(snapshot.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "生成数据快照失败");
    }
  }

  async function runAnalysisTask(kind: "technical" | "news" | "capital_flow" | "standard") {
    setLoadingDetail(true);
    setError("");
    const taskMap = {
      technical: {
        mode: "technical",
        query: `分析 ${symbol} 的技术面结构，重点关注趋势、量价和指标。`,
        agent_keys: ["data_steward", "technical", "risk"],
        include_report: false
      },
      news: {
        mode: "news",
        query: `分析 ${symbol} 的近期新闻、公告和研报观点。`,
        agent_keys: ["news", "risk"],
        include_report: false
      },
      capital_flow: {
        mode: "capital_flow",
        query: `分析 ${symbol} 的资金流、北向、龙虎榜和两融变化。`,
        agent_keys: ["capital_flow", "risk"],
        include_report: false
      },
      standard: {
        mode: "standard",
        query: `生成 ${symbol} 的标准 A 股投研分析报告。`,
        agent_keys: ["data_steward", "technical", "news", "fundamental", "capital_flow", "risk", "research_director"],
        include_report: true
      }
    }[kind];
    try {
      const task = await createAnalysisTask({
        symbol,
        period,
        limit: 80,
        ...taskMap
      });
      setLatestTask(task);
      if (task.snapshot_id) {
        setSnapshotId(task.snapshot_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "分析任务创建失败");
    } finally {
      setLoadingDetail(false);
    }
  }

  function changeNewsPage(direction: 1 | -1) {
    setNewsPage((current) => Math.min(Math.max(current + direction, 0), newsPageCount - 1));
  }

  function toggleIndicator(indicator: string) {
    setSelectedIndicators((current) => {
      if (current.includes(indicator)) {
        return current.filter((item) => item !== indicator);
      }
      return [...current, indicator];
    });
  }

  if (viewMode === "detail") {
    const priceTone = toneByChange(quote?.change_percent);
    const displayName = quote?.name || klines?.name || symbol;
    const latestFinancial = financials?.items[0];
    const latestFundFlow = fundFlow?.items[fundFlow.items.length - 1];

    return (
      <div className="page-grid analysis-layout">
        <div className="main-column">
          <Panel
            title="股票详情"
            actions={
              <>
                <button className="btn btn-secondary" onClick={() => setViewMode("overview")} type="button">
                  <ArrowLeft size={14} />
                  返回概览
                </button>
                <button className="btn btn-secondary" type="button">加入观察</button>
                <button className="btn btn-primary" onClick={createSnapshot} type="button">生成分析快照</button>
              </>
            }
          >
            <div className="search-row">
              <input
                className="input mono"
                onChange={(event) => setSymbolInput(event.target.value)}
                onKeyDown={(event) => event.key === "Enter" && submitSearch()}
                placeholder="输入股票代码，例如 300750"
                value={symbolInput}
              />
              <button className="btn btn-primary" onClick={submitSearch} type="button">
                <Search size={14} />
                查询
              </button>
              <button className="icon-btn" disabled={loadingDetail} onClick={() => loadDetail(symbol, period)} title="刷新行情" type="button">
                <RefreshCw size={15} />
              </button>
            </div>
            {error ? <div className="notice error">{error}</div> : null}
            <div className="metrics-grid six">
              <Metric label={`${displayName} 最新价`} value={formatOptional(quote?.price)} meta={`${formatOptional(quote?.change_percent, "%")} 今日`} tone={priceTone} />
              <Metric label="成交额" value={formatOptional(quote?.amount, "万", 0)} meta={`成交量 ${formatOptional(quote?.volume, "手", 0)}`} />
              <Metric label="换手率" value={formatOptional(quote?.turnover_rate, "%")} meta="来自腾讯行情" />
              <Metric label="总市值" value={formatOptional(quote?.market_cap, "亿")} meta="接口原始单位" />
              <Metric label="PE(TTM)" value={formatOptional(quote?.pe_ttm)} meta="估值指标" />
              <Metric label="PB" value={formatOptional(quote?.pb)} meta={`更新时间 ${formatQuoteTime(quote?.timestamp ?? "")}`} />
            </div>
          </Panel>

          <Panel
            title="行情图表"
            description={`当前使用 ${klines?.provider_key ?? "-"}，共 ${bars.length} 条 K 线。指标：${selectedIndicators.join("、") || "无"}`}
            actions={
              <div className="segmented">
                {[["5m", "5分"], ["30m", "30分"], ["60m", "60分"], ["daily", "日K"], ["weekly", "周K"], ["monthly", "月K"]].map(([value, label]) => (
                  <button className={period === value ? "active" : ""} key={value} onClick={() => setPeriod(value)} type="button">
                    {label}
                  </button>
                ))}
              </div>
            }
          >
            <div className="chart-shell">
              <div className="chart-candle-layer">
                {bars.length ? (
                  <svg className="chart-candle-svg" viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="K 线图">
                    {bars.map((bar, index) => {
                      const range = Math.max(chartStats.maxHigh - chartStats.minLow, 1);
                      const x = bars.length === 1 ? 50 : (index / (bars.length - 1)) * 100;
                      const yHigh = 92 - ((bar.high - chartStats.minLow) / range) * 82;
                      const yLow = 92 - ((bar.low - chartStats.minLow) / range) * 82;
                      const yOpen = 92 - ((bar.open - chartStats.minLow) / range) * 82;
                      const yClose = 92 - ((bar.close - chartStats.minLow) / range) * 82;
                      const bodyTop = Math.min(yOpen, yClose);
                      const bodyHeight = Math.max(Math.abs(yClose - yOpen), 2.2);
                      const bodyWidth = Math.max(Math.min(72 / bars.length, 1.35), 0.72);
                      const tone = bar.close >= bar.open ? "up" : "down";
                      return (
                        <g className={`svg-candle ${tone}`} key={bar.time}>
                          <title>{`${bar.time} 开 ${bar.open} 高 ${bar.high} 低 ${bar.low} 收 ${bar.close}`}</title>
                          <line x1={x} x2={x} y1={yHigh} y2={yLow} />
                          <rect x={x - bodyWidth / 2} y={bodyTop} width={bodyWidth} height={bodyHeight} />
                        </g>
                      );
                    })}
                  </svg>
                ) : (
                  <span className="chart-empty">暂无 K 线数据</span>
                )}
              </div>
              {selectedIndicators.includes("成交量") ? (
                <div className="chart-volume-overlay" aria-label="成交量叠层">
                  {bars.map((bar) => (
                    <i key={bar.time} style={{ height: `${10 + Math.min(bar.volume / Math.max(...bars.map((item) => item.volume), 1), 1) * 52}px` }} />
                  ))}
                </div>
              ) : null}
              <svg className="chart-line-overlay" viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="技术指标折线">
                {indicatorLines.map((line) => (
                  <polyline key={line.key} points={line.points} stroke={line.color} />
                ))}
              </svg>
              <div className="chart-indicator-tags">
                {indicatorLines.map((line) => (
                  <span key={line.key} style={{ borderColor: line.color, color: line.color }}>{line.label}</span>
                ))}
              </div>
            </div>
            <div className="toggle-row indicator-row">
              {indicators.map((item) => (
                <label className="check-chip" key={item}>
                  <input checked={selectedIndicators.includes(item)} onChange={() => toggleIndicator(item)} type="checkbox" />
                  <span>{item}</span>
                </label>
              ))}
            </div>
          </Panel>

          <Panel
            title="新闻快讯"
            description="底部快讯窗口支持上下翻页，便于在看图后快速扫事件。"
            actions={
              <div className="news-pager">
                <button className="icon-btn" disabled={newsPage === 0} onClick={() => changeNewsPage(-1)} title="上一页" type="button">
                  <ArrowUp size={14} />
                </button>
                <span>{newsPage + 1} / {newsPageCount}</span>
                <button className="icon-btn" disabled={newsPage >= newsPageCount - 1} onClick={() => changeNewsPage(1)} title="下一页" type="button">
                  <ArrowDown size={14} />
                </button>
              </div>
            }
          >
            <div className="news-scroll-window">
              {visibleNews.length ? (
                visibleNews.map((item) => (
                  <article className="news-card" key={item.id}>
                    <div>
                      <span className="mono">{formatNewsTime(item.publish_time)}</span>
                      <StatusBadge tone={item.level === "A" || item.level === "B" ? "amber" : "neutral"}>{item.source || news?.provider_key}</StatusBadge>
                    </div>
                    <strong>{item.title || item.content}</strong>
                    {item.title && item.content ? <p>{item.content}</p> : null}
                  </article>
                ))
              ) : (
                <div className="news-empty">暂无新闻快讯</div>
              )}
            </div>
          </Panel>
        </div>

        <aside className="side-column">
          <Panel title="数据新鲜度">
            <div className="kv-list">
              <div><span>行情源</span><strong>{quote?.provider_key ?? "-"}</strong></div>
              <div><span>K 线源</span><strong>{klines?.provider_key ?? "-"}</strong></div>
              <div><span>新闻源</span><strong>{news?.provider_key ?? "-"}</strong></div>
              <div><span>公告源</span><strong>{announcements?.provider_key ?? "-"}</strong></div>
              <div><span>财务源</span><strong>{fundamentals?.provider_key ?? financials?.provider_key ?? "-"}</strong></div>
              <div><span>资金源</span><strong>{fundFlow?.provider_key ?? "-"}</strong></div>
              <div><span>行情时间</span><strong>{formatQuoteTime(quote?.timestamp ?? "")}</strong></div>
              <div><span>最近快照</span><strong>{snapshotId ? `#${snapshotId}` : "-"}</strong></div>
              <div><span>时间显示</span><strong>Asia/Shanghai</strong></div>
            </div>
          </Panel>
          <Panel title="基本面摘要" description="估值和最近一期利润表，作为基本面 Agent 的输入。">
            <div className="kv-list">
              <div><span>总市值</span><strong>{formatLargeMoney(numericMetric(fundamentals, "market_cap"))}</strong></div>
              <div><span>PE(TTM)</span><strong>{formatOptional(numericMetric(fundamentals, "pe_ttm"), "", 2)}</strong></div>
              <div><span>PB</span><strong>{formatOptional(numericMetric(fundamentals, "pb"), "", 2)}</strong></div>
              <div><span>ROE</span><strong>{formatOptional(numericMetric(fundamentals, "roe"), "%", 2)}</strong></div>
              <div><span>报告期</span><strong>{latestFinancial?.report_date?.slice(0, 10) ?? "-"}</strong></div>
              <div><span>归母净利</span><strong>{formatLargeMoney(Number(latestFinancial?.values.PARENT_NETPROFIT))}</strong></div>
            </div>
          </Panel>
          <Panel title="资金流" description="东方财富个股资金流，正值表示净流入。">
            <div className="kv-list">
              <div><span>日期</span><strong>{latestFundFlow?.date ?? "-"}</strong></div>
              <div><span>主力净流入</span><strong className={toneByChange(latestFundFlow?.main_net_inflow)}>{formatLargeMoney(latestFundFlow?.main_net_inflow)}</strong></div>
              <div><span>超大单</span><strong className={toneByChange(latestFundFlow?.super_large_net_inflow)}>{formatLargeMoney(latestFundFlow?.super_large_net_inflow)}</strong></div>
              <div><span>大单</span><strong className={toneByChange(latestFundFlow?.large_net_inflow)}>{formatLargeMoney(latestFundFlow?.large_net_inflow)}</strong></div>
            </div>
          </Panel>
          <Panel title="公司公告" description="来自交易所公告聚合源，后续可进入知识库和 Agent 引用。">
            <div className="announcement-list">
              {(announcements?.items ?? []).length ? (
                announcements?.items.map((item) => (
                  <article className="announcement-item" key={item.id}>
                    <div>
                      <span className="mono">{item.publish_time || "-"}</span>
                      <StatusBadge tone="neutral">{item.category || item.source || "公告"}</StatusBadge>
                    </div>
                    {item.url ? (
                      <a href={item.url} rel="noreferrer" target="_blank">{item.title}</a>
                    ) : (
                      <strong>{item.title}</strong>
                    )}
                  </article>
                ))
              ) : (
                <div className="news-empty">暂无公司公告</div>
              )}
            </div>
          </Panel>
          <Panel title="交易行为与供给压力" description="龙虎榜、解禁和融资融券，作为风控与资金行为 Agent 的输入。">
            <div className="kv-list">
              <div><span>龙虎榜日期</span><strong>{dragonTiger?.items[0]?.trade_date?.slice(0, 10) ?? "-"}</strong></div>
              <div><span>龙虎榜净买入</span><strong className={toneByChange(dragonTiger?.items[0]?.net_amount)}>{formatLargeMoney(dragonTiger?.items[0]?.net_amount)}</strong></div>
              <div><span>最近解禁</span><strong>{lockupExpiry?.items[0]?.free_date?.slice(0, 10) ?? "-"}</strong></div>
              <div><span>解禁市值</span><strong>{formatLargeMoney(lockupExpiry?.items[0]?.market_cap)}</strong></div>
              <div><span>两融余额</span><strong>{formatLargeMoney(marginTrading?.items[0]?.margin_balance)}</strong></div>
              <div><span>融资净买入</span><strong className={toneByChange(marginTrading?.items[0]?.financing_net_buy_amount)}>{formatLargeMoney(marginTrading?.items[0]?.financing_net_buy_amount)}</strong></div>
            </div>
          </Panel>
          <Panel title="研报观点" description="研报属于观点数据，只作为参考和引用线索。">
            <div className="announcement-list">
              {(researchReports?.items ?? []).length ? (
                researchReports?.items.map((item) => (
                  <article className="announcement-item" key={item.id}>
                    <div>
                      <span>{item.org_name || "机构"}</span>
                      <StatusBadge tone={item.rating ? "amber" : "neutral"}>{item.rating || "未评级"}</StatusBadge>
                    </div>
                    {item.url ? (
                      <a href={item.url} rel="noreferrer" target="_blank">{item.title}</a>
                    ) : (
                      <strong>{item.title}</strong>
                    )}
                  </article>
                ))
              ) : (
                <div className="news-empty">暂无研报观点</div>
              )}
            </div>
          </Panel>
          <Panel title="分析入口">
            <div className="button-stack">
              <button className="btn btn-primary" disabled={loadingDetail} onClick={() => runAnalysisTask("technical")} type="button">运行技术面 Agent</button>
              <button className="btn btn-secondary" disabled={loadingDetail} onClick={() => runAnalysisTask("news")} type="button">运行新闻 Agent</button>
              <button className="btn btn-secondary" disabled={loadingDetail} onClick={() => runAnalysisTask("capital_flow")} type="button">运行资金流 Agent</button>
              <button className="btn btn-secondary" disabled={loadingDetail} onClick={() => runAnalysisTask("standard")} type="button">生成标准报告</button>
            </div>
            {latestTask ? (
              <div className="task-mini">
                <span>最新任务</span>
                <strong className="mono">{latestTask.task_key}</strong>
                <small>{latestTask.status} · {latestTask.stage} · {latestTask.progress}%</small>
              </div>
            ) : null}
          </Panel>
        </aside>
      </div>
    );
  }

  return (
    <div className="page-grid overview-layout">
      <div className="main-column">
        <Panel
          title="数据概览"
          description="概览页用于筛选标的和观察市场，不承载单只股票的完整分析。"
          actions={
            <>
              <button className="btn btn-secondary" disabled={loadingOverview} onClick={loadOverview} type="button">
                <RefreshCw size={14} />
                刷新概览
              </button>
              <button className="btn btn-secondary" onClick={addWatchStock} type="button">
                <Plus size={14} />
                添加自选
              </button>
              <div className="search-row compact-search">
                <input
                  className="input mono"
                  onChange={(event) => setSymbolInput(event.target.value)}
                  onKeyDown={(event) => event.key === "Enter" && submitSearch()}
                  placeholder="代码直达详情"
                  value={symbolInput}
                />
                <button className="btn btn-primary" onClick={submitSearch} type="button">查看详情</button>
              </div>
            </>
          }
        >
          <div className="tab-strip overview-tabs">
            {[["watchlist", "自选股"], ["recommended", "推荐股"], ["market", "大盘情况"]].map(([key, label]) => (
              <button className={activeTab === key ? "active" : ""} key={key} onClick={() => setActiveTab(key as OverviewTab)} type="button">
                {label}
              </button>
            ))}
          </div>
          {error ? <div className="notice error">{error}</div> : null}
          {activeTab === "watchlist" ? (
            <StockTable
              draggingSymbol={draggingSymbol}
              seeds={watchlist}
              quotes={overviewQuotes}
              onDragStart={setDraggingSymbol}
              onDropOn={moveWatchStock}
              onOpenDetail={openDetail}
              onRemove={removeWatchStock}
            />
          ) : null}
          {activeTab === "recommended" ? <RecommendedTable seeds={recommendedSeeds} quotes={overviewQuotes} onOpenDetail={openDetail} /> : null}
          {activeTab === "market" ? (
            <MarketOverview
              concepts={conceptSnapshots}
              cpi={macroCpi}
              northbound={northboundFlow}
              pmi={macroPmi}
              sectors={sectorSnapshots}
            />
          ) : null}
        </Panel>
      </div>

      <aside className="side-column">
        <Panel title="概览指标">
          <div className="metrics-grid overview-metrics">
            <Metric label="自选股" value={`${watchlist.length}`} meta="当前观察池" />
            <Metric label="推荐股" value={`${recommendedSeeds.length}`} meta="策略候选池" />
            <Metric label="上涨数量" value={`${Object.values(overviewQuotes).filter((item) => (item.change_percent ?? 0) > 0).length}`} meta="来自实时行情" tone="up" />
            <Metric label="下跌数量" value={`${Object.values(overviewQuotes).filter((item) => (item.change_percent ?? 0) < 0).length}`} meta="来自实时行情" tone="down" />
          </div>
        </Panel>
        <Panel title="后续模块">
          <div className="button-stack">
            <button className="btn btn-secondary" type="button">批量刷新自选股</button>
            <button className="btn btn-secondary" type="button">生成推荐理由</button>
            <button className="btn btn-secondary" type="button">查看数据源日志</button>
          </div>
        </Panel>
      </aside>
    </div>
  );
}

function StockTable({
  seeds,
  draggingSymbol,
  quotes,
  onDragStart,
  onDropOn,
  onOpenDetail,
  onRemove
}: {
  seeds: Array<StockSeed | WatchlistItem>;
  draggingSymbol: string;
  quotes: Record<string, RealtimeQuote>;
  onDragStart: (symbol: string) => void;
  onDropOn: (symbol: string) => void;
  onOpenDetail: (symbol: string) => void;
  onRemove: (symbol: string) => void;
}) {
  return (
    <div className="table-wrap overview-table">
      <table>
        <thead><tr><th></th><th>代码</th><th>名称</th><th>最新价</th><th>涨跌幅</th><th>成交额</th><th>PE</th><th>更新时间</th><th>操作</th></tr></thead>
        <tbody>
          {seeds.map((seed) => {
            const quote = quotes[seed.symbol];
            return (
              <tr
                className={draggingSymbol === seed.symbol ? "dragging-row" : ""}
                draggable
                key={seed.symbol}
                onDragOver={(event) => event.preventDefault()}
                onDragStart={() => onDragStart(seed.symbol)}
                onDrop={() => onDropOn(seed.symbol)}
              >
                <td>
                  <button className="icon-btn row-handle" title="拖动排序" type="button">
                    <GripVertical size={13} />
                  </button>
                </td>
                <td className="mono">{seed.symbol}</td>
                <td>{quote?.name || seed.name}</td>
                <td className="mono">{formatOptional(quote?.price)}</td>
                <td className={toneByChange(quote?.change_percent)}>{formatOptional(quote?.change_percent, "%")}</td>
                <td className="mono">{formatOptional(quote?.amount, "万", 0)}</td>
                <td className="mono">{formatOptional(quote?.pe_ttm)}</td>
                <td>{formatQuoteTime(quote?.timestamp ?? "")}</td>
                <td>
                  <div className="table-actions">
                    <button className="btn btn-table" onClick={() => onOpenDetail(seed.symbol)} type="button">详情</button>
                    <button className="icon-btn row-delete" onClick={() => onRemove(seed.symbol)} title="删除自选" type="button">
                      <Trash2 size={13} />
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function RecommendedTable({ seeds, quotes, onOpenDetail }: { seeds: StockSeed[]; quotes: Record<string, RealtimeQuote>; onOpenDetail: (symbol: string) => void }) {
  return (
    <div className="table-wrap overview-table">
      <table>
        <thead><tr><th>评分</th><th>代码</th><th>名称</th><th>最新价</th><th>涨跌幅</th><th>推荐理由</th><th>操作</th></tr></thead>
        <tbody>
          {seeds.map((seed) => {
            const quote = quotes[seed.symbol];
            return (
              <tr key={seed.symbol}>
                <td><StatusBadge tone={(seed.score ?? 0) >= 80 ? "green" : "amber"}>{seed.score}</StatusBadge></td>
                <td className="mono">{seed.symbol}</td>
                <td>{quote?.name || seed.name}</td>
                <td className="mono">{formatOptional(quote?.price)}</td>
                <td className={toneByChange(quote?.change_percent)}>{formatOptional(quote?.change_percent, "%")}</td>
                <td>{seed.reason}</td>
                <td><button className="btn btn-table" onClick={() => onOpenDetail(seed.symbol)} type="button">详情</button></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function MarketOverview({
  concepts,
  cpi,
  northbound,
  pmi,
  sectors
}: {
  concepts: SectorSnapshotResponse | null;
  cpi: MacroIndicatorResponse | null;
  northbound: NorthboundFlowResponse | null;
  pmi: MacroIndicatorResponse | null;
  sectors: SectorSnapshotResponse | null;
}) {
  const latestNorthbound = northbound?.items[0];
  const latestCpi = cpi?.items[0];
  const latestPmi = pmi?.items[0];
  return (
    <div className="overview-market">
      <div className="metrics-grid four">
        <Metric label="CPI 同比" value={formatOptional(Number(latestCpi?.values.NATIONAL_SAME), "%", 1)} meta={latestCpi?.time_label || "宏观通胀"} />
        <Metric label="制造业 PMI" value={formatOptional(Number(latestPmi?.values.MAKE_INDEX), "", 1)} meta={latestPmi?.time_label || "景气指标"} />
        <Metric label="行业主线" value={sectors?.items[0]?.name ?? "待加载"} meta={formatLargeMoney(sectors?.items[0]?.main_net_inflow)} />
        <Metric label="概念主线" value={concepts?.items[0]?.name ?? "待加载"} meta={formatLargeMoney(concepts?.items[0]?.main_net_inflow)} />
      </div>
      <div className="metrics-grid four">
        <Metric label="北向成交" value={formatOptional(latestNorthbound?.deal_amount, "万", 1)} meta={latestNorthbound?.lead_stock_name || "东方财富沪深港通"} />
        <Metric label="北向类型" value={latestNorthbound?.mutual_type || "-"} meta={latestNorthbound?.trade_date?.slice(0, 10) || "最近记录"} />
        <Metric label="市场温度" value="中性偏强" meta="成交额与涨跌家数综合判断" />
        <Metric label="风险提示" value="高低切换" meta="题材快速轮动，追高风险上升" tone="down" />
      </div>
      <div className="table-wrap overview-table">
        <table>
          <thead><tr><th>市场</th><th>状态</th><th>涨跌幅</th><th>观察</th></tr></thead>
          <tbody>
            {marketRows.map(([name, status, change, note]) => (
              <tr key={name}>
                <td>{name}</td>
                <td><StatusBadge tone={status === "修复" ? "green" : status === "偏弱" ? "red" : "amber"}>{status}</StatusBadge></td>
                <td className={change.startsWith("+") ? "up" : "down"}>{change}</td>
                <td>{note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="market-snapshot-grid">
        <SectorTable title="行业资金流" rows={sectors?.items ?? []} />
        <SectorTable title="概念资金流" rows={concepts?.items ?? []} />
      </div>
    </div>
  );
}

function SectorTable({ title, rows }: { title: string; rows: SectorSnapshotItem[] }) {
  return (
    <div className="table-wrap overview-table compact sector-table">
      <table>
        <thead><tr><th>{title}</th><th>涨跌幅</th><th>主力净流入</th></tr></thead>
        <tbody>
          {rows.length ? rows.map((row) => (
            <tr key={row.code}>
              <td>{row.name}</td>
              <td className={toneByChange(row.change_percent)}>{formatOptional(row.change_percent, "%")}</td>
              <td className={toneByChange(row.main_net_inflow)}>{formatLargeMoney(row.main_net_inflow)}</td>
            </tr>
          )) : (
            <tr><td colSpan={3}>暂无数据</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
