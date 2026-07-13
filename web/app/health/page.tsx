"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface HealthReport {
    topics_active: number;
    topics_pending: number;
    topics_archived: number;
    last_sync_time: string;
    last_sync_outcome: string;
    top_topics: Array<{ topic_id: string; source_count: number }>;
    fingerprint_mismatches: number;
    notify_count_7d: number;
    planner_tasks_7d: number;
    generated_at: string;
}

export default function HealthPage() {
    const [report, setReport] = useState<HealthReport | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchHealth = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch("http://localhost:8000/health/datamart", {
                headers: { "X-API-Key": "dev-token-change-me" },
            });
            if (!res.ok) throw new Error(`API error: ${res.status}`);
            const data = await res.json();
            setReport(data);
        } catch (e: any) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchHealth();
    }, []);

    const outcomeColors: Record<string, string> = {
        SUCCESS: "bg-green-500/20 text-green-400 border-green-500/30",
        FAILED: "bg-red-500/20 text-red-400 border-red-500/30",
        Unknown: "bg-zinc-500/20 text-zinc-400 border-zinc-500/30",
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-r from-emerald-500/10 via-green-500/10 to-teal-500/10 rounded-2xl blur-xl" />
                <div className="relative bg-zinc-900/80 backdrop-blur-sm border border-zinc-800 rounded-2xl p-6">
                    <div className="flex items-center justify-between">
                        <div>
                            <h1 className="text-3xl font-bold bg-gradient-to-r from-emerald-400 via-green-400 to-teal-400 bg-clip-text text-transparent">
                                💊 System Health
                            </h1>
                            <p className="text-zinc-500 text-sm mt-1">
                                Datamart infrastructure status
                                {report && <span className="ml-2 text-zinc-600">• Generated: {new Date(report.generated_at).toLocaleString()}</span>}
                            </p>
                        </div>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={fetchHealth}
                            disabled={loading}
                            className="h-10 px-4 rounded-lg border-zinc-700"
                        >
                            {loading ? "⟳" : "↻ Refresh"}
                        </Button>
                    </div>
                </div>
            </div>

            {error && (
                <div className="bg-red-950/30 border border-red-800/50 rounded-xl p-4 flex items-center justify-between">
                    <div>
                        <p className="text-red-400 font-medium">⚠️ Connection Error</p>
                        <p className="text-red-400/70 text-sm">{error}</p>
                    </div>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={fetchHealth}
                        className="border-red-800 text-red-400 hover:bg-red-900/30"
                    >
                        ↻ Retry
                    </Button>
                </div>
            )}

            {loading && !report ? (
                <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-12 text-center">
                    <div className="text-4xl mb-3 animate-pulse">💊</div>
                    <p className="text-zinc-500">Loading health report...</p>
                </div>
            ) : report && (
                <div className="space-y-6">
                    {/* Status Cards */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        {/* Topic Status */}
                        <Card className="bg-zinc-900/80 border-zinc-800 rounded-xl">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm text-zinc-400 font-normal">Topics</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="flex items-baseline gap-2">
                                    <span className="text-3xl font-bold text-emerald-400">{report.topics_active}</span>
                                    <span className="text-sm text-zinc-500">active</span>
                                </div>
                                <div className="flex gap-3 mt-2 text-xs">
                                    <span className="text-amber-400">{report.topics_pending} pending</span>
                                    <span className="text-zinc-500">{report.topics_archived} archived</span>
                                </div>
                            </CardContent>
                        </Card>

                        {/* Last Sync */}
                        <Card className="bg-zinc-900/80 border-zinc-800 rounded-xl">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm text-zinc-400 font-normal">Last Sync</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <span className={`inline-block text-sm px-3 py-1 rounded-full border ${outcomeColors[report.last_sync_outcome] || outcomeColors.Unknown}`}>
                                    {report.last_sync_outcome}
                                </span>
                                <p className="text-[10px] text-zinc-500 mt-2 truncate" title={report.last_sync_time}>
                                    {report.last_sync_time}
                                </p>
                            </CardContent>
                        </Card>

                        {/* Fingerprint Status */}
                        <Card className="bg-zinc-900/80 border-zinc-800 rounded-xl">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm text-zinc-400 font-normal">Fingerprints</CardTitle>
                            </CardHeader>
                            <CardContent>
                                {report.fingerprint_mismatches === 0 ? (
                                    <div className="text-2xl">✅</div>
                                ) : (
                                    <div className="text-2xl">⚠️</div>
                                )}
                                <p className="text-sm text-zinc-300 mt-1">
                                    {report.fingerprint_mismatches === 0 ? "All valid" : `${report.fingerprint_mismatches} mismatches`}
                                </p>
                            </CardContent>
                        </Card>

                        {/* 7-Day Activity */}
                        <Card className="bg-zinc-900/80 border-zinc-800 rounded-xl">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm text-zinc-400 font-normal">7-Day Activity</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="flex gap-4">
                                    <div>
                                        <div className="text-xl font-bold text-cyan-400">{report.notify_count_7d}</div>
                                        <div className="text-[10px] text-zinc-500">NOTIFY</div>
                                    </div>
                                    <div>
                                        <div className="text-xl font-bold text-violet-400">{report.planner_tasks_7d}</div>
                                        <div className="text-[10px] text-zinc-500">Planner</div>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Top Topics */}
                    <Card className="bg-zinc-900/80 border-zinc-800 rounded-xl">
                        <CardHeader>
                            <CardTitle className="text-lg flex items-center gap-2">
                                <span>📊</span> Top Topics by Source Count
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {report.top_topics.length === 0 ? (
                                <p className="text-zinc-500 text-sm">No bundles with sources yet.</p>
                            ) : (
                                <div className="space-y-2">
                                    {report.top_topics.map((topic, i) => (
                                        <div key={topic.topic_id} className="flex items-center gap-3">
                                            <span className="text-sm text-zinc-500 w-6">{i + 1}.</span>
                                            <span className="text-sm text-zinc-200 flex-1 font-mono">{topic.topic_id}</span>
                                            <div className="flex items-center gap-2">
                                                <div
                                                    className="h-2 bg-gradient-to-r from-emerald-500 to-teal-500 rounded-full"
                                                    style={{ width: `${Math.min(topic.source_count * 20, 200)}px` }}
                                                />
                                                <span className="text-sm text-emerald-400 w-8 text-right">{topic.source_count}</span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </div>
            )}
        </div>
    );
}
