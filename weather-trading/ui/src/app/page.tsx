'use client';

import React, { useState, useEffect, useCallback } from 'react';
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
import weatherApi, { Opportunity, Position, Stats, Status, EdgeHarvestOpportunity, EdgeHarvestStats, Order } from '@/lib/api';

// --- Components ---

const StatCard = ({ title, value, subtext, icon: Icon, trend, loading }: any) => (
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
        <div className="text-2xl font-bold text-zinc-100">{value}</div>
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
          <span className="text-emerald-400 font-medium">{((opt.edge ?? 0) * 100).toFixed(1)}% Edge</span>
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

const EdgeHarvestRow = ({ opp, onTrade, trading }: { opp: any, onTrade: (opp: any, size: number) => void, trading: boolean }) => {
  const [size, setSize] = React.useState(Math.min(Math.floor(opp.bestAskPrice > 0 ? (opp.bestAskSize ?? 50) : 50), 100));

  const riskColor = opp.riskTier === 'LOW' ? 'text-emerald-400' : opp.riskTier === 'MEDIUM' ? 'text-yellow-400' : 'text-rose-400';
  const riskBg = opp.riskTier === 'LOW' ? 'bg-emerald-500/10' : opp.riskTier === 'MEDIUM' ? 'bg-yellow-500/10' : 'bg-rose-500/10';
  const typeColor = opp.thresholdType === 'CONSERVATIVE' ? 'text-blue-400 bg-blue-500/10' : 'text-orange-400 bg-orange-500/10';

  return (
    <tr className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors group">
      <td className="py-4 pl-4 pr-3 sm:pl-6">
        <div className="flex flex-col">
          <span className="font-semibold text-zinc-100 uppercase text-sm">{opp.city}</span>
          <span className="text-zinc-500 text-xs">{opp.targetDate}</span>
          {opp.frontWarning && (
            <span className="text-rose-400 text-xs mt-1 flex items-center">
              <ShieldAlert size={12} className="mr-1" />
              Front Warning
            </span>
          )}
        </div>
      </td>
      <td className="px-3 py-4 text-sm font-medium text-zinc-200">{opp.bucket}</td>
      <td className="px-3 py-4">
        <div className="flex flex-col">
          <span className="text-sm text-zinc-200">{(opp.forecastTemp ?? 0).toFixed(0)}°F</span>
          {(opp.modelSpread ?? 0) > 0 && (
            <span className="text-xs text-zinc-500">±{(opp.modelSpread ?? 0).toFixed(1)}° spread</span>
          )}
        </div>
      </td>
      <td className="px-3 py-4">
        <span className="text-sm text-zinc-300">{opp.bandsAway ?? 0} bands</span>
        <span className="text-xs text-zinc-500 ml-1">({(opp.degreesAway ?? 0).toFixed(0)}°F)</span>
      </td>
      <td className="px-4 py-3 text-sm text-gray-300">${(opp.bestAskPrice ?? opp.noPrice ?? 0).toFixed(2)}</td>
      <td className="px-4 py-3 text-sm text-gray-400">{(opp.bestAskSize ?? 0).toFixed(0)}</td>
      <td className="px-3 py-4">
        <span className="text-sm font-semibold text-emerald-400">{(opp.potentialReturnPct ?? 0).toFixed(1)}%</span>
      </td>
      <td className="px-4 py-3 text-sm text-gray-300">{opp.ev.toFixed(2)}</td>
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
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${typeColor}`}>
          {opp.thresholdType}
        </span>
      </td>
      <td className="px-3 py-4 text-right sm:pr-6">
        <div className="flex items-center justify-end space-x-2">
          <input
            type="number"
            value={size}
            onChange={(e) => setSize(Number(e.target.value))}
            className="w-16 px-2 py-1 bg-zinc-800 border border-zinc-700 rounded text-sm text-right text-zinc-200"
            min="1"
            max="300"
          />
          <button
            onClick={() => onTrade(opp, size)}
            disabled={trading}
            className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-700 rounded-lg text-xs font-medium transition-colors flex items-center"
          >
            {trading ? <RefreshCcw size={12} className="animate-spin" /> : 'Buy NO'}
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
  const [settings, setSettings] = useState({ bankroll: 1000, isLive: false });

  const fetchData = useCallback(async () => {
    try {
      const [statusRes, statsRes, oppsRes, posRes, ordersRes] = await Promise.all([
        weatherApi.getStatus(),
        weatherApi.getStats(),
        weatherApi.getOpportunities(),
        weatherApi.getPositions(),
        weatherApi.getOrders().catch(() => ({ orders: [] }))
      ]);
      setStatus(statusRes);
      setStats(statsRes);
      setOpportunities(oppsRes.opportunities);
      setPositions(posRes.positions);
      setOrders(ordersRes.orders);
      setSettings({ bankroll: statusRes.bankroll, isLive: statusRes.isLive });
    } catch (err) {
      console.error('Failed to fetch dashboard data', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000); // 1 min poll
    return () => clearInterval(interval);
  }, [fetchData]);

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
    } catch (err) {
      alert('Scan failed');
    } finally {
      setScanning(false);
    }
  };

  const handleTrade = async (opt: Opportunity, size: number) => {
    setTrading(opt.id);
    try {
      const result = await weatherApi.executeTrade(opt.id, opt.recommendedSide, size);
      if (result.success) {
        alert(`Successfully placed ${opt.recommendedSide} order for ${opt.city} - $${size.toFixed(2)}`);
        fetchData();
      } else {
        alert(`Order failed: ${result.error || 'Unknown error'}`);
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Unknown error';
      alert(`Trade execution failed: ${detail}`);
    } finally {
      setTrading(null);
    }
  };

  const handleEdgeHarvestTrade = async (opp: EdgeHarvestOpportunity, size: number) => {
    setTrading(opp.id);
    try {
      const result = await weatherApi.executeTrade(opp.id, 'NO', size);
      if (result.success) {
        alert(`Successfully placed NO order for ${opp.city} ${opp.bucket} - $${size.toFixed(2)}`);
        fetchData();
      } else {
        alert(`Order failed: ${result.error || 'Unknown error'}`);
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Unknown error';
      alert(`Trade execution failed: ${detail}`);
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

  const handleSettingsUpdate = async () => {
    try {
      await weatherApi.updateSettings(settings);
      setIsSettingsOpen(false);
      fetchData();
    } catch (err) {
      alert('Failed to update settings');
    }
  };

  // Calculate EV and group by date
  const oppsWithEV = edgeHarvestOpps.map(opp => ({
    ...opp,
    ev: (opp.potentialReturnPct * (100 - opp.riskScore) / 100)
  }));

  const groupedByDate = oppsWithEV.reduce((acc, opp) => {
    const date = opp.targetDate;
    if (!acc[date]) acc[date] = [];
    acc[date].push(opp);
    return acc;
  }, {} as Record<string, typeof oppsWithEV>);

  // Sort dates chronologically, then sort opportunities within each date by EV descending
  const sortedDates = Object.keys(groupedByDate).sort();
  sortedDates.forEach(date => {
    groupedByDate[date].sort((a, b) => b.ev - a.ev);
  });

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
              <div className="hidden md:flex items-center space-x-2 px-3 py-1 bg-zinc-900 border border-zinc-800 rounded-full text-xs font-medium">
                <div className={`w-2 h-2 rounded-full ${status?.isLive ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`}></div>
                <span className="text-zinc-400">{status?.isLive ? 'LIVE' : 'PAPER'} TRADING</span>
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
            <div className="hidden lg:block text-right mr-3">
              <div className="text-[10px] text-zinc-600 uppercase font-tracking-widest">Last Scan</div>
              <div className="text-xs text-zinc-400 font-mono">{status?.lastScan ? new Date(status.lastScan).toLocaleTimeString() : 'Never'}</div>
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
            subtext={stats ? `Available: $${stats.available.toFixed(2)}` : '...'}
            icon={Wallet}
            loading={loading}
          />
          <StatCard
            title="Win Rate"
            value={stats?.winRate != null ? `${(stats.winRate * 100).toFixed(1)}%` : 'N/A'}
            subtext={stats ? `${stats.winCount} Wins / ${stats.lossCount} Losses` : '...'}
            icon={TrendingUp}
            trend={stats?.winRate != null ? 1.2 : null}
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
            value={stats ? `${stats.totalPnl >= 0 ? '+' : ''}$${stats.totalPnl.toFixed(2)}` : '---'}
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
              <span className="ml-2 px-1.5 py-0.5 bg-zinc-500/10 text-zinc-400 text-[10px] rounded-full border border-zinc-500/20">{positions.length}</span>
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
            {activeView === 'monitor' ? (
              <div className="overflow-x-auto">
                {activeTab === 'edge' && (
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
                )}

                {activeTab === 'harvest' && (
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
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">EV</th>
                        <th className="px-3 py-3.5 text-left text-xs font-semibold text-zinc-400 uppercase tracking-wider">Risk</th>
                        <th className="px-3 py-3.5 text-left text-xs font-semibold text-zinc-400 uppercase tracking-wider">Type</th>
                        <th className="px-3 py-3.5 text-right text-xs font-semibold text-zinc-400 uppercase tracking-wider sm:pr-6">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/50">
                      {edgeHarvestOpps.length === 0 ? (
                        <tr>
                          <td colSpan={11} className="py-12 text-center">
                            <div className="flex flex-col items-center text-zinc-500">
                              <Zap size={32} className="mb-3 text-zinc-600" />
                              <p className="text-sm font-medium">No edge harvest opportunities</p>
                              <p className="text-zinc-700 text-xs mt-1">Run scanner to find NO opportunities on extreme buckets</p>
                            </div>
                          </td>
                        </tr>
                      ) : (
                        sortedDates.map(date => (
                          <React.Fragment key={date}>
                            <tr className="bg-gray-800/50">
                              <td colSpan={11} className="px-4 py-2 text-sm font-semibold text-gray-300">
                                {new Date(date + 'T12:00:00Z').toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })}
                              </td>
                            </tr>
                            {groupedByDate[date].map(opp => (
                              <EdgeHarvestRow key={opp.id} opp={opp} onTrade={handleEdgeHarvestTrade} trading={trading === opp.id} />
                            ))}
                          </React.Fragment>
                        ))
                      )}
                    </tbody>
                  </table>
                )}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-zinc-800">
                  <thead className="bg-zinc-900/50">
                    <tr>
                      <th className="py-3.5 pl-4 pr-3 text-left text-xs font-bold text-zinc-500 uppercase tracking-wider sm:pl-6">Position</th>
                      <th className="px-3 py-3.5 text-left text-xs font-bold text-zinc-500 uppercase tracking-wider">Side / Entry</th>
                      <th className="px-3 py-3.5 text-left text-xs font-bold text-zinc-500 uppercase tracking-wider">Current Val</th>
                      <th className="px-3 py-3.5 text-left text-xs font-bold text-zinc-500 uppercase tracking-wider">Unrealized PnL</th>
                      <th className="px-3 py-3.5 text-left text-xs font-bold text-zinc-500 uppercase tracking-wider">Status</th>
                      <th className="relative py-3.5 pl-3 pr-4 sm:pr-6">
                        <span className="sr-only">Actions</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-900/50">
                    {positions.length > 0 ? (
                      positions.map((pos) => (
                        <tr key={pos.id} className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors">
                          <td className="py-4 pl-4 pr-3 text-sm sm:pl-6">
                            <div className="font-semibold text-zinc-200">{pos.city}</div>
                            <div className="text-zinc-500 text-xs">{pos.bucket} ({pos.targetDate})</div>
                          </td>
                          <td className="px-3 py-4 text-sm">
                            <span className={`font-bold ${pos.side === 'YES' ? 'text-emerald-400' : 'text-rose-400'}`}>{pos.side}</span>
                            <div className="text-zinc-500 text-xs">${(pos.entryPrice ?? 0).toFixed(2)} avg</div>
                          </td>
                          <td className="px-3 py-4 text-sm">
                            <div className="font-bold text-zinc-200">${((pos.shares ?? 0) * (pos.currentPrice ?? 0)).toFixed(2)}</div>
                            <div className="text-zinc-500 text-xs">{(pos.shares ?? 0).toFixed(1)} units @ ${(pos.currentPrice ?? 0).toFixed(2)}</div>
                          </td>
                          <td className="px-3 py-4 text-sm font-bold">
                            <span className={(pos.unrealizedPnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                              {(pos.unrealizedPnl ?? 0) >= 0 ? '+' : ''}${(pos.unrealizedPnl ?? 0).toFixed(2)}
                            </span>
                            <div className="text-[10px] text-zinc-600">{(((pos.unrealizedPnl ?? 0) / ((pos.entryPrice ?? 1) * (pos.shares ?? 1))) * 100).toFixed(1)}% ROI</div>
                          </td>
                          <td className="px-3 py-4 text-sm">
                            <div className="flex items-center space-x-1.5">
                              <span className={`w-1.5 h-1.5 rounded-full ${pos.status === 'OPEN' ? 'bg-blue-400' : 'bg-zinc-600'}`}></span>
                              <span className="text-zinc-300 font-medium">{pos.status}</span>
                            </div>
                            <div className="text-zinc-500 text-[10px] mt-0.5">{(pos.hoursRemaining ?? 0).toFixed(1)}h left</div>
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
                          <p className="text-zinc-500">No active positions.</p>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
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
                            <span className={`font-bold ${order.side === 'BUY' ? 'text-emerald-400' : 'text-rose-400'}`}>{order.side}</span>
                          </td>
                          <td className="px-3 py-4 text-sm text-zinc-300">${order.price.toFixed(2)}</td>
                          <td className="px-3 py-4 text-sm text-zinc-300">{order.originalSize.toFixed(1)}</td>
                          <td className="px-3 py-4 text-sm">
                            <span className="text-zinc-300">{order.sizeMatched.toFixed(1)}</span>
                            <span className="text-zinc-600 text-xs ml-1">/ {order.originalSize.toFixed(1)}</span>
                          </td>
                          <td className="px-3 py-4 text-sm">
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${order.status === 'LIVE' || order.status === 'SUBMITTED' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' :
                              order.status === 'MATCHED' || order.status === 'FILLED' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' :
                                order.status === 'CANCELLED' ? 'bg-zinc-500/10 text-zinc-400 border border-zinc-500/20' :
                                  'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                              }`}>
                              {order.status}
                            </span>
                          </td>
                          <td className="px-3 py-4 text-sm">
                            <span className={`text-[10px] font-medium ${order.source === 'LIVE' ? 'text-blue-400' : 'text-zinc-500'}`}>
                              {order.source}
                            </span>
                          </td>
                          <td className="py-4 pl-3 pr-4 text-right text-sm sm:pr-6">
                            {(order.status === 'LIVE' || order.status === 'SUBMITTED') && order.source === 'LIVE' && (
                              <button
                                onClick={() => handleCancelOrder(order.id)}
                                className="px-2 py-1 bg-rose-600/20 hover:bg-rose-600/40 text-rose-400 text-xs font-medium rounded-lg transition-colors border border-rose-500/20"
                              >
                                Cancel
                              </button>
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
          <div className="flex items-center gap-4">
            <span className="flex items-center"><Activity size={10} className="mr-1" /> CLOB API CONNECTED</span>
            <span className="flex items-center"><ShieldCheck size={10} className="mr-1" /> HALF-KELLY ENFORCED</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
