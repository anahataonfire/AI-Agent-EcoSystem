"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface Opportunity {
    question: string;
    certainty_side: string;
    certainty_pct: number;
    hours_remaining: number;
    liquidity: number;
    apr_estimate: number;
    market_url: string;
    event_slug: string;
}

export default function PolymarketPage() {
    const [maxHours, setMaxHours] = useState(24); // Default: 24h (matches backend)
    const [minCertainty, setMinCertainty] = useState(90); // Default: 90% (matches backend)
    const [minLiquidity, setMinLiquidity] = useState(100);
    const [loading, setLoading] = useState(false);
    const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [sortBy, setSortBy] = useState<'apr' | 'time' | 'liquidity'>('apr');

    const scanMarkets = async () => {
        setLoading(true);
        setError(null);

        try {
            const res = await fetch(
                `http://localhost:8000/polymarket/opportunities?max_hours=${maxHours}&min_certainty=${minCertainty / 100}&min_liquidity=${minLiquidity}`,
                { headers: { "X-API-Key": "dev-token-change-me" } }
            );

            if (!res.ok) throw new Error(`API error: ${res.status}`);
            const data = await res.json();
            setOpportunities(data || []);
        } catch (e: any) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    const totalLiquidity = opportunities.reduce((sum, o) => sum + o.liquidity, 0);
    const avgApr = opportunities.length > 0
        ? opportunities.reduce((sum, o) => sum + o.apr_estimate, 0) / opportunities.length
        : 0;
    const soonest = opportunities.length > 0
        ? Math.min(...opportunities.map((o) => o.hours_remaining))
        : 0;

    return (
        <div className="space-y-8">
            {/* Header */}
            <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-r from-emerald-500/10 via-green-500/10 to-teal-500/10 rounded-2xl blur-xl" />
                <div className="relative bg-zinc-900/80 backdrop-blur-sm border border-zinc-800 rounded-2xl p-6">
                    <h1 className="text-4xl font-bold bg-gradient-to-r from-emerald-400 via-green-400 to-teal-400 bg-clip-text text-transparent">
                        Polymarket Scanner
                    </h1>
                    <p className="text-zinc-400 mt-2">Find high-certainty markets approaching resolution</p>
                </div>
            </div>

            {/* Scanner Controls */}
            <Card className="bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <span className="text-2xl">⚙️</span>
                        Scanner Settings
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div>
                            <label className="text-sm text-zinc-400 mb-2 block">Max Hours to Resolution</label>
                            <div className="flex items-center gap-4">
                                <input
                                    type="range"
                                    min={1}
                                    max={168}
                                    step={1}
                                    value={maxHours}
                                    onChange={(e) => setMaxHours(Number(e.target.value))}
                                    className="flex-1 accent-emerald-500"
                                />
                                <span className="text-lg font-bold text-emerald-400 w-16">{maxHours}h</span>
                            </div>
                        </div>
                        <div>
                            <label className="text-sm text-zinc-400 mb-2 block">Min Certainty %</label>
                            <div className="flex items-center gap-4">
                                <input
                                    type="range"
                                    min={80}
                                    max={99}
                                    value={minCertainty}
                                    onChange={(e) => setMinCertainty(Number(e.target.value))}
                                    className="flex-1 accent-emerald-500"
                                />
                                <span className="text-lg font-bold text-emerald-400 w-12">{minCertainty}%</span>
                            </div>
                        </div>
                        <div>
                            <label className="text-sm text-zinc-400 mb-2 block">Min Liquidity ($)</label>
                            <input
                                type="number"
                                value={minLiquidity}
                                onChange={(e) => setMinLiquidity(Number(e.target.value))}
                                className="w-full bg-zinc-800/50 border border-zinc-700 rounded-xl px-4 py-2.5 text-lg"
                            />
                        </div>
                    </div>
                    <Button
                        onClick={scanMarkets}
                        disabled={loading}
                        className="w-full h-14 text-lg rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600"
                    >
                        {loading ? "⟳ Scanning markets..." : "🔍 Scan Markets"}
                    </Button>
                </CardContent>
            </Card>

            {error && (
                <div className="bg-yellow-950/30 border border-yellow-800/50 rounded-2xl p-4">
                    <p className="text-yellow-400">⚠️ {error}</p>
                </div>
            )}

            {/* Stats */}
            {opportunities.length > 0 && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <StatCard icon="💰" label="Total Liquidity" value={`$${totalLiquidity.toLocaleString()}`} color="from-emerald-500 to-green-500" />
                    <StatCard icon="📈" label="Avg APR" value={`${avgApr.toFixed(0)}%`} color="from-green-500 to-teal-500" />
                    <StatCard icon="⏱️" label="Soonest" value={`${soonest.toFixed(1)}h`} color="from-teal-500 to-cyan-500" />
                    <StatCard icon="🎯" label="Opportunities" value={opportunities.length.toString()} color="from-cyan-500 to-blue-500" />
                </div>
            )}

            {/* Opportunities */}
            {opportunities.length > 0 && (
                <div className="space-y-4">
                    {opportunities.map((opp, i) => (
                        <OpportunityCard key={i} opportunity={opp} />
                    ))}
                </div>
            )}

            {!loading && opportunities.length === 0 && !error && (
                <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-12 text-center">
                    <div className="text-6xl mb-4">🎯</div>
                    <h3 className="text-xl font-semibold text-zinc-200">Ready to scan</h3>
                    <p className="text-zinc-500 mt-2">Click "Scan Markets" to find opportunities</p>
                </div>
            )}
        </div>
    );
}

function StatCard({ icon, label, value, color }: { icon: string; label: string; value: string; color: string }) {
    return (
        <div className="group relative">
            <div className={`absolute inset-0 bg-gradient-to-r ${color} rounded-2xl opacity-0 group-hover:opacity-20 transition-opacity blur-xl`} />
            <Card className="relative bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl">
                <CardContent className="p-5">
                    <div className="flex items-center gap-3">
                        <span className="text-2xl">{icon}</span>
                        <div>
                            <p className={`text-xl font-bold bg-gradient-to-r ${color} bg-clip-text text-transparent`}>{value}</p>
                            <p className="text-xs text-zinc-500">{label}</p>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}

function OpportunityCard({ opportunity }: { opportunity: Opportunity }) {
    const isUrgent = opportunity.hours_remaining < 1;
    const isWarning = opportunity.hours_remaining < 4;

    const borderColor = isUrgent
        ? "border-red-500/50 bg-red-950/20"
        : isWarning
            ? "border-yellow-500/50 bg-yellow-950/20"
            : "border-emerald-500/50 bg-emerald-950/20";

    const urgencyIcon = isUrgent ? "🔴" : isWarning ? "🟡" : "🟢";

    return (
        <Card className={`${borderColor} border rounded-2xl transition-all hover:scale-[1.01]`}>
            <CardContent className="p-6">
                <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                        <div className="flex items-center gap-3 mb-3">
                            <span className="text-xl">{urgencyIcon}</span>
                            <span className="text-2xl font-bold text-emerald-400">
                                {opportunity.apr_estimate.toLocaleString()}% APR
                            </span>
                            <span className="text-zinc-400">|</span>
                            <span className="text-lg text-zinc-300">
                                ⏳ {opportunity.hours_remaining.toFixed(1)}h
                            </span>
                        </div>
                        <p className="text-zinc-200 text-lg leading-relaxed">{opportunity.question}</p>
                        <div className="flex items-center gap-4 mt-4">
                            <span className="px-3 py-1 bg-zinc-800 rounded-full text-sm">
                                {opportunity.certainty_side} @ <strong className="text-emerald-400">{opportunity.certainty_pct.toFixed(1)}%</strong>
                            </span>
                            <span className="text-zinc-500">💰 ${opportunity.liquidity.toLocaleString()}</span>
                        </div>
                    </div>
                    <a
                        href={opportunity.market_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="shrink-0 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 px-6 py-3 rounded-xl text-sm font-medium transition-all"
                    >
                        Trade →
                    </a>
                </div>
            </CardContent>
        </Card>
    );
}
