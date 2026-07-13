'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Cloud,
  TrendingUp,
  TrendingDown,
  Activity,
  DollarSign,
  Percent,
  ShieldCheck,
  ShieldAlert,
  RefreshCcw,
  History,
  Clock,
  ExternalLink,
  ChevronRight,
  Plus,
  ArrowUpRight,
  ArrowDownRight,
  Zap,
  LayoutDashboard,
  Wallet,
  Settings,
  X
} from 'lucide-react';
import weatherApi, { Opportunity, Position, Stats, Status, EdgeHarvestOpportunity, EdgeHarvestStats, Order, RuntimeSettings } from '@/lib/api';

// --- Helpers ---

// targetDate is the CITY-local calendar date ("2026-06-11") from the market
// slug; comparing against the operator's local today is coarse but good
// enough for a today/tomorrow/Nd countdown.
const resolutionLabel = (targetDate: string): string => {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(targetDate ?? '');
  if (!m) return '—';
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const target = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])).getTime();
  const days = Math.round((target - today) / 86400000);
  if (days < 0) return 'settling';
  if (days === 0) return 'today';
  if (days === 1) return 'tomorrow';
  return `${days}d`;
};

// --- Components ---

const StatCard = ({ title, value, subtext, icon: Icon, trend, loading, valueClass }: any) => (
  <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-6 backdrop-blur-sm hover:border-zinc-700 transition-all group">
    <div className="flex justify-between items-start mb-4">
      <div className="p-2 bg-zinc-800 rounded-lg group-hover:bg-zinc-700 transition-colors">
        <Icon size={20} className="text-zinc-400 group-hover:text-blue-400" />
      </div>
      {trend && (
        <div className={`flex items-center text-xs font-medium ${trend > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
          {trend > 0 ? <ArrowUpRight size={14} className="mr-1" /> : <ArrowDownRight size={14} className="mr-1" />}
          {Math.abs(trend)}%
        </div>
      )}
    </div>
    <div className="space-y-1">
      <h3 className="text-zinc-500 text-sm font-medium">{title}</h3>
      {loading ? (
        <div className="h-8 w-24 bg-zinc-800 animate-pulse rounded"></div>
      ) : (
        <div className={`text-2xl font-bold ${valueClass || 'text-zinc-100'}`}>{value}</div>
      )}
      {subtext && <p className="text-zinc-600 text-xs font-medium">{subtext}</p>}
    </div>
  </div>
);

const OpportunityRow = ({ opt, onTrade, trading }: { opt: Opportunity, onTrade: (opt: Opportunity, size: number) => void, trading: boolean }) => {
  const [size, setSize] = React.useState(opt.positionSize);

  return (
    <tr className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors group">
      <td className="py-4 pl-4 pr-3 text-sm sm:pl-6">
        <div className="flex items-center">
          <div className="h-10 w-10 flex-shrink-0 bg-zinc-800 rounded-lg flex items-center justify-center mr-3">
            <Cloud size={20} className="text-zinc-400" />
          </div>
          <div>
            <div className="font-semibold text-zinc-200">{opt.city}</div>
            <div className="text-zinc-500 text-xs">{opt.targetDate}</div>
          </div>
        </div>
      </td>
      <td className="px-3 py-4 text-sm text-zinc-400">
        <div className="font-medium text-zinc-200">{opt.bucket}</div>
        <div className="text-xs text-zinc-500">Forecast: {(opt.forecastTemp ?? 0).toFixed(1)}°</div>
      </td>
      <td className="px-3 py-4 text-sm">
        <div className="flex items-center space-x-2">
          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${opt.tier === 'HIGH' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' :
            opt.tier === 'MEDIUM' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
              'bg-zinc-500/10 text-zinc-400 border border-zinc-500/20'
            }`}>
            {opt.tier}
          </span>
          <span className={`font-medium ${(opt.edge ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{((opt.edge ?? 0) * 100).toFixed(1)}% Edge</span>
        </div>
      </td>
      <td className="px-3 py-4 text-sm">
        <div className="flex flex-col">
          <span className="text-zinc-300 font-medium">${(opt.yesPrice ?? 0).toFixed(2)} Yes / ${(opt.noPrice ?? 0).toFixed(2)} No</span>
          <span className="text-zinc-600 text-xs">${(opt.liquidity ?? 0).toFixed(0)} Liquidity</span>
        </div>
      </td>
      <td className="px-3 py-4 text-sm text-center">
        <span className={`font-bold ${opt.recommendedSide === 'YES' ? 'text-emerald-400' : 'text-rose-400'}`}>
          {opt.recommendedSide}
        </span>
        <div className="flex items-center justify-center mt-1 space-x-1">
          <span className="text-zinc-500 text-[10px]">$</span>
          <input
            type="number"
            value={size}
            onChange={(e) => setSize(Number(e.target.value))}
            step="0.01"
            min="0.01"
            className="w-16 bg-zinc-800 border border-zinc-700 rounded px-1.5 py-0.5 text-xs text-zinc-200 text-center focus:outline-none focus:border-blue-500"
          />
        </div>
        <div className="text-[10px] text-zinc-600 mt-0.5">Rec: ${(opt.positionSize ?? 0).toFixed(2)}</div>
      </td>
      <td className="py-4 pl-3 pr-4 text-right text-sm font-medium sm:pr-6">
        <div className="flex justify-end space-x-2">
          {opt.marketUrl && (
            <a
              href={opt.marketUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 text-zinc-500 hover:text-zinc-300 border border-zinc-800 rounded-lg transition-colors"
            >
              <ExternalLink size={16} />
            </a>
          )}
          <button
            onClick={() => onTrade(opt, size)}
            disabled={trading || size <= 0}
            className="bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-800 disabled:text-zinc-600 text-white font-bold py-1.5 px-3 rounded-lg flex items-center shadow-lg shadow-blue-900/20 transition-all hover:scale-[1.02] active:scale-[0.98]"
          >
            {trading ? <RefreshCcw size={14} className="animate-spin mr-1.5" /> : <Zap size={14} className="mr-1.5" />}
            Execute
          </button>
        </div>
      </td>
    </tr>
  );
};

// Codex C v2: type the row against the API contract (was `any` before, so
// the frontend silently accepted breaking changes to marketType/acceptingOrders
// fields without compile-time check).
type EdgeHarvestRowOpp = EdgeHarvestOpportunity;

const EdgeHarvestRow = ({ opp, onTrade, trading, isLive }: { opp: EdgeHarvestRowOpp, onTrade: (opp: EdgeHarvestRowOpp, size: number) => void, trading: boolean, isLive: boolean }) => {
  const dollarLiquidity = (opp.bestAskSize ?? 0) * (opp.bestAskPrice ?? 0);
  const defaultSize = Math.max(1, Math.floor(Math.min(dollarLiquidity, 100)));
  const [size, setSize] = React.useState(defaultSize);

  // Keyed on row identity, not on liquidity — a 60s poll refresh must never
  // clobber a hand-typed size.
  React.useEffect(() => {
    setSize(defaultSize);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opp.id]);

  // bestAskPrice <= 0 means "no book data", not "free" — fall back to the
  // side's scan price, and never display $0.00 as a price.
  const rawAsk = opp.bestAskPrice ?? 0;
  const sidePrice = (opp.recommendedSide === 'YES' ? opp.yesPrice : opp.noPrice) ?? 0;
  const effectiveAsk = rawAsk > 0 ? rawAsk : sidePrice > 0 ? sidePrice : null;

  const riskColor = opp.riskTier === 'LOW' ? 'text-emerald-400' : opp.riskTier === 'MEDIUM' ? 'text-yellow-400' : 'text-rose-400';
  const riskBg = opp.riskTier === 'LOW' ? 'bg-emerald-500/10' : opp.riskTier === 'MEDIUM' ? 'bg-yellow-500/10' : 'bg-rose-500/10';
  // PD-340 v3: settlement-basis status drives presentation. Missing → UNCORRECTED (fail-honest).
  const recStatus = opp.recommendationStatus ?? 'UNCORRECTED';
  const roomColor = opp.nowcastHardBound ? 'text-cyan-200 bg-cyan-500/15 border-cyan-400/50'
    : recStatus === 'ROOM' ? 'text-emerald-300 bg-emerald-500/10 border-emerald-500/40'
    : recStatus === 'NO_ROOM' ? 'text-rose-300 bg-rose-500/15 border-rose-500/40'
    : 'text-zinc-400 bg-zinc-700/30 border-zinc-600/40';
  const roomLabel = opp.nowcastHardBound ? 'HARD BOUND' : recStatus === 'ROOM' ? 'ROOM' : recStatus === 'NO_ROOM' ? 'NO ROOM' : 'UNVERIFIED';
  const dlt = opp.effectiveDeltaC ?? 0;
  const reason = opp.nowcastHardBound
    ? `${opp.nowcastStation ?? 'authoritative station'} observed ${opp.observedExtreme?.toFixed(1) ?? '—'}° and eliminated this bucket`
    : opp.openBucket
    ? 'open-ended bucket — bet against the whole tail'
    : opp.forecastUncertain
    ? `forecast shaky — ±${(opp.modelSpread ?? 0).toFixed(0)}° spread${opp.frontWarning ? ' + front' : ''}`
    : recStatus === 'UNCORRECTED'
    ? (opp.basisStatus === 'uncorrected-coords-suspect'
        ? `erratic settlement · n=${opp.basisN ?? 0}`
        : `unproven · n=${opp.basisN ?? 0}`)
    : `settles ${dlt >= 0 ? '+' : ''}${dlt.toFixed(1)}°C vs your spot · n=${opp.basisN ?? 0}`;
  const rowMuted = recStatus !== 'ROOM' && !opp.nowcastHardBound ? 'opacity-60' : '';

  return (
    <tr className={`border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors group ${rowMuted}`}>
      <td className="py-4 pl-4 pr-3 sm:pl-6">
        <div className="flex flex-col">
          <span className="font-semibold text-zinc-100 uppercase text-sm">{opp.city}</span>
          <span className="text-zinc-500 text-xs">{opp.targetDate}</span>
          <span className={`text-[10px] font-bold mt-1 px-1.5 py-0.5 rounded w-fit border ${
            opp.marketType === 'low'
              ? 'bg-sky-500/15 text-sky-300 border-sky-500/40'
              : 'bg-amber-500/15 text-amber-300 border-amber-500/40'
          }`}>
            {opp.marketType === 'low' ? 'LOW TEMP' : 'HIGH TEMP'}
          </span>
          {opp.frontWarning && (
            <span className="text-rose-400 text-xs mt-1 flex items-center">
              <ShieldAlert size={12} className="mr-1" />
              Front Warning
            </span>
          )}
        </div>
      </td>
      <td className="px-3 py-4 text-sm font-medium text-zinc-200">
        <div className="flex flex-col">
          <span>{opp.bucket}</span>
          <span className="text-[10px] text-zinc-500 mt-0.5">
            {opp.marketType === 'low' ? 'lowest temp' : 'highest temp'}
          </span>
        </div>
      </td>
      <td className="px-3 py-4">
        <div className="flex flex-col">
          <span className="text-sm text-zinc-200">{(opp.forecastTemp ?? 0).toFixed(0)}°{opp.bucket?.includes('°C') ? 'C' : 'F'}</span>
          {(opp.modelSpread ?? 0) > 0 && (
            <span className="text-xs text-zinc-500">±{(opp.modelSpread ?? 0).toFixed(1)}° spread</span>
          )}
        </div>
      </td>
      <td className="px-3 py-4">
        {recStatus === 'UNCORRECTED' ? (
          <div className="flex flex-col">
            <span className="text-sm text-zinc-400">{opp.bandsAway ?? 0} bands <span className="text-[10px] text-zinc-600">(raw)</span></span>
            <span className="text-[10px] text-zinc-500 mt-0.5">{reason}</span>
          </div>
        ) : (
          <div className="flex flex-col">
            <span className={`text-sm font-semibold ${recStatus === 'ROOM' ? 'text-emerald-300' : 'text-rose-300'}`}>
              {opp.correctedBands ?? 0} bands <span className="text-[10px] text-zinc-500">(corrected)</span>
            </span>
            <span className="text-[10px] text-zinc-500 mt-0.5">was {opp.bandsAway ?? 0} raw · {reason}</span>
          </div>
        )}
      </td>
      <td className="px-4 py-3 text-sm text-gray-300">{effectiveAsk != null ? `$${effectiveAsk.toFixed(2)}` : '—'}</td>
      <td className="px-4 py-3 text-sm text-gray-400">${dollarLiquidity.toFixed(0)}</td>
      <td className="px-3 py-4">
        <span className={`text-sm font-semibold ${opp.netWinReturnPct == null ? 'text-amber-400' : 'text-emerald-400'}`}>
          {opp.netWinReturnPct == null ? 'unknown' : `${opp.netWinReturnPct.toFixed(2)}%`}
        </span>
        <div className="text-[10px] text-zinc-500" title={`${opp.feeModel ?? 'fee metadata unavailable'} · ${opp.feeSource ?? 'UNKNOWN'}`}>
          gross {(opp.grossReturnPct ?? opp.potentialReturnPct ?? 0).toFixed(2)}% · {opp.feeKnown ? `${opp.feeRateBps ?? 0} bps rate` : 'fee unverified'}
        </div>
      </td>
      <td className="px-3 py-4">
        <div className="flex flex-col">
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full w-fit ${riskBg} ${riskColor}`}>
            {opp.riskTier ?? 'N/A'} ({opp.riskScore ?? 0}/10)
          </span>
          {(opp.riskFactors?.length ?? 0) > 0 && (
            <span className="text-xs text-zinc-500 mt-1 max-w-32 truncate" title={opp.riskFactors?.join(', ') ?? ''}>
              {opp.riskFactors?.[0] ?? ''}
            </span>
          )}
        </div>
      </td>
      <td className="px-3 py-4">
        <div className="flex flex-col items-start gap-1">
          <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${roomColor}`}
                title={`basis: ${opp.basisStatus ?? 'n/a'} · ${opp.basisConfidence ?? ''} · margin ${(opp.marginC ?? 0).toFixed(1)}°C`}>
            {roomLabel}
          </span>
          <span className={`text-xs font-mono ${
            opp.marginC == null ? 'text-zinc-600'
              : opp.marginC < 0 ? 'text-rose-400'
              : opp.marginC >= 1 ? 'text-emerald-400'
              : 'text-zinc-400'
          }`}>
            {opp.marginC != null ? `${opp.marginC >= 0 ? '+' : ''}${opp.marginC.toFixed(1)}°C` : '—'}
          </span>
          <div className="flex items-center gap-1">
            <span
              title={`basis n=${opp.basisN ?? 0}`}
              className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${
                opp.basisConfidence === 'TRUSTED' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                  : opp.basisConfidence === 'PROVISIONAL' ? 'bg-zinc-500/10 text-zinc-400 border-zinc-600/40'
                  : 'text-amber-400 border-amber-500/40'
              }`}
            >
              {opp.basisConfidence ?? 'UNPROVEN'}
            </span>
            {opp.openBucket && (
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-rose-500/15 text-rose-300 border border-rose-500/40">TAIL</span>
            )}
          </div>
        </div>
      </td>
      <td className="px-3 py-4 text-right sm:pr-6">
        <div className="flex items-center justify-end space-x-2">
          <div className="flex flex-col items-end">
            <input
              type="number"
              value={size}
              onChange={(e) => {
                const v = Number(e.target.value);
                setSize(Number.isFinite(v) && v >= 1 ? v : 1);
              }}
              className="w-16 px-2 py-1 bg-zinc-800 border border-zinc-700 rounded text-sm text-right text-zinc-200"
              min="1"
              max="300"
            />
            <span className="text-[10px] text-zinc-500 mt-0.5 whitespace-nowrap">
              risk ${size.toFixed(1)} → win {effectiveAsk != null ? `$${((size * (1 - effectiveAsk)) / effectiveAsk).toFixed(1)}` : '—'}
            </span>
          </div>
          <button
            onClick={() => onTrade(opp, size)}
            disabled={trading}
            title={recStatus !== 'ROOM' && !opp.nowcastHardBound ? `${roomLabel} — ${reason}` : undefined}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center disabled:bg-zinc-700 ${
              recStatus === 'ROOM' || opp.nowcastHardBound ? 'bg-emerald-600 hover:bg-emerald-500' : 'bg-zinc-700 hover:bg-zinc-600 text-zinc-300'
            } ${isLive ? 'ring-2 ring-rose-500/70' : ''}`}
          >
            {trading ? <RefreshCcw size={12} className="animate-spin" /> : `Buy ${opp.recommendedSide ?? 'NO'}${isLive ? ' · LIVE' : ''}`}
          </button>
          {opp.marketUrl && (
            <a href={opp.marketUrl} target="_blank" rel="noopener noreferrer" className="p-1.5 hover:bg-zinc-700 rounded-lg transition-colors">
              <ExternalLink size={14} className="text-zinc-400" />
            </a>
          )}
        </div>
      </td>
    </tr>
  );
};

export default function Dashboard() {
  const [status, setStatus] = useState<Status | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [edgeHarvestOpps, setEdgeHarvestOpps] = useState<EdgeHarvestOpportunity[]>([]);
  const [edgeHarvestStats, setEdgeHarvestStats] = useState<EdgeHarvestStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [trading, setTrading] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'edge' | 'harvest'>('harvest');
  const [activeView, setActiveView] = useState<'monitor' | 'portfolio' | 'orders'>('monitor');
  const [orders, setOrders] = useState<Order[]>([]);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [settings, setSettings] = useState<RuntimeSettings>({
    bankroll: 1000,
    isLive: false,
    maxOpportunityExposureUsd: 150,
    maxEventExposureUsd: 300,
    defaultOrderMode: 'GTC',
    maxScanAgeMin: 15,
    requoteTolerance: 0.02,
  });
  const [posFilter, setPosFilter] = useState<'open' | 'settled' | 'all'>('open');
  const [hideNoRoom, setHideNoRoom] = useState(true);
  const [cityFilter, setCityFilter] = useState('all');
  const [mtFilter, setMtFilter] = useState<'all' | 'high' | 'low'>('all');
  const [basisFilter, setBasisFilter] = useState<'all' | 'TRUSTED' | 'PROVISIONAL'>('all');
  const [nowTick, setNowTick] = useState(() => Date.now());

  // Refs, not state, so fetchData stays referentially stable for the poll interval.
  const fetchInFlightRef = useRef(false);
  const isSettingsOpenRef = useRef(false);
  useEffect(() => {
    isSettingsOpenRef.current = isSettingsOpen;
  }, [isSettingsOpen]);

  const fetchData = useCallback(async () => {
    if (fetchInFlightRef.current) return; // overlapping 60s polls skip, not stack
    fetchInFlightRef.current = true;
    try {
      const [statusRes, statsRes, oppsRes, posRes, ordersRes, edgeHarvestRes] = await Promise.all([
        weatherApi.getStatus(),
        weatherApi.getStats(),
        weatherApi.getOpportunities(),
        weatherApi.getPositions(),
        weatherApi.getOrders().catch(() => ({ orders: [] })),
        weatherApi.getEdgeHarvest().catch(() => null)
      ]);
      setStatus(statusRes);
      setStats(statsRes);
      setOpportunities(oppsRes.opportunities);
      setPositions(posRes.positions);
      setOrders(ordersRes.orders);
      // null = fetch failed (keep previous data); [] = legitimately-empty scan (clear table).
      if (edgeHarvestRes) {
        setEdgeHarvestOpps(edgeHarvestRes.opportunities);
      }
      // Don't clobber half-edited form values while the modal is open.
      if (!isSettingsOpenRef.current) {
        setSettings({
          bankroll: statusRes.bankroll,
          isLive: statusRes.isLive,
          maxOpportunityExposureUsd: statusRes.maxOpportunityExposureUsd ?? 150,
          maxEventExposureUsd: statusRes.maxEventExposureUsd ?? 300,
          defaultOrderMode: statusRes.defaultOrderMode ?? 'GTC',
          maxScanAgeMin: statusRes.maxScanAgeMin ?? 15,
          requoteTolerance: statusRes.requoteTolerance ?? 0.02,
        });
      }
    } catch (err) {
      console.error('Failed to fetch dashboard data', err);
    } finally {
      fetchInFlightRef.current = false;
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000); // 1 min poll
    return () => clearInterval(interval);
  }, [fetchData]);

  // 30s ticker so the scan-age chip stays honest between polls.
  useEffect(() => {
    const t = setInterval(() => setNowTick(Date.now()), 30000);
    return () => clearInterval(t);
  }, []);

  const handleScan = async () => {
    setScanning(true);
    try {
      if (activeTab === 'harvest') {
        const res = await weatherApi.scanEdgeHarvest();
        setEdgeHarvestOpps(res.opportunities);
        setEdgeHarvestStats(res.stats);
      } else {
        const res = await weatherApi.scan();
        setOpportunities(res.opportunities);
      }
      fetchData();
    } catch (err: any) {
      alert(err?.response?.data?.detail ?? err?.message ?? 'Scan failed');
    } finally {
      setScanning(false);
    }
  };

  type TradeResult = Awaited<ReturnType<typeof weatherApi.executeTrade>>;

  const reportTradeResult = (result: TradeResult, side: string, city: string, bucket: string, size: number) => {
    if (result.success) {
      if (result.persistenceError) {
        // The order is live on the book even though the local write failed —
        // a re-click would double the position.
        alert(
          `ORDER PLACED but NOT saved to local records — DO NOT re-click Buy.\n\n` +
          `${result.persistenceError}\n\nReconcile via the Orders tab / Polymarket.`
        );
      } else {
        const ex = result.executionResult;
        alert(`Placed ${side} — ${city} ${bucket} · $${size} @ $${ex?.price != null ? ex.price.toFixed(2) : '?'} (${ex?.status ?? 'unknown'})`);
      }
      fetchData();
    } else {
      alert(`Order failed: ${result.error || 'Unknown error'}`);
    }
  };

  const handleTrade = async (opt: Opportunity, size: number) => {
    setTrading(opt.id);
    try {
      const result = await weatherApi.executeTrade(opt.id, opt.recommendedSide, size);
      reportTradeResult(result, opt.recommendedSide, opt.city, opt.bucket, size);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      const msg = detail?.gate && Array.isArray(detail.reasons)
        ? `Blocked by trade gates:\n\n• ${detail.reasons.join('\n• ')}`
        : typeof detail === 'string' ? detail : err?.message || 'Unknown error';
      alert(`Trade execution failed: ${msg}`);
    } finally {
      setTrading(null);
    }
  };

  const handleEdgeHarvestTrade = async (opp: EdgeHarvestOpportunity, size: number) => {
    setTrading(opp.id);
    const side = opp.recommendedSide ?? 'NO';
    try {
      const result = await weatherApi.executeTrade(opp.id, side, size);
      reportTradeResult(result, side, opp.city, opp.bucket, size);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (err?.response?.status === 400 && detail?.gate) {
        const reasons: string[] = Array.isArray(detail.reasons) ? detail.reasons : [];
        if (window.confirm(`Blocked by trade gates:\n\n• ${reasons.join('\n• ')}\n\nTrade anyway (override)?`)) {
          try {
            const result = await weatherApi.executeTrade(opp.id, side, size, true);
            reportTradeResult(result, side, opp.city, opp.bucket, size);
          } catch (err2: any) {
            const d2 = err2?.response?.data?.detail;
            alert(typeof d2 === 'string' ? d2 : err2?.message || 'Trade execution failed');
          }
        }
      } else {
        // 409 stale-scan / 423 closed-book / 503 empty-cache arrive as plain string details.
        alert(typeof detail === 'string' ? detail : err?.message || 'Trade execution failed');
      }
    } finally {
      setTrading(null);
    }
  };

  const handleClosePosition = async (posId: string, outcome: 'WON' | 'LOST') => {
    try {
      await weatherApi.closePosition(posId, outcome);
      fetchData();
    } catch (err) {
      alert('Failed to close position');
    }
  };

  const handleCancelOrder = async (orderId: string) => {
    try {
      const result = await weatherApi.cancelOrder(orderId);
      if (result.success) {
        alert('Order cancelled');
        fetchData();
      }
    } catch (err) {
      alert('Failed to cancel order');
    }
  };

  const handleReconcileOrder = async (orderId: string) => {
    try {
      await weatherApi.reconcileOrder(orderId);
      await fetchData();
    } catch (err: any) {
      alert(err?.response?.data?.detail ?? err?.message ?? 'Failed to reconcile order');
    }
  };

  const handleSettingsUpdate = async () => {
    try {
      await weatherApi.updateSettings(settings);
      setIsSettingsOpen(false);
      fetchData();
    } catch (err) {
      alert('Failed to update settings');
    }
  };

  // Harvest filter bar — options derive from loaded rows so they survive filtering.
  const cityOptions = Array.from(new Set(edgeHarvestOpps.map(o => o.city))).sort();
  const filteredOpps = edgeHarvestOpps.filter(o => {
    if (hideNoRoom && !o.nowcastHardBound && (o.recommendationStatus === 'NO_ROOM' || o.openBucket)) return false;
    if (cityFilter !== 'all' && o.city !== cityFilter) return false;
    if (mtFilter !== 'all' && (o.marketType ?? 'high') !== mtFilter) return false;
    if (basisFilter === 'TRUSTED' && o.basisConfidence !== 'TRUSTED') return false;
    if (basisFilter === 'PROVISIONAL' && o.basisConfidence !== 'TRUSTED' && o.basisConfidence !== 'PROVISIONAL') return false;
    return true;
  });

  const groupedByDate = filteredOpps.reduce((acc, opp) => {
    const date = opp.targetDate;
    if (!acc[date]) acc[date] = [];
    acc[date].push(opp);
    return acc;
  }, {} as Record<string, typeof filteredOpps>);

  // Sort dates chronologically, then by conditional fee-net winning payoff.
  const sortedDates = Object.keys(groupedByDate).sort();
  // ROOM first, then UNVERIFIED, then NO_ROOM. This is a screening order, not EV.
  const statusRank = (o: typeof edgeHarvestOpps[number]) =>
    o.nowcastHardBound || o.recommendationStatus === 'ROOM' ? 0 : o.recommendationStatus === 'NO_ROOM' ? 2 : 1;
  sortedDates.forEach(date => {
    groupedByDate[date].sort((a, b) => statusRank(a) - statusRank(b)
      || (b.netWinReturnPct ?? -Infinity) - (a.netWinReturnPct ?? -Infinity));
  });

  // Positions view — newest first; ISO strings sort lexicographically.
  const openPositions = positions.filter(p => p.status === 'OPEN' || p.status === 'RESOLUTION_PENDING');
  const settledPositions = positions.filter(p => p.status !== 'OPEN' && p.status !== 'RESOLUTION_PENDING');
  const visiblePositions = [...(posFilter === 'open' ? openPositions : posFilter === 'settled' ? settledPositions : positions)]
    .sort((a, b) => (b.openedAt ?? '').localeCompare(a.openedAt ?? ''));

  // Scan staleness — backend rejects trades on scans older than 15 min.
  const lastScanMs = status?.lastScan ? Date.parse(status.lastScan) : NaN;
  const scanAgeMin = Number.isNaN(lastScanMs) ? null : Math.max(0, (nowTick - lastScanMs) / 60000);
  const scanAgeLabel = scanAgeMin == null ? null
    : scanAgeMin < 1 ? 'just now'
    : scanAgeMin < 60 ? `${Math.floor(scanAgeMin)}m ago`
    : `${Math.floor(scanAgeMin / 60)}h ${Math.floor(scanAgeMin % 60)}m ago`;
  const scanAgeClass = scanAgeMin == null ? 'text-zinc-500 border-zinc-800'
    : scanAgeMin > 30 ? 'text-rose-400 border-rose-500/40 bg-rose-500/10'
    : scanAgeMin >= 10 ? 'text-amber-400 border-amber-500/40 bg-amber-500/10'
    : 'text-zinc-400 border-zinc-700 bg-zinc-800/60';

  const live = status?.isLive === true;
  // executorLive is ground truth from the executor; false while isLive says
  // true means a mode switch failed and the chip must not claim LIVE.
  const modeError = live && status?.executorLive === false;

  return (
    <div className="min-h-screen bg-black text-white font-sans selection:bg-blue-500/30">
      {/* Navigation */}
      <nav className="border-b border-zinc-900 bg-black/50 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg flex items-center justify-center shadow-lg shadow-blue-500/20">
                <Cloud size={18} className="text-white" />
              </div>
              <span className="text-xl font-bold tracking-tight">Antigravity <span className="text-blue-500">Weather</span></span>
            </div>
            <div className="flex items-center space-x-4">
              <div className={`flex items-center space-x-2 px-3 py-1 rounded-full text-xs font-bold border ${
                modeError ? 'bg-amber-500/10 border-amber-500/40'
                  : live ? 'bg-rose-500/10 border-rose-500/40'
                  : 'bg-zinc-900 border-zinc-800'
              }`}>
                <div className={`w-2 h-2 rounded-full ${
                  modeError ? 'bg-amber-400 animate-pulse' : live ? 'bg-rose-500 animate-pulse' : 'bg-zinc-500'
                }`}></div>
                <span className={modeError ? 'text-amber-400' : live ? 'text-rose-400' : 'text-zinc-400'}>
                  {modeError ? 'MODE ERROR' : live ? 'LIVE TRADING' : 'PAPER TRADING'}
                </span>
              </div>
              <button
                onClick={() => setIsSettingsOpen(true)}
                className="p-2 text-zinc-400 hover:text-white transition-colors"
                title="Settings"
              >
                <Settings size={20} />
              </button>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Header Section */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6">
          <div>
            <h1 className="text-3xl font-extrabold text-zinc-100 tracking-tight mb-2">Market Core</h1>
            <p className="text-zinc-500 text-sm max-w-xl">
              Advanced edge detection and Kelly criterion position sizing for Polymarket weather volatility.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right mr-3">
              <div className="text-[10px] text-zinc-600 uppercase tracking-widest">Last Scan</div>
              {scanAgeMin != null && status?.lastScan ? (
                <span
                  title={new Date(status.lastScan).toLocaleString()}
                  className={`inline-flex items-center gap-1 px-2 py-0.5 mt-0.5 rounded-full border text-[11px] font-mono ${scanAgeClass}`}
                >
                  <Clock size={10} />
                  {scanAgeLabel}{scanAgeMin > 15 ? ' — refresh to trade' : ''}
                </span>
              ) : (
                <div className="text-xs text-zinc-500 font-mono">Never</div>
              )}
            </div>
            <div className="flex items-center space-x-2">
              <div className="flex bg-zinc-800 rounded-lg p-1">
                <button
                  onClick={() => setActiveTab('harvest')}
                  className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${activeTab === 'harvest' ? 'bg-blue-600 text-white' : 'text-zinc-400 hover:text-white'}`}
                >
                  Edge Harvest
                </button>
                <button
                  onClick={() => setActiveTab('edge')}
                  className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${activeTab === 'edge' ? 'bg-blue-600 text-white' : 'text-zinc-400 hover:text-white'}`}
                >
                  Edge Trading
                </button>
              </div>
              <button
                onClick={handleScan}
                disabled={scanning}
                className="flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-700 disabled:cursor-not-allowed rounded-xl text-sm font-medium transition-colors"
              >
                {scanning ? <RefreshCcw size={18} className="animate-spin mr-2" /> : <RefreshCcw size={18} className="mr-2" />}
                Run Scanner
              </button>
            </div>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Total Bankroll"
            value={stats ? `$${stats.bankroll.toFixed(2)}` : '---'}
            subtext={stats ? `Available $${stats.available.toFixed(2)} · reserved $${(stats.reserved ?? 0).toFixed(2)}` : '...'}
            icon={Wallet}
            loading={loading}
          />
          <StatCard
            title="Win Rate"
            value={stats?.winRate != null ? `${(stats.winRate * 100).toFixed(1)}%` : 'N/A'}
            subtext={stats ? `${stats.winCount} verified wins / ${stats.lossCount} losses · ${stats.legacyTrades ?? 0} legacy excluded` : '...'}
            icon={TrendingUp}
            loading={loading}
          />
          <StatCard
            title="Open Risk"
            value={stats ? `$${stats.deployed.toFixed(2)}` : '---'}
            subtext={stats ? `${stats.openPositions} active trades` : '...'}
            icon={ShieldCheck}
            loading={loading}
          />
          <StatCard
            title="Total PnL"
            value={stats ? `${stats.totalPnl < 0 ? '-' : '+'}$${Math.abs(stats.totalPnl).toFixed(2)}` : '---'}
            subtext="realized"
            valueClass={stats ? (stats.totalPnl < 0 ? 'text-rose-400' : 'text-emerald-400') : undefined}
            icon={DollarSign}
            loading={loading}
          />
        </div>

        {/* Main Content Area */}
        <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl overflow-hidden shadow-2xl backdrop-blur-md">
          <div className="border-b border-zinc-800 flex items-center p-1">
            <button
              onClick={() => setActiveView('monitor')}
              className={`flex-1 flex items-center justify-center space-x-2 py-3 rounded-xl text-sm font-bold transition-all ${activeView === 'monitor' ? 'bg-zinc-800 text-white' : 'text-zinc-500 hover:text-zinc-300'}`}
            >
              <Activity size={18} />
              <span>Edge Monitor</span>
              <span className="ml-2 px-1.5 py-0.5 bg-blue-500/10 text-blue-400 text-[10px] rounded-full border border-blue-500/20">{opportunities.length}</span>
            </button>
            <button
              onClick={() => setActiveView('portfolio')}
              className={`flex-1 flex items-center justify-center space-x-2 py-3 rounded-xl text-sm font-bold transition-all ${activeView === 'portfolio' ? 'bg-zinc-800 text-white' : 'text-zinc-500 hover:text-zinc-300'}`}
            >
              <LayoutDashboard size={18} />
              <span>Live Portfolio</span>
              <span className="ml-2 px-1.5 py-0.5 bg-zinc-500/10 text-zinc-400 text-[10px] rounded-full border border-zinc-500/20">{openPositions.length}</span>
            </button>
            <button
              onClick={() => setActiveView('orders')}
              className={`flex-1 flex items-center justify-center space-x-2 py-3 rounded-xl text-sm font-bold transition-all ${activeView === 'orders' ? 'bg-zinc-800 text-white' : 'text-zinc-500 hover:text-zinc-300'}`}
            >
              <History size={18} />
              <span>Orders</span>
              <span className="ml-2 px-1.5 py-0.5 bg-zinc-500/10 text-zinc-400 text-[10px] rounded-full border border-zinc-500/20">{orders.length}</span>
            </button>
          </div>

          <div className="min-h-[400px]">
            {activeView === 'monitor' && (
              <div>
                {activeTab === 'edge' && (
                  <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-zinc-800">
                    <thead className="bg-zinc-900/50">
                      <tr>
                        <th className="py-3.5 pl-4 pr-3 text-left text-xs font-bold text-zinc-500 uppercase tracking-wider sm:pl-6">Market</th>
                        <th className="px-3 py-3.5 text-left text-xs font-bold text-zinc-500 uppercase tracking-wider">Bucket</th>
                        <th className="px-3 py-3.5 text-left text-xs font-bold text-zinc-500 uppercase tracking-wider">Analysis</th>
                        <th className="px-3 py-3.5 text-left text-xs font-bold text-zinc-500 uppercase tracking-wider">Pricing</th>
                        <th className="px-3 py-3.5 text-center text-xs font-bold text-zinc-500 uppercase tracking-wider">Action Plan</th>
                        <th className="relative py-3.5 pl-3 pr-4 sm:pr-6">
                          <span className="sr-only">Actions</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-900/50">
                      {opportunities.length > 0 ? (
                        opportunities.map((opt) => (
                          <OpportunityRow
                            key={opt.id}
                            opt={opt}
                            onTrade={handleTrade}
                            trading={trading === opt.id}
                          />
                        ))
                      ) : (
                        <tr>
                          <td colSpan={6} className="py-20 text-center">
                            <div className="flex flex-col items-center">
                              <Cloud size={48} className="text-zinc-800 mb-4" />
                              <p className="text-zinc-500 font-medium">No weather opportunities found.</p>
                              <p className="text-zinc-700 text-xs mt-1">Try running the scanner to fetch fresh data.</p>
                            </div>
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                  </div>
                )}

                {activeTab === 'harvest' && (
                  <div>
                    {edgeHarvestStats && (
                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2 border-b border-zinc-800 text-[11px] text-zinc-500 sm:px-6">
                        <span>last scan: <span className="text-zinc-300 font-bold">{edgeHarvestStats.total}</span> total</span>
                        <span><span className="text-zinc-300 font-bold">{edgeHarvestStats.conservative}</span> conservative</span>
                        <span><span className="text-zinc-300 font-bold">{edgeHarvestStats.aggressive}</span> aggressive</span>
                        <span><span className={`font-bold ${edgeHarvestStats.withWarnings > 0 ? 'text-amber-400' : 'text-zinc-300'}`}>{edgeHarvestStats.withWarnings}</span> warnings</span>
                      </div>
                    )}
                    <div className="flex flex-wrap items-center gap-2 px-4 py-3 border-b border-zinc-800 sm:px-6">
                      <button
                        onClick={() => setHideNoRoom(v => !v)}
                        className={`px-2.5 py-1 rounded-full text-xs font-bold border transition-colors ${
                          hideNoRoom ? 'bg-zinc-800 text-zinc-200 border-zinc-600' : 'text-zinc-500 border-zinc-800 hover:text-zinc-300'
                        }`}
                      >
                        Hide NO_ROOM
                      </button>
                      <select
                        value={cityFilter}
                        onChange={(e) => setCityFilter(e.target.value)}
                        className="bg-zinc-800 border border-zinc-700 rounded-lg px-2 py-1 text-xs text-zinc-300 focus:outline-none focus:border-blue-500"
                      >
                        <option value="all">All cities</option>
                        {cityOptions.map(c => <option key={c} value={c}>{c}</option>)}
                      </select>
                      <select
                        value={mtFilter}
                        onChange={(e) => setMtFilter(e.target.value as 'all' | 'high' | 'low')}
                        className="bg-zinc-800 border border-zinc-700 rounded-lg px-2 py-1 text-xs text-zinc-300 focus:outline-none focus:border-blue-500"
                      >
                        <option value="all">All types</option>
                        <option value="high">HIGH</option>
                        <option value="low">LOW</option>
                      </select>
                      <select
                        value={basisFilter}
                        onChange={(e) => setBasisFilter(e.target.value as 'all' | 'TRUSTED' | 'PROVISIONAL')}
                        className="bg-zinc-800 border border-zinc-700 rounded-lg px-2 py-1 text-xs text-zinc-300 focus:outline-none focus:border-blue-500"
                      >
                        <option value="all">All basis</option>
                        <option value="TRUSTED">TRUSTED</option>
                        <option value="PROVISIONAL">PROVISIONAL+</option>
                      </select>
                      <span className="ml-auto text-xs text-zinc-500">showing {filteredOpps.length} of {edgeHarvestOpps.length}</span>
                    </div>
                    <div className="overflow-x-auto">
                  <table className="min-w-full">
                    <thead>
                      <tr className="border-b border-zinc-800">
                        <th className="py-3.5 pl-4 pr-3 text-left text-xs font-semibold text-zinc-400 uppercase tracking-wider sm:pl-6">City</th>
                        <th className="px-3 py-3.5 text-left text-xs font-semibold text-zinc-400 uppercase tracking-wider">Bucket</th>
                        <th className="px-3 py-3.5 text-left text-xs font-semibold text-zinc-400 uppercase tracking-wider">Forecast</th>
                        <th className="px-3 py-3.5 text-left text-xs font-semibold text-zinc-400 uppercase tracking-wider">Distance</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">ASK</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">LIQUIDITY</th>
                        <th className="px-3 py-3.5 text-left text-xs font-semibold text-zinc-400 uppercase tracking-wider">Return</th>
                        <th className="px-3 py-3.5 text-left text-xs font-semibold text-zinc-400 uppercase tracking-wider">Risk</th>
                        <th className="px-3 py-3.5 text-left text-xs font-semibold text-zinc-400 uppercase tracking-wider">Settlement</th>
                        <th className="px-3 py-3.5 text-right text-xs font-semibold text-zinc-400 uppercase tracking-wider sm:pr-6">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/50">
                      {filteredOpps.length === 0 ? (
                        <tr>
                          <td colSpan={10} className="py-12 text-center">
                            <div className="flex flex-col items-center text-zinc-500">
                              <Zap size={32} className="mb-3 text-zinc-600" />
                              {edgeHarvestOpps.length > 0 ? (
                                <>
                                  <p className="text-sm font-medium">All {edgeHarvestOpps.length} rows hidden by filters</p>
                                  <p className="text-zinc-700 text-xs mt-1">Loosen the filters above to see them</p>
                                </>
                              ) : (
                                <>
                                  <p className="text-sm font-medium">No edge harvest opportunities</p>
                                  <p className="text-zinc-700 text-xs mt-1">Run scanner to find NO opportunities on extreme buckets</p>
                                </>
                              )}
                            </div>
                          </td>
                        </tr>
                      ) : (
                        sortedDates.map(date => (
                          <React.Fragment key={date}>
                            <tr className="bg-gray-800/50">
                              <td colSpan={10} className="px-4 py-2 text-sm font-semibold text-gray-300">
                                {new Date(date + 'T12:00:00Z').toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })}
                              </td>
                            </tr>
                            {groupedByDate[date].map(opp => (
                              <EdgeHarvestRow key={opp.id} opp={opp} onTrade={handleEdgeHarvestTrade} trading={trading === opp.id} isLive={live} />
                            ))}
                          </React.Fragment>
                        ))
                      )}
                    </tbody>
                  </table>
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeView === 'portfolio' && (
              <div>
                <div className="flex items-center gap-2 px-4 pt-4 sm:px-6">
                  {([['open', 'Open', openPositions.length], ['settled', 'Settled', settledPositions.length], ['all', 'All', positions.length]] as const).map(([key, label, count]) => (
                    <button
                      key={key}
                      onClick={() => setPosFilter(key)}
                      className={`px-3 py-1 rounded-full text-xs font-bold border transition-colors ${
                        posFilter === key ? 'bg-zinc-800 text-white border-zinc-600' : 'text-zinc-500 border-zinc-800 hover:text-zinc-300'
                      }`}
                    >
                      {label} ({count})
                    </button>
                  ))}
                </div>
                <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-zinc-800">
                  <thead className="bg-zinc-900/50">
                    <tr>
                      <th className="py-3.5 pl-4 pr-3 text-left text-xs font-bold text-zinc-500 uppercase tracking-wider sm:pl-6">Position</th>
                      <th className="px-3 py-3.5 text-left text-xs font-bold text-zinc-500 uppercase tracking-wider">Side / Entry</th>
                      <th className="px-3 py-3.5 text-left text-xs font-bold text-zinc-500 uppercase tracking-wider">Entry Val</th>
                      <th className="px-3 py-3.5 text-left text-xs font-bold text-zinc-500 uppercase tracking-wider">Realized PnL</th>
                      <th className="px-3 py-3.5 text-left text-xs font-bold text-zinc-500 uppercase tracking-wider">Status</th>
                      <th className="relative py-3.5 pl-3 pr-4 sm:pr-6">
                        <span className="sr-only">Actions</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-900/50">
                    {visiblePositions.length > 0 ? (
                      visiblePositions.map((pos) => (
                        <tr key={pos.id} className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors">
                          <td className="py-4 pl-4 pr-3 text-sm sm:pl-6">
                            <div className="font-semibold text-zinc-200">{pos.city}</div>
                            <div className="text-zinc-500 text-xs">{pos.bucket} ({pos.targetDate})</div>
                            {(() => {
                              const oid = pos.opportunityId ?? '';
                              // Only eh_ ids embed the market type; anything else carries no signal.
                              const mt = oid.includes('_low_') ? 'low' : oid.includes('_high_') ? 'high' : null;
                              return (
                                <span className={`text-[10px] font-bold mt-1 px-1.5 py-0.5 rounded w-fit inline-block border ${
                                  mt === 'low'
                                    ? 'bg-sky-500/15 text-sky-300 border-sky-500/40'
                                    : mt === 'high'
                                    ? 'bg-amber-500/15 text-amber-300 border-amber-500/40'
                                    : 'bg-zinc-700/30 text-zinc-500 border-zinc-600/40'
                                }`}>
                                  {mt === 'low' ? 'LOW TEMP' : mt === 'high' ? 'HIGH TEMP' : '—'}
                                </span>
                              );
                            })()}
                          </td>
                          <td className="px-3 py-4 text-sm">
                            <span className={`font-bold ${pos.side === 'YES' ? 'text-emerald-400' : 'text-rose-400'}`}>{pos.side}</span>
                            <div className="text-zinc-500 text-xs">${(pos.entryPrice ?? 0).toFixed(2)} avg</div>
                          </td>
                          <td className="px-3 py-4 text-sm">
                            <div className="font-bold text-zinc-200">${((pos.shares ?? 0) * (pos.entryPrice ?? 0)).toFixed(2)}</div>
                            <div className="text-zinc-500 text-xs">{(pos.shares ?? 0).toFixed(1)} units @ ${(pos.entryPrice ?? 0).toFixed(2)}</div>
                          </td>
                          <td className="px-3 py-4 text-sm font-bold">
                            {pos.pnl != null ? (
                              <span className={pos.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                                {pos.pnl >= 0 ? '+' : '-'}${Math.abs(pos.pnl).toFixed(2)}
                              </span>
                            ) : (
                              <span className="text-zinc-600">—</span>
                            )}
                          </td>
                          <td className="px-3 py-4 text-sm">
                            <div className="flex items-center space-x-1.5">
                              <span className={`w-1.5 h-1.5 rounded-full ${
                                pos.status === 'OPEN' ? 'bg-blue-400'
                                  : pos.status === 'WON' ? 'bg-emerald-400'
                                  : pos.status === 'LOST' ? 'bg-rose-400'
                                  : 'bg-zinc-600'
                              }`}></span>
                              <span className="text-zinc-300 font-medium">{pos.status}</span>
                            </div>
                            <div className="text-zinc-500 text-[10px] mt-0.5">
                              {pos.status === 'OPEN'
                                ? (resolutionLabel(pos.targetDate) === 'settling' ? 'awaiting settlement' : `resolves ${resolutionLabel(pos.targetDate)}`)
                                : pos.closedAt ? `closed ${new Date(pos.closedAt).toLocaleDateString()}` : '—'}
                            </div>
                          </td>
                          <td className="py-4 pl-3 pr-4 text-right text-sm font-medium sm:pr-6">
                            <div className="flex justify-end space-x-2">
                              {pos.status === 'OPEN' ? (
                                <>
                                  <button onClick={() => handleClosePosition(pos.id, 'WON')} className="text-emerald-400 hover:text-emerald-300 p-1 border border-emerald-500/20 rounded">W</button>
                                  <button onClick={() => handleClosePosition(pos.id, 'LOST')} className="text-rose-400 hover:text-rose-300 p-1 border border-rose-500/20 rounded">L</button>
                                </>
                              ) : (
                                <button disabled className="text-zinc-700 italic">Settled</button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={6} className="py-20 text-center">
                          <p className="text-zinc-500">{posFilter === 'all' ? 'No positions.' : `No ${posFilter} positions.`}</p>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
                </div>
              </div>
            )}

            {activeView === 'orders' && (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-zinc-800">
                  <thead className="bg-zinc-900/50">
                    <tr>
                      <th className="py-3.5 pl-4 pr-3 text-left text-xs font-bold text-zinc-500 uppercase tracking-wider sm:pl-6">Order ID</th>
                      <th className="px-3 py-3.5 text-left text-xs font-bold text-zinc-500 uppercase tracking-wider">Side</th>
                      <th className="px-3 py-3.5 text-left text-xs font-bold text-zinc-500 uppercase tracking-wider">Price</th>
                      <th className="px-3 py-3.5 text-left text-xs font-bold text-zinc-500 uppercase tracking-wider">Size</th>
                      <th className="px-3 py-3.5 text-left text-xs font-bold text-zinc-500 uppercase tracking-wider">Filled</th>
                      <th className="px-3 py-3.5 text-left text-xs font-bold text-zinc-500 uppercase tracking-wider">Status</th>
                      <th className="px-3 py-3.5 text-left text-xs font-bold text-zinc-500 uppercase tracking-wider">Source</th>
                      <th className="relative py-3.5 pl-3 pr-4 sm:pr-6"><span className="sr-only">Actions</span></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-900/50">
                    {orders.length > 0 ? (
                      orders.map((order) => (
                        <tr key={order.id} className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors">
                          <td className="py-4 pl-4 pr-3 text-sm sm:pl-6">
                            <span className="font-mono text-zinc-300 text-xs">{order.id.slice(0, 12)}...</span>
                            <div className="text-zinc-600 text-[10px]">{order.createdAt ? new Date(order.createdAt).toLocaleString() : ''}</div>
                          </td>
                          <td className="px-3 py-4 text-sm">
                            <span className={`font-bold ${order.side === 'BUY' || order.side === 'YES' ? 'text-emerald-400' : 'text-rose-400'}`}>{order.side}</span>
                          </td>
                          <td className="px-3 py-4 text-sm text-zinc-300">${order.price.toFixed(2)}</td>
                          <td className="px-3 py-4 text-sm text-zinc-300">{order.originalSize.toFixed(1)}</td>
                          <td className="px-3 py-4 text-sm">
                            <span className="text-zinc-300">{order.sizeMatched.toFixed(1)}</span>
                            <span className="text-zinc-600 text-xs ml-1">/ {order.originalSize.toFixed(1)}</span>
                          </td>
                          <td className="px-3 py-4 text-sm">
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${['LIVE', 'SUBMITTED', 'MATCHED', 'MINED', 'PARTIALLY_FILLED'].includes(order.status) ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' :
                              order.status === 'CONFIRMED' || order.status === 'PARTIALLY_CONFIRMED' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' :
                                order.status === 'CANCELLED' || order.status === 'CANCELED' ? 'bg-zinc-500/10 text-zinc-400 border border-zinc-500/20' :
                                  'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                              }`}>
                              {order.status}
                            </span>
                          </td>
                          <td className="px-3 py-4 text-sm">
                            <span className={`text-[10px] font-medium ${order.source === 'LIVE' ? 'text-blue-400' : 'text-zinc-500'}`}>
                              {order.source} · {order.orderMode ?? 'GTC'}
                            </span>
                            {(order.reservedDollars ?? 0) > 0 && (
                              <div className="text-[10px] text-amber-400">${order.reservedDollars?.toFixed(2)} reserved</div>
                            )}
                          </td>
                          <td className="py-4 pl-3 pr-4 text-right text-sm sm:pr-6">
                            {live && ['LIVE', 'SUBMITTED', 'MATCHED', 'PARTIALLY_FILLED', 'PARTIALLY_CONFIRMED'].includes(order.status) && (
                              <div className="flex justify-end gap-1">
                                {order.source === 'LOCAL' && (
                                  <button
                                    onClick={() => handleReconcileOrder(order.id)}
                                    className="px-2 py-1 bg-blue-600/20 hover:bg-blue-600/40 text-blue-300 text-xs font-medium rounded-lg border border-blue-500/20"
                                  >
                                    Reconcile
                                  </button>
                                )}
                                <button
                                  onClick={() => handleCancelOrder(order.id)}
                                  className="px-2 py-1 bg-rose-600/20 hover:bg-rose-600/40 text-rose-400 text-xs font-medium rounded-lg transition-colors border border-rose-500/20"
                                >
                                  Cancel
                                </button>
                              </div>
                            )}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={8} className="py-20 text-center">
                          <div className="flex flex-col items-center">
                            <History size={48} className="text-zinc-800 mb-4" />
                            <p className="text-zinc-500 font-medium">No orders found.</p>
                            <p className="text-zinc-700 text-xs mt-1">Orders will appear here after executing trades.</p>
                          </div>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Settings Modal */}
      {isSettingsOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" onClick={() => setIsSettingsOpen(false)}></div>
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-md p-6 relative z-10 shadow-3xl">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-bold flex items-center">
                <Settings size={20} className="mr-2 text-zinc-400" />
                Settings
              </h2>
              <button
                onClick={() => setIsSettingsOpen(false)}
                className="text-zinc-500 hover:text-white"
              >
                <X size={24} />
              </button>
            </div>

            <div className="space-y-6">
              <div className="space-y-2">
                <label className="text-zinc-400 text-xs font-bold uppercase tracking-wider">Trading Mode</label>
                <div className="grid grid-cols-2 gap-2 bg-zinc-800 p-1 rounded-xl">
                  <button
                    onClick={() => setSettings({ ...settings, isLive: false })}
                    className={`py-2 rounded-lg text-sm font-bold transition-all ${!settings.isLive ? 'bg-zinc-700 text-white shadow-lg' : 'text-zinc-500'}`}
                  >
                    Paper
                  </button>
                  <button
                    onClick={() => setSettings({ ...settings, isLive: true })}
                    className={`py-2 rounded-lg text-sm font-bold transition-all ${settings.isLive ? 'bg-blue-600 text-white shadow-lg' : 'text-zinc-500'}`}
                  >
                    Live
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-zinc-400 text-xs font-bold uppercase tracking-wider font-mono">Total Bankroll ($)</label>
                <input
                  type="number"
                  value={settings.bankroll}
                  onChange={(e) => setSettings({ ...settings, bankroll: Number(e.target.value) })}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all font-mono"
                />
                <p className="text-zinc-600 text-[10px]">Adjusting bankroll recalibrates all Kelly criterion sizing.</p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <label className="text-zinc-400 text-xs font-bold uppercase tracking-wider">
                  Opportunity cap ($)
                  <input
                    type="number"
                    min="0.01"
                    step="0.01"
                    value={settings.maxOpportunityExposureUsd}
                    onChange={(e) => setSettings({ ...settings, maxOpportunityExposureUsd: Number(e.target.value) })}
                    className="mt-2 w-full bg-zinc-800 border border-zinc-700 rounded-xl px-3 py-2 text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500/50 font-mono"
                  />
                </label>
                <label className="text-zinc-400 text-xs font-bold uppercase tracking-wider">
                  Event cap ($)
                  <input
                    type="number"
                    min="0.01"
                    step="0.01"
                    value={settings.maxEventExposureUsd}
                    onChange={(e) => setSettings({ ...settings, maxEventExposureUsd: Number(e.target.value) })}
                    className="mt-2 w-full bg-zinc-800 border border-zinc-700 rounded-xl px-3 py-2 text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500/50 font-mono"
                  />
                </label>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <label className="text-zinc-400 text-xs font-bold uppercase tracking-wider">
                  Max scan age (min)
                  <input
                    type="number"
                    min="0.01"
                    step="0.5"
                    value={settings.maxScanAgeMin}
                    onChange={(e) => setSettings({ ...settings, maxScanAgeMin: Number(e.target.value) })}
                    className="mt-2 w-full bg-zinc-800 border border-zinc-700 rounded-xl px-3 py-2 text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500/50 font-mono"
                  />
                </label>
                <label className="text-zinc-400 text-xs font-bold uppercase tracking-wider">
                  Requote tolerance ($)
                  <input
                    type="number"
                    min="0"
                    step="0.001"
                    value={settings.requoteTolerance}
                    onChange={(e) => setSettings({ ...settings, requoteTolerance: Number(e.target.value) })}
                    className="mt-2 w-full bg-zinc-800 border border-zinc-700 rounded-xl px-3 py-2 text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500/50 font-mono"
                  />
                </label>
              </div>

              <label className="block text-zinc-400 text-xs font-bold uppercase tracking-wider">
                Default order mode
                <select
                  value={settings.defaultOrderMode}
                  onChange={(e) => setSettings({ ...settings, defaultOrderMode: e.target.value as 'GTC' | 'POST_ONLY' })}
                  className="mt-2 w-full bg-zinc-800 border border-zinc-700 rounded-xl px-3 py-2 text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                >
                  <option value="GTC">GTC · may take or rest</option>
                  <option value="POST_ONLY">Post-only · maker only</option>
                </select>
              </label>

              <button
                onClick={handleSettingsUpdate}
                className="w-full bg-zinc-100 hover:bg-white text-black font-extrabold py-3 rounded-xl shadow-xl transition-all active:scale-[0.98] mt-4"
              >
                Save Configuration
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Footer Area */}
      <footer className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 border-t border-zinc-900 mt-12">
        <div className="flex flex-col md:flex-row justify-between items-center gap-4 text-zinc-600 text-[10px] font-bold uppercase tracking-widest">
          <div>© 2026 Antigravity Algorithmic Weather Systems</div>
        </div>
      </footer>
    </div>
  );
}
