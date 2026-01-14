"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface DatamartItem {
    topic_id: string;
    topic_name: string;
    source_count: number;
    version: number;
    fingerprint: string;
    status: string;
    created_at: string;
    updated_at: string;
}

export default function DatamartsPage() {
    const [datamarts, setDatamarts] = useState<DatamartItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchDatamarts = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch("http://localhost:8000/datamarts/list?include_archived=true", {
                headers: { "X-API-Key": "dev-token-change-me" },
            });
            if (!res.ok) throw new Error(`API error: ${res.status}`);
            const data = await res.json();
            setDatamarts(data);
        } catch (e: any) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchDatamarts();
    }, []);

    const statusColors: Record<string, string> = {
        active: "bg-green-500/20 text-green-400 border-green-500/30",
        pending: "bg-amber-500/20 text-amber-400 border-amber-500/30",
        archived: "bg-zinc-500/20 text-zinc-400 border-zinc-500/30",
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-r from-teal-500/10 via-cyan-500/10 to-blue-500/10 rounded-2xl blur-xl" />
                <div className="relative bg-zinc-900/80 backdrop-blur-sm border border-zinc-800 rounded-2xl p-6">
                    <div className="flex items-center justify-between">
                        <div>
                            <h1 className="text-3xl font-bold bg-gradient-to-r from-teal-400 via-cyan-400 to-blue-400 bg-clip-text text-transparent">
                                📦 Datamarts
                            </h1>
                            <p className="text-zinc-500 text-sm mt-1">
                                NotebookLM-ready knowledge bundles • {datamarts.length} topics
                            </p>
                        </div>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={fetchDatamarts}
                            disabled={loading}
                            className="h-10 px-4 rounded-lg border-zinc-700"
                        >
                            {loading ? "⟳" : "↻ Refresh"}
                        </Button>
                    </div>
                </div>
            </div>

            {error && (
                <div className="bg-red-950/30 border border-red-800/50 rounded-xl p-3 text-sm">
                    <p className="text-red-400">⚠️ {error}</p>
                </div>
            )}

            {loading && datamarts.length === 0 ? (
                <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-12 text-center">
                    <div className="text-4xl mb-3 animate-pulse">📦</div>
                    <p className="text-zinc-500">Loading datamarts...</p>
                </div>
            ) : datamarts.length === 0 ? (
                <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-12 text-center">
                    <div className="text-4xl mb-3">📦</div>
                    <p className="text-zinc-500">No datamarts found. Process content to create bundles.</p>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                    {datamarts.map((dm) => (
                        <Card
                            key={dm.topic_id}
                            className="bg-gradient-to-br from-zinc-900/90 to-teal-900/10 border-teal-500/20 hover:border-teal-400/40 rounded-xl transition-all group"
                        >
                            <CardHeader className="pb-2">
                                <div className="flex items-start justify-between">
                                    <div className="flex-1 min-w-0">
                                        <CardTitle className="text-base font-semibold text-zinc-100 truncate">
                                            {dm.topic_name}
                                        </CardTitle>
                                        <CardDescription className="text-xs text-zinc-500 font-mono mt-1">
                                            {dm.topic_id}
                                        </CardDescription>
                                    </div>
                                    <span className={`shrink-0 text-[10px] px-2 py-0.5 rounded-full border ${statusColors[dm.status] || statusColors.archived}`}>
                                        {dm.status}
                                    </span>
                                </div>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                {/* Stats */}
                                <div className="grid grid-cols-3 gap-2 text-center">
                                    <div className="bg-zinc-800/50 rounded-lg p-2">
                                        <div className="text-lg font-bold text-teal-400">{dm.source_count}</div>
                                        <div className="text-[10px] text-zinc-500">Sources</div>
                                    </div>
                                    <div className="bg-zinc-800/50 rounded-lg p-2">
                                        <div className="text-lg font-bold text-cyan-400">v{dm.version}</div>
                                        <div className="text-[10px] text-zinc-500">Version</div>
                                    </div>
                                    <div className="bg-zinc-800/50 rounded-lg p-2">
                                        <div className="text-[10px] font-mono text-zinc-400 truncate">{dm.fingerprint.slice(0, 12)}</div>
                                        <div className="text-[10px] text-zinc-500">Fingerprint</div>
                                    </div>
                                </div>

                                {/* Timestamps */}
                                <div className="text-[10px] text-zinc-600 flex justify-between">
                                    <span>Created: {new Date(dm.created_at).toLocaleDateString()}</span>
                                    <span>Updated: {new Date(dm.updated_at).toLocaleDateString()}</span>
                                </div>

                                {/* Actions */}
                                <div className="flex gap-2 pt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <Button variant="ghost" size="sm" className="h-7 text-xs text-teal-400 hover:text-teal-300 flex-1">
                                        View Bundle
                                    </Button>
                                    <Button variant="ghost" size="sm" className="h-7 text-xs text-zinc-500 hover:text-zinc-300">
                                        Rebuild
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}
