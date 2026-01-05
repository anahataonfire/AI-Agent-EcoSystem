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
    const [maxHours, setMaxHours] = useState(4);
    const [minCertainty, setMinCertainty] = useState(95);
    const [minLiquidity, setMinLiquidity] = useState(100);
    const [loading, setLoading] = useState(false);
    const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
    const [error, setError] = useState<string | null>(null);

    const scanMarkets = async () => {
        setLoading(true);
        setError(null);

        try {
            const res = await fetch("http://localhost:8000/polymarket/opportunities", {
                headers: { "X-API-Key": "dev-token-change-me" },
            });

            if (!res.ok) throw new Error(`API error: ${res.status}`);

            const data = await res.json();
            setOpportunities(data || []);
        } catch (e: any) {
            setError(e.message);
            // Demo data for UI testing
            setOpportunities([
                {
                    question: "Will Bitcoin exceed $100k by end of January 2026?",
                    certainty_side: "YES",
                    certainty_pct: 0.97,
                    hours_remaining: 2.5,
                    liquidity: 45000,
                    apr_estimate: 892,
                    market_url: "https://polymarket.com/event/btc-100k",
                    event_slug: "btc-100k-jan-2026",
                },
                {
                    question: "Will the Fed cut rates in January 2026?",
                    certainty_side: "NO",
                    certainty_pct: 0.96,
                    hours_remaining: 8.2,
                    liquidity: 28000,
                    apr_estimate: 456,
                    market_url: "https://polymarket.com/event/fed-rates",
                    event_slug: "fed-rates-jan-2026",
                },
            ]);
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
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold">🎯 Polymarket Certainty Scanner</h1>
                <p className="text-zinc-400 mt-1">Find high-certainty markets approaching resolution for maximum APR trades</p>
            </div>

            <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader>
                    <CardTitle>⚙️ Scanner Settings</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="grid grid-cols-3 gap-4">
                        <div>
                            <label className="text-sm text-zinc-400">Max Hours to Resolution</label>
                            <input
                                type="range"
                                min={1}
                                max={24}
                                value={maxHours}
                                onChange={(e) => setMaxHours(Number(e.target.value))}
                                className="w-full mt-2"
                            />
                            <span className="text-sm">{maxHours}h</span>
                        </div>
                        <div>
                            <label className="text-sm text-zinc-400">Min Certainty %</label>
                            <input
                                type="range"
                                min={50}
                                max={99}
                                value={minCertainty}
                                onChange={(e) => setMinCertainty(Number(e.target.value))}
                                className="w-full mt-2"
                            />
                            <span className="text-sm">{minCertainty}%</span>
                        </div>
                        <div>
                            <label className="text-sm text-zinc-400">Min Liquidity ($)</label>
                            <input
                                type="number"
                                value={minLiquidity}
                                onChange={(e) => setMinLiquidity(Number(e.target.value))}
                                className="w-full mt-2 bg-zinc-800 border border-zinc-700 rounded px-3 py-1"
                            />
                        </div>
                    </div>
                    <Button onClick={scanMarkets} disabled={loading} className="w-full">
                        {loading ? "🔄 Scanning..." : "🔍 Scan Markets"}
                    </Button>
                </CardContent>
            </Card>

            {error && (
                <Card className="bg-yellow-950/50 border-yellow-800">
                    <CardContent className="p-4">
                        <p className="text-yellow-400">⚠️ API unavailable, showing demo data. Error: {error}</p>
                    </CardContent>
                </Card>
            )}

            {opportunities.length > 0 && (
                <>
                    <div className="grid grid-cols-4 gap-4">
                        <Card className="bg-zinc-900 border-zinc-800">
                            <CardContent className="p-4">
                                <p className="text-xs text-zinc-500">Total Liquidity</p>
                                <p className="text-2xl font-bold">${totalLiquidity.toLocaleString()}</p>
                            </CardContent>
                        </Card>
                        <Card className="bg-zinc-900 border-zinc-800">
                            <CardContent className="p-4">
                                <p className="text-xs text-zinc-500">Avg APR</p>
                                <p className="text-2xl font-bold text-green-400">{avgApr.toFixed(0)}%</p>
                            </CardContent>
                        </Card>
                        <Card className="bg-zinc-900 border-zinc-800">
                            <CardContent className="p-4">
                                <p className="text-xs text-zinc-500">Soonest Resolution</p>
                                <p className="text-2xl font-bold">{soonest.toFixed(1)}h</p>
                            </CardContent>
                        </Card>
                        <Card className="bg-zinc-900 border-zinc-800">
                            <CardContent className="p-4">
                                <p className="text-xs text-zinc-500">Opportunities</p>
                                <p className="text-2xl font-bold">{opportunities.length}</p>
                            </CardContent>
                        </Card>
                    </div>

                    <div className="space-y-3">
                        {opportunities.map((opp, i) => (
                            <OpportunityCard key={i} opportunity={opp} />
                        ))}
                    </div>
                </>
            )}
        </div>
    );
}

function OpportunityCard({ opportunity }: { opportunity: Opportunity }) {
    const urgencyColor =
        opportunity.hours_remaining < 1
            ? "bg-red-500/20 border-red-500/50"
            : opportunity.hours_remaining < 4
                ? "bg-yellow-500/20 border-yellow-500/50"
                : "bg-green-500/20 border-green-500/50";

    const urgencyIcon =
        opportunity.hours_remaining < 1 ? "🔴" : opportunity.hours_remaining < 4 ? "🟡" : "🟢";

    return (
        <Card className={`${urgencyColor} border`}>
            <CardContent className="p-4">
                <div className="flex items-start justify-between">
                    <div className="flex-1">
                        <p className="font-bold">
                            {urgencyIcon} {opportunity.apr_estimate.toLocaleString()}% APR | ⏳ {opportunity.hours_remaining.toFixed(1)}h
                        </p>
                        <p className="text-sm text-zinc-300 mt-1">{opportunity.question}</p>
                        <p className="text-sm text-zinc-400 mt-2">
                            Certainty: <code className="bg-zinc-800 px-1 rounded">{opportunity.certainty_side}</code> @ <strong>{(opportunity.certainty_pct * 100).toFixed(1)}%</strong>
                        </p>
                    </div>
                    <div className="text-right space-y-1">
                        <p className="text-sm">💰 ${opportunity.liquidity.toLocaleString()}</p>
                        <a
                            href={opportunity.market_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-400 text-sm hover:underline"
                        >
                            View Market →
                        </a>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
