"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface Position {
    conditionId: string;
    question: string;
    slug: string;
    outcome: string;
    size: number;
    avgPrice: number;
    currentPrice: number;
    pnl: number;
    endDate?: string;
}

interface TraderData {
    wallet: string;
    username: string;
    positions: Position[];
    stats: {
        totalProfit: number;
        predictions: number;
        biggestWin: number;
    };
    error?: string;
    note?: string;
}

export default function FollowTraderPage() {
    const [loading, setLoading] = useState(false);
    const [data, setData] = useState<TraderData | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [lastRefresh, setLastRefresh] = useState<string | null>(null);

    const fetchTraderData = async () => {
        setLoading(true);
        setError(null);

        try {
            const res = await fetch("/api/follow-trader");
            if (!res.ok) throw new Error(`API error: ${res.status}`);

            const result = await res.json();
            setData(result);
            setLastRefresh(new Date().toLocaleTimeString());

            if (result.error) {
                setError(result.note || result.error);
            }
        } catch (e: any) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchTraderData();
    }, []);

    const formatCurrency = (value: number) => {
        return new Intl.NumberFormat("en-US", {
            style: "currency",
            currency: "USD",
            minimumFractionDigits: 2
        }).format(value);
    };

    const formatPercent = (value: number) => {
        return `${(value * 100).toFixed(1)}%`;
    };

    return (
        <div className="space-y-8">
            {/* Header */}
            <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-r from-blue-500/10 via-purple-500/10 to-pink-500/10 rounded-2xl blur-xl" />
                <div className="relative bg-zinc-900/80 backdrop-blur-sm border border-zinc-800 rounded-2xl p-6">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <span className="text-4xl">👤</span>
                            <div>
                                <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
                                    Follow Trader
                                </h1>
                                <p className="text-zinc-400 mt-1">Track @neobrother's positions on Polymarket</p>
                            </div>
                        </div>
                        <div className="flex items-center gap-4">
                            <a
                                href="https://polymarket.com/@neobrother"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-xl text-zinc-200 transition-colors"
                            >
                                View Profile →
                            </a>
                            <Button
                                onClick={fetchTraderData}
                                disabled={loading}
                                className="px-6 py-2 bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 rounded-xl"
                            >
                                {loading ? "⟳ Refreshing..." : "🔄 Refresh"}
                            </Button>
                        </div>
                    </div>
                </div>
            </div>

            {/* Stats */}
            {data?.stats && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <StatCard
                        icon="💰"
                        label="All-Time Profit"
                        value={formatCurrency(data.stats.totalProfit)}
                        color="from-green-500 to-emerald-500"
                    />
                    <StatCard
                        icon="📊"
                        label="Total Predictions"
                        value={data.stats.predictions.toLocaleString()}
                        color="from-blue-500 to-cyan-500"
                    />
                    <StatCard
                        icon="🏆"
                        label="Biggest Win"
                        value={formatCurrency(data.stats.biggestWin)}
                        color="from-amber-500 to-yellow-500"
                    />
                </div>
            )}

            {/* Error/Note */}
            {error && (
                <div className="bg-yellow-950/30 border border-yellow-800/50 rounded-2xl p-4">
                    <p className="text-yellow-400">⚠️ {error}</p>
                </div>
            )}

            {/* Positions */}
            <Card className="bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl">
                <CardHeader>
                    <CardTitle className="flex items-center justify-between">
                        <span className="flex items-center gap-2">
                            <span className="text-2xl">📈</span>
                            Active Positions
                        </span>
                        {lastRefresh && (
                            <span className="text-sm text-zinc-500 font-normal">
                                Last updated: {lastRefresh}
                            </span>
                        )}
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {loading ? (
                        <div className="text-center py-12">
                            <div className="text-4xl animate-spin mb-4">⟳</div>
                            <p className="text-zinc-400">Loading positions...</p>
                        </div>
                    ) : data?.positions && data.positions.length > 0 ? (
                        <div className="space-y-4">
                            {data.positions.map((pos, i) => (
                                <PositionCard key={i} position={pos} />
                            ))}
                        </div>
                    ) : (
                        <div className="text-center py-12">
                            <div className="text-6xl mb-4">📭</div>
                            <h3 className="text-xl font-semibold text-zinc-200">No Active Positions</h3>
                            <p className="text-zinc-500 mt-2">
                                Neobrother doesn't have any open positions right now, or the API is unavailable.
                            </p>
                            <p className="text-zinc-600 mt-4 text-sm">
                                Try visiting their{" "}
                                <a
                                    href="https://polymarket.com/@neobrother"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-blue-400 hover:underline"
                                >
                                    Polymarket profile
                                </a>{" "}
                                directly to see live positions.
                            </p>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Quick Links */}
            <Card className="bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <span className="text-2xl">🔗</span>
                        Quick Access
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex flex-wrap gap-4">
                        <a
                            href="https://polymarket.com/@neobrother"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="px-6 py-3 bg-zinc-800 hover:bg-zinc-700 rounded-xl text-zinc-200 transition-colors"
                        >
                            👤 Polymarket Profile
                        </a>
                        <a
                            href="https://polygonscan.com/address/0x6297b93ea37ff92a57fd636410f3b71ebf74517e"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="px-6 py-3 bg-zinc-800 hover:bg-zinc-700 rounded-xl text-zinc-200 transition-colors"
                        >
                            🔍 Wallet on Polygonscan
                        </a>
                        <a
                            href="https://x.com/spydenuevo"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="px-6 py-3 bg-zinc-800 hover:bg-zinc-700 rounded-xl text-zinc-200 transition-colors"
                        >
                            🐦 Twitter @spydenuevo
                        </a>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}

function StatCard({ icon, label, value, color }: { icon: string; label: string; value: string; color: string }) {
    return (
        <div className="group relative">
            <div className={`absolute inset-0 bg-gradient-to-r ${color} rounded-2xl opacity-0 group-hover:opacity-20 transition-opacity blur-xl`} />
            <Card className="relative bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl">
                <CardContent className="p-6">
                    <div className="flex items-center gap-4">
                        <span className="text-3xl">{icon}</span>
                        <div>
                            <p className={`text-2xl font-bold bg-gradient-to-r ${color} bg-clip-text text-transparent`}>
                                {value}
                            </p>
                            <p className="text-sm text-zinc-500">{label}</p>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}

function PositionCard({ position }: { position: Position }) {
    const pnlColor = position.pnl >= 0 ? "text-green-400" : "text-red-400";
    const pnlBg = position.pnl >= 0 ? "bg-green-900/30 border-green-800/50" : "bg-red-900/30 border-red-800/50";

    return (
        <Card className="bg-zinc-800/50 border-zinc-700 rounded-xl">
            <CardContent className="p-4">
                <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                        <h4 className="font-semibold text-zinc-100 line-clamp-2">
                            {position.question}
                        </h4>
                        <div className="flex items-center gap-4 mt-2 text-sm">
                            <span className={`px-2 py-1 rounded ${position.outcome === "Yes" ? "bg-green-900/50 text-green-400" : "bg-red-900/50 text-red-400"}`}>
                                {position.outcome}
                            </span>
                            <span className="text-zinc-400">
                                Size: <strong className="text-zinc-200">{position.size.toLocaleString()}</strong> shares
                            </span>
                            <span className="text-zinc-400">
                                Avg: <strong className="text-zinc-200">${(position.avgPrice * 100).toFixed(1)}¢</strong>
                            </span>
                        </div>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                        <span className={`px-3 py-1.5 rounded-lg border ${pnlBg} ${pnlColor} font-medium`}>
                            {position.pnl >= 0 ? "+" : ""}{position.pnl.toFixed(2)}
                        </span>
                        {position.slug && (
                            <a
                                href={`https://polymarket.com/market/${position.slug}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-sm text-blue-400 hover:underline"
                            >
                                Trade →
                            </a>
                        )}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
