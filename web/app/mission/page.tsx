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
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold">🛰️ Mission Control</h1>
                <p className="text-zinc-400 mt-1">Execute missions and monitor live telemetry</p>
            </div>

            <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader>
                    <CardTitle>📋 Mission Briefing</CardTitle>
                    <CardDescription>Define the objective for the autonomous agent swarm</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <Textarea
                        placeholder="e.g., Compare AI news coverage from BBC and TechCrunch"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        className="bg-zinc-800 border-zinc-700 min-h-[100px]"
                    />
                    <Button onClick={executeMission} disabled={loading || !query} className="w-full">
                        {loading ? "🔄 Mission in progress..." : "🚀 Execute Mission"}
                    </Button>
                </CardContent>
            </Card>

            {error && (
                <Card className="bg-red-950/50 border-red-800">
                    <CardContent className="p-4">
                        <p className="text-red-400">❌ Mission Aborted: {error}</p>
                    </CardContent>
                </Card>
            )}

            {result && (
                <>
                    <Card className="bg-zinc-900 border-zinc-800">
                        <CardHeader>
                            <CardTitle>📡 Live Telemetry</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="grid grid-cols-4 gap-4">
                                <TelemetryCard
                                    label="🎯 Alignment Score"
                                    value={`${result.telemetry.alignment_score.toFixed(1)}%`}
                                />
                                <TelemetryCard
                                    label="📦 Evidence Count"
                                    value={Object.keys(result.evidence_map).length.toString()}
                                />
                                <TelemetryCard
                                    label="🛡️ Sanitizer Status"
                                    value={result.telemetry.sanitizer_reject_count === 0 ? "🟢 Secure" : `🔴 ${result.telemetry.sanitizer_reject_count} Rejects`}
                                />
                                <TelemetryCard
                                    label="⚙️ Steps Executed"
                                    value={result.circuit_breaker.step_count.toString()}
                                />
                            </div>
                        </CardContent>
                    </Card>

                    {result.structured_report && (
                        <Card className="bg-blue-950/30 border-blue-800">
                            <CardContent className="p-4">
                                <p className="font-medium">Executive Summary:</p>
                                <p className="text-zinc-300 mt-1">{result.structured_report.executive_summary}</p>
                                <div className="flex gap-4 mt-3">
                                    <span className="text-sm">
                                        Sentiment: <strong className={result.structured_report.sentiment_score >= 7 ? "text-green-400" : result.structured_report.sentiment_score <= 4 ? "text-red-400" : "text-yellow-400"}>{result.structured_report.sentiment_score}/10</strong>
                                    </span>
                                    {result.structured_report.key_entities.length > 0 && (
                                        <span className="text-sm">
                                            Entities: {result.structured_report.key_entities.map((e) => (
                                                <code key={e} className="bg-zinc-800 px-1 mx-1 rounded text-xs">{e}</code>
                                            ))}
                                        </span>
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    <Card className="bg-zinc-900 border-zinc-800">
                        <CardHeader>
                            <CardTitle>📄 Mission Report</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="bg-zinc-950 p-4 rounded-lg border border-zinc-800 prose prose-invert prose-sm max-w-none">
                                <pre className="whitespace-pre-wrap text-sm">{result.final_report}</pre>
                            </div>
                        </CardContent>
                    </Card>
                </>
            )}
        </div>
    );
}

function TelemetryCard({ label, value }: { label: string; value: string }) {
    return (
        <div className="bg-zinc-800 p-3 rounded-lg">
            <p className="text-xs text-zinc-500">{label}</p>
            <p className="text-lg font-bold mt-1">{value}</p>
        </div>
    );
}
