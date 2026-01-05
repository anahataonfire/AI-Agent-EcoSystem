"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface MissionResult {
    final_report: string;
    telemetry: {
        alignment_score: number;
        sanitizer_reject_count: number;
    };
    evidence_map: Record<string, any>;
    circuit_breaker: {
        step_count: number;
    };
    structured_report?: {
        executive_summary: string;
        sentiment_score: number;
        key_entities: string[];
    };
}

export default function MissionControlPage() {
    const [query, setQuery] = useState("");
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<MissionResult | null>(null);
    const [error, setError] = useState<string | null>(null);

    const executeMission = async () => {
        if (!query) return;
        setLoading(true);
        setError(null);

        try {
            const res = await fetch("http://localhost:8000/research/run", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-API-Key": "dev-token-change-me",
                },
                body: JSON.stringify({ query, use_library: true }),
            });

            if (!res.ok) throw new Error(`API error: ${res.status}`);

            const data = await res.json();
            setResult({
                final_report: data.markdown,
                telemetry: {
                    alignment_score: data.grounding_score || 0,
                    sanitizer_reject_count: 0,
                },
                evidence_map: Object.fromEntries(
                    (data.evidence_ids || []).map((id: string) => [id, {}])
                ),
                circuit_breaker: { step_count: 1 },
            });
        } catch (e: any) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-8">
            {/* Header */}
            <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-r from-orange-500/10 via-red-500/10 to-purple-500/10 rounded-2xl blur-xl" />
                <div className="relative bg-zinc-900/80 backdrop-blur-sm border border-zinc-800 rounded-2xl p-6">
                    <h1 className="text-4xl font-bold bg-gradient-to-r from-orange-400 via-red-400 to-purple-400 bg-clip-text text-transparent">
                        Mission Control
                    </h1>
                    <p className="text-zinc-400 mt-2">Execute missions and monitor live telemetry</p>
                </div>
            </div>

            {/* Mission Input */}
            <Card className="bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <span className="text-2xl">📋</span>
                        Mission Briefing
                    </CardTitle>
                    <CardDescription>Define the objective for the autonomous agent swarm</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <Textarea
                        placeholder="e.g., Compare AI news coverage from BBC and TechCrunch"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        className="bg-zinc-800/50 border-zinc-700 min-h-[120px] rounded-xl text-lg"
                    />
                    <Button
                        onClick={executeMission}
                        disabled={loading || !query}
                        className="w-full h-14 text-lg rounded-xl bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-600 hover:to-red-600"
                    >
                        {loading ? (
                            <span className="flex items-center gap-2">
                                <span className="animate-spin">⟳</span> Mission in progress...
                            </span>
                        ) : (
                            <span className="flex items-center gap-2">
                                🚀 Execute Mission
                            </span>
                        )}
                    </Button>
                </CardContent>
            </Card>

            {error && (
                <div className="bg-red-950/30 border border-red-800/50 rounded-2xl p-6">
                    <p className="text-red-400 flex items-center gap-2">
                        <span>❌</span> Mission Aborted: {error}
                    </p>
                </div>
            )}

            {result && (
                <>
                    {/* Telemetry Grid */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <TelemetryCard
                            icon="🎯"
                            label="Alignment Score"
                            value={`${result.telemetry.alignment_score.toFixed(0)}%`}
                            color="from-green-500 to-emerald-500"
                        />
                        <TelemetryCard
                            icon="📦"
                            label="Evidence Count"
                            value={Object.keys(result.evidence_map).length.toString()}
                            color="from-blue-500 to-cyan-500"
                        />
                        <TelemetryCard
                            icon="🛡️"
                            label="Sanitizer"
                            value={result.telemetry.sanitizer_reject_count === 0 ? "Secure" : `${result.telemetry.sanitizer_reject_count} Rejects`}
                            color={result.telemetry.sanitizer_reject_count === 0 ? "from-green-500 to-teal-500" : "from-red-500 to-orange-500"}
                        />
                        <TelemetryCard
                            icon="⚙️"
                            label="Steps Executed"
                            value={result.circuit_breaker.step_count.toString()}
                            color="from-purple-500 to-pink-500"
                        />
                    </div>

                    {/* Executive Summary */}
                    {result.structured_report && (
                        <Card className="bg-blue-950/30 border-blue-800/50 rounded-2xl">
                            <CardContent className="p-6">
                                <h3 className="font-semibold text-blue-300 mb-2">Executive Summary</h3>
                                <p className="text-zinc-300">{result.structured_report.executive_summary}</p>
                                <div className="flex gap-4 mt-4 text-sm">
                                    <span className={`px-3 py-1 rounded-full ${result.structured_report.sentiment_score >= 7
                                            ? "bg-green-500/20 text-green-400"
                                            : result.structured_report.sentiment_score <= 4
                                                ? "bg-red-500/20 text-red-400"
                                                : "bg-yellow-500/20 text-yellow-400"
                                        }`}>
                                        Sentiment: {result.structured_report.sentiment_score}/10
                                    </span>
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    {/* Report */}
                    <Card className="bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <span>📄</span> Mission Report
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="bg-zinc-950/50 p-6 rounded-xl border border-zinc-800">
                                <pre className="whitespace-pre-wrap text-sm text-zinc-300 font-mono leading-relaxed">
                                    {result.final_report}
                                </pre>
                            </div>
                        </CardContent>
                    </Card>
                </>
            )}
        </div>
    );
}

function TelemetryCard({ icon, label, value, color }: { icon: string; label: string; value: string; color: string }) {
    return (
        <div className="group relative">
            <div className={`absolute inset-0 bg-gradient-to-r ${color} rounded-2xl opacity-0 group-hover:opacity-20 transition-opacity blur-xl`} />
            <Card className="relative bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl">
                <CardContent className="p-5">
                    <div className="flex items-center gap-3">
                        <span className="text-2xl">{icon}</span>
                        <div>
                            <p className={`text-xl font-bold bg-gradient-to-r ${color} bg-clip-text text-transparent`}>
                                {value}
                            </p>
                            <p className="text-xs text-zinc-500">{label}</p>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
