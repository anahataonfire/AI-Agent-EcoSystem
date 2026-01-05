"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface ResearchResult {
    id: string;
    query: string;
    markdown: string;
    grounding_score: number;
    evidence_ids: string[];
}

export default function ResearchPage() {
    const [query, setQuery] = useState("");
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<ResearchResult | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [feedback, setFeedback] = useState<"positive" | "negative" | null>(null);

    const runResearch = async () => {
        if (!query.trim()) return;
        setLoading(true);
        setError(null);
        setFeedback(null);

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
            setResult(data);
        } catch (e: any) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    const submitFeedback = async (type: "positive" | "negative") => {
        setFeedback(type);
        if (result) {
            try {
                await fetch("http://localhost:8000/feedback", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-API-Key": "dev-token-change-me",
                    },
                    body: JSON.stringify({
                        item_id: result.id,
                        feedback_type: type,
                    }),
                });
            } catch { }
        }
    };

    return (
        <div className="space-y-8">
            {/* Header */}
            <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-r from-blue-500/10 via-indigo-500/10 to-violet-500/10 rounded-2xl blur-xl" />
                <div className="relative bg-zinc-900/80 backdrop-blur-sm border border-zinc-800 rounded-2xl p-6">
                    <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-400 via-indigo-400 to-violet-400 bg-clip-text text-transparent">
                        Research
                    </h1>
                    <p className="text-zinc-400 mt-2">Grounded answers backed by evidence — no hallucinations</p>
                </div>
            </div>

            {/* Query Input */}
            <Card className="bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <span className="text-2xl">🔬</span>
                        Research Query
                    </CardTitle>
                    <CardDescription>Ask a question — get a grounded, evidence-based answer</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <Textarea
                        placeholder="e.g., What are the latest developments in transformer architectures?"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        className="bg-zinc-800/50 border-zinc-700 min-h-[100px] rounded-xl text-lg"
                    />
                    <Button
                        onClick={runResearch}
                        disabled={loading || !query.trim()}
                        className="w-full h-14 text-lg rounded-xl bg-gradient-to-r from-blue-500 to-indigo-500 hover:from-blue-600 hover:to-indigo-600"
                    >
                        {loading ? "⟳ Researching..." : "🔍 Run Research"}
                    </Button>
                </CardContent>
            </Card>

            {error && (
                <div className="bg-red-950/30 border border-red-800/50 rounded-2xl p-6">
                    <p className="text-red-400">❌ Error: {error}</p>
                </div>
            )}

            {result && (
                <>
                    {/* Grounding Score */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <Card className="bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl col-span-1">
                            <CardContent className="p-6">
                                <div className="flex items-center gap-4">
                                    <div className="relative">
                                        <svg className="w-20 h-20 transform -rotate-90">
                                            <circle cx="40" cy="40" r="35" fill="none" stroke="#27272a" strokeWidth="8" />
                                            <circle
                                                cx="40"
                                                cy="40"
                                                r="35"
                                                fill="none"
                                                stroke="url(#gradient)"
                                                strokeWidth="8"
                                                strokeDasharray={`${(result.grounding_score / 100) * 220} 220`}
                                                strokeLinecap="round"
                                            />
                                            <defs>
                                                <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                                                    <stop offset="0%" stopColor="#3b82f6" />
                                                    <stop offset="100%" stopColor="#8b5cf6" />
                                                </linearGradient>
                                            </defs>
                                        </svg>
                                        <span className="absolute inset-0 flex items-center justify-center text-2xl font-bold">
                                            {result.grounding_score}%
                                        </span>
                                    </div>
                                    <div>
                                        <p className="font-semibold text-zinc-200">Grounding Score</p>
                                        <p className="text-sm text-zinc-500">Based on {result.evidence_ids.length} evidence items</p>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>

                        <Card className="bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl col-span-2">
                            <CardContent className="p-6">
                                <p className="text-sm text-zinc-500 mb-2">Evidence IDs Referenced:</p>
                                <div className="flex flex-wrap gap-2">
                                    {result.evidence_ids.slice(0, 10).map((id) => (
                                        <span key={id} className="text-xs bg-zinc-800 px-2 py-1 rounded-full text-blue-400 font-mono">
                                            {id.slice(0, 16)}...
                                        </span>
                                    ))}
                                    {result.evidence_ids.length > 10 && (
                                        <span className="text-xs text-zinc-500">+{result.evidence_ids.length - 10} more</span>
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Report */}
                    <Card className="bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl">
                        <CardHeader className="border-b border-zinc-800">
                            <div className="flex items-center justify-between">
                                <CardTitle className="flex items-center gap-2">
                                    <span>📄</span> Research Report
                                </CardTitle>
                                <div className="flex gap-2">
                                    <Button
                                        variant={feedback === "positive" ? "default" : "outline"}
                                        size="sm"
                                        onClick={() => submitFeedback("positive")}
                                        className={feedback === "positive" ? "bg-green-500" : "border-zinc-700"}
                                    >
                                        👍 Helpful
                                    </Button>
                                    <Button
                                        variant={feedback === "negative" ? "default" : "outline"}
                                        size="sm"
                                        onClick={() => submitFeedback("negative")}
                                        className={feedback === "negative" ? "bg-red-500" : "border-zinc-700"}
                                    >
                                        👎 Not Useful
                                    </Button>
                                </div>
                            </div>
                        </CardHeader>
                        <CardContent className="p-6">
                            <div className="prose prose-invert prose-sm max-w-none">
                                <pre className="whitespace-pre-wrap text-sm text-zinc-300 font-sans leading-relaxed bg-transparent p-0 m-0">
                                    {result.markdown}
                                </pre>
                            </div>
                        </CardContent>
                    </Card>
                </>
            )}

            {!loading && !result && (
                <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-12 text-center">
                    <div className="text-6xl mb-4">🔬</div>
                    <h3 className="text-xl font-semibold text-zinc-200">Ask anything</h3>
                    <p className="text-zinc-500 mt-2 max-w-md mx-auto">
                        Your questions are answered using only verified evidence from your library — no AI hallucinations.
                    </p>
                </div>
            )}
        </div>
    );
}
