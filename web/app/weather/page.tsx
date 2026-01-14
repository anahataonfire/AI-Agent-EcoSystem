"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface WeatherOpportunity {
    city: string;
    city_name: string;
    target_date: string;
    bucket_low: number;
    bucket_high: number;
    bucket_unit: string;
    forecast_temp: number;
    forecast_confidence: number;
    market_price: number;
    calculated_probability: number;
    edge: number;
    liquidity: number;
    hours_remaining: number;
    market_url: string;
}

interface Forecast {
    city: string;
    temp: number;
    unit: string;
    confidence: number;
}

const CITIES = [
    { key: "nyc", name: "NYC", flag: "🇺🇸" },
    { key: "london", name: "London", flag: "🇬🇧" },
    { key: "buenos_aires", name: "Buenos Aires", flag: "🇦🇷" },
    { key: "seattle", name: "Seattle", flag: "🇺🇸" },
    { key: "toronto", name: "Toronto", flag: "🇨🇦" },
    { key: "atlanta", name: "Atlanta", flag: "🇺🇸" },
];

export default function WeatherTradingPage() {
    const [selectedCities, setSelectedCities] = useState<string[]>(["nyc", "london"]);
    const [edgeThreshold, setEdgeThreshold] = useState(15);
    const [loading, setLoading] = useState(false);
    const [useLive, setUseLive] = useState(false);
    const [opportunities, setOpportunities] = useState<WeatherOpportunity[]>([]);
    const [forecasts, setForecasts] = useState<Forecast[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [lastScan, setLastScan] = useState<string | null>(null);

    const toggleCity = (cityKey: string) => {
        setSelectedCities((prev) =>
            prev.includes(cityKey)
                ? prev.filter((c) => c !== cityKey)
                : [...prev, cityKey]
        );
    };

    const scanMarkets = async (live: boolean = false) => {
        setLoading(true);
        setError(null);

        try {
            const res = await fetch(
                `/api/weather/scan?cities=${selectedCities.join(",")}&min_edge=${edgeThreshold / 100}&live=${live}`
            );

            if (!res.ok) throw new Error(`API error: ${res.status}`);
            const data = await res.json();

            if (data.error) {
                throw new Error(data.error);
            }

            setOpportunities(data.opportunities || []);
            setForecasts(data.forecasts || []);
            setLastScan(new Date().toLocaleTimeString());
        } catch (e: any) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    const edgeOpportunities = opportunities.filter((o) => o.edge >= edgeThreshold / 100);
    const totalLiquidity = opportunities.reduce((sum, o) => sum + o.liquidity, 0);
    const soonest = opportunities.length > 0
        ? Math.min(...opportunities.map((o) => o.hours_remaining))
        : 0;

    return (
        <div className="space-y-8">
            {/* Header */}
            <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-r from-orange-500/10 via-amber-500/10 to-yellow-500/10 rounded-2xl blur-xl" />
                <div className="relative bg-zinc-900/80 backdrop-blur-sm border border-zinc-800 rounded-2xl p-6">
                    <div className="flex items-center gap-3">
                        <span className="text-4xl">🌡️</span>
                        <div>
                            <h1 className="text-4xl font-bold bg-gradient-to-r from-orange-400 via-amber-400 to-yellow-400 bg-clip-text text-transparent">
                                Weather Trading
                            </h1>
                            <p className="text-zinc-400 mt-1">Temperature bracket betting on Polymarket</p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Controls */}
            <Card className="bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <span className="text-2xl">⚙️</span>
                        Scanner Settings
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                    {/* City Selector */}
                    <div>
                        <label className="text-sm text-zinc-400 mb-3 block">Select Cities</label>
                        <div className="flex flex-wrap gap-2">
                            {CITIES.map((city) => (
                                <button
                                    key={city.key}
                                    onClick={() => toggleCity(city.key)}
                                    className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${selectedCities.includes(city.key)
                                        ? "bg-gradient-to-r from-orange-500 to-amber-500 text-white"
                                        : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
                                        }`}
                                >
                                    {city.flag} {city.name}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Edge Threshold */}
                    <div>
                        <label className="text-sm text-zinc-400 mb-2 block">Minimum Edge Threshold</label>
                        <div className="flex items-center gap-4">
                            <input
                                type="range"
                                min={5}
                                max={50}
                                step={5}
                                value={edgeThreshold}
                                onChange={(e) => setEdgeThreshold(Number(e.target.value))}
                                className="flex-1 accent-orange-500"
                            />
                            <span className="text-lg font-bold text-orange-400 w-16">{edgeThreshold}%</span>
                        </div>
                    </div>

                    {/* Scan Buttons */}
                    <div className="flex gap-4">
                        <Button
                            onClick={() => scanMarkets(false)}
                            disabled={loading || selectedCities.length === 0}
                            className="flex-1 h-14 text-lg rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200"
                        >
                            {loading ? "⟳ Loading..." : "📋 Demo Data"}
                        </Button>
                        <Button
                            onClick={() => scanMarkets(true)}
                            disabled={loading || selectedCities.length === 0}
                            className="flex-1 h-14 text-lg rounded-xl bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600"
                        >
                            {loading ? "⟳ Scanning Polymarket..." : "🚀 Run Live Scanner"}
                        </Button>
                    </div>

                    {lastScan && (
                        <p className="text-sm text-zinc-500 text-center">Last scan: {lastScan}</p>
                    )}
                </CardContent>
            </Card>

            {error && (
                <div className="bg-red-950/30 border border-red-800/50 rounded-2xl p-4">
                    <p className="text-red-400">❌ {error}</p>
                </div>
            )}

            {/* Stats */}
            {opportunities.length > 0 && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <StatCard
                        icon="🌡️"
                        label="Forecasts"
                        value={forecasts.map((f) => `${f.temp}°${f.unit}`).join(", ") || "—"}
                        color="from-orange-500 to-amber-500"
                    />
                    <StatCard
                        icon="📊"
                        label="Edge Found"
                        value={`${edgeOpportunities.length} markets`}
                        color="from-amber-500 to-yellow-500"
                    />
                    <StatCard
                        icon="💰"
                        label="Total Liquidity"
                        value={`$${totalLiquidity.toLocaleString()}`}
                        color="from-yellow-500 to-lime-500"
                    />
                    <StatCard
                        icon="⏱️"
                        label="Soonest"
                        value={`${soonest.toFixed(1)}h`}
                        color="from-lime-500 to-green-500"
                    />
                </div>
            )}

            {/* Opportunities */}
            {opportunities.length > 0 && (
                <div className="space-y-4">
                    <h2 className="text-xl font-semibold text-zinc-200">
                        {opportunities.length} Markets Found
                    </h2>
                    {opportunities.map((opp, i) => (
                        <OpportunityCard key={i} opportunity={opp} threshold={edgeThreshold / 100} />
                    ))}
                </div>
            )}

            {!loading && opportunities.length === 0 && (
                <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-12 text-center">
                    <div className="text-6xl mb-4">🌤️</div>
                    <h3 className="text-xl font-semibold text-zinc-200">Ready to scan</h3>
                    <p className="text-zinc-500 mt-2">
                        Select cities and click "Scan Markets" to find temperature trading opportunities
                    </p>
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

function OpportunityCard({ opportunity, threshold }: { opportunity: WeatherOpportunity; threshold: number }) {
    const hasEdge = opportunity.edge >= threshold;
    const isNearResolution = opportunity.hours_remaining < 6;

    const city = CITIES.find((c) => c.key === opportunity.city);
    const flag = city?.flag || "🌍";

    const bucketLabel =
        opportunity.bucket_low === -Infinity
            ? `${opportunity.bucket_high}°${opportunity.bucket_unit} or below`
            : opportunity.bucket_high === Infinity
                ? `${opportunity.bucket_low}°${opportunity.bucket_unit} or above`
                : `${opportunity.bucket_low}-${opportunity.bucket_high}°${opportunity.bucket_unit}`;

    const dateLabel = new Date(opportunity.target_date).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
    });

    const borderColor = hasEdge
        ? "border-green-500/50 bg-green-950/20"
        : "border-zinc-700 bg-zinc-900/50";

    return (
        <Card className={`${borderColor} border rounded-2xl transition-all hover:scale-[1.01]`}>
            <CardContent className="p-6">
                <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                        {/* Header */}
                        <div className="flex items-center gap-2 mb-3">
                            <span className="text-xl">{flag}</span>
                            <span className="text-lg font-semibold text-zinc-100">
                                {opportunity.city_name}
                            </span>
                            <span className="text-zinc-500">•</span>
                            <span className="text-zinc-400">{dateLabel}</span>
                            <span className="text-zinc-500">•</span>
                            <span className="text-orange-400 font-medium">{bucketLabel}</span>
                        </div>

                        {/* Forecast */}
                        <div className="flex items-center gap-4 mb-4">
                            <div className="flex items-center gap-2">
                                <span className="text-sm text-zinc-400">Forecast:</span>
                                <span className="text-lg font-bold text-amber-400">
                                    {opportunity.forecast_temp}°{opportunity.bucket_unit}
                                </span>
                            </div>
                            <div className="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-gradient-to-r from-orange-500 to-amber-500"
                                    style={{ width: `${opportunity.forecast_confidence * 100}%` }}
                                />
                            </div>
                            <span className="text-sm text-zinc-400">
                                {(opportunity.forecast_confidence * 100).toFixed(0)}% conf
                            </span>
                        </div>

                        {/* Pricing Comparison */}
                        <div className="flex items-center gap-4 text-sm">
                            <span className="px-3 py-1.5 bg-zinc-800 rounded-lg">
                                Market: <strong className="text-zinc-200">${(opportunity.market_price * 100).toFixed(0)}¢</strong>
                            </span>
                            <span className="px-3 py-1.5 bg-zinc-800 rounded-lg">
                                Your Prob: <strong className="text-amber-400">{(opportunity.calculated_probability * 100).toFixed(0)}%</strong>
                            </span>
                            <span className={`px-3 py-1.5 rounded-lg ${hasEdge ? "bg-green-900/50 text-green-400" : "bg-red-900/30 text-red-400"
                                }`}>
                                Edge: <strong>{opportunity.edge > 0 ? "+" : ""}{(opportunity.edge * 100).toFixed(0)}%</strong>
                            </span>
                            <span className="text-zinc-500">
                                💰 ${opportunity.liquidity.toLocaleString()}
                            </span>
                            {isNearResolution && (
                                <span className="text-yellow-400">⏳ {opportunity.hours_remaining.toFixed(1)}h</span>
                            )}
                        </div>
                    </div>

                    {/* Action */}
                    <div className="flex flex-col items-end gap-2">
                        {hasEdge ? (
                            <div className="px-4 py-2 bg-green-500/20 border border-green-500/50 rounded-xl text-green-400 font-bold">
                                {(opportunity.edge * 100).toFixed(0)}% EDGE ✓
                            </div>
                        ) : (
                            <div className="px-4 py-2 bg-red-500/20 border border-red-500/50 rounded-xl text-red-400 font-medium">
                                NO EDGE
                            </div>
                        )}
                        <a
                            href={opportunity.market_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className={`px-6 py-3 rounded-xl text-sm font-medium transition-all ${hasEdge
                                ? "bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600 text-white"
                                : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
                                }`}
                        >
                            Trade →
                        </a>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
