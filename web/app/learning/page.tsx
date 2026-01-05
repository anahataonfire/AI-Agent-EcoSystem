"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface LearningPattern {
    type: string;
    context: string;
    outcome: string;
    confidence: number;
    created_at: string;
}

interface LearningSummary {
    feedback_count: number;
    patterns: LearningPattern[];
    categories: Record<string, number>;
}

export default function LearningPage() {
    const [summary, setSummary] = useState<LearningSummary | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchSummary = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch("http://localhost:8000/learning/summary", {
                headers: { "X-API-Key": "dev-token-change-me" },
            });
            if (!res.ok) throw new Error(`API error: ${res.status}`);
            const data = await res.json();
            setSummary(data);
        } catch (e: any) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchSummary();
    }, []);

    const sortedCategories = summary?.categories
        ? Object.entries(summary.categories).sort((a, b) => b[1] - a[1])
        : [];

    const acceptanceRate = summary?.patterns
        ? Math.round(
            (summary.patterns.filter((p) => p.outcome === "accepted").length /
                Math.max(summary.patterns.length, 1)) *
            100
        )
        : 0;

    return (
        <div className="space-y-8">
            {/* Header */}
            <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-r from-amber-500/10 via-yellow-500/10 to-lime-500/10 rounded-2xl blur-xl" />
                <div className="relative bg-zinc-900/80 backdrop-blur-sm border border-zinc-800 rounded-2xl p-6 flex items-center justify-between">
                    <div>
                        <h1 className="text-4xl font-bold bg-gradient-to-r from-amber-400 via-yellow-400 to-lime-400 bg-clip-text text-transparent">
                            Learning
                        </h1>
                        <p className="text-zinc-400 mt-2">How the system adapts to your preferences</p>
                    </div>
                    <Button
                        variant="outline"
                        onClick={fetchSummary}
                        disabled={loading}
                        className="rounded-xl border-zinc-700"
                    >
                        {loading ? "⟳ Loading..." : "↻ Refresh"}
                    </Button>
                </div>
            </div>

            {error && (
                <div className="bg-yellow-950/30 border border-yellow-800/50 rounded-2xl p-4">
                    <p className="text-yellow-400">⚠️ {error}</p>
                </div>
            )}

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <StatCard
                    icon="📊"
                    label="Feedback Signals"
                    value={summary?.feedback_count?.toString() || "0"}
                    description="Total interactions"
                    color="from-amber-500 to-yellow-500"
                />
                <StatCard
                    icon="🏷️"
                    label="Categories Learned"
                    value={sortedCategories.length.toString()}
                    description="Unique topics"
                    color="from-yellow-500 to-lime-500"
                />
                <StatCard
                    icon="✅"
                    label="Acceptance Rate"
                    value={`${acceptanceRate}%`}
                    description="Suggestions approved"
                    color="from-lime-500 to-green-500"
                />
            </div>

            {/* Category Preferences */}
            <Card className="bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <span>🧠</span> Category Preferences
                    </CardTitle>
                    <CardDescription>Topics you've shown interest in</CardDescription>
                </CardHeader>
                <CardContent>
                    {sortedCategories.length === 0 ? (
                        <div className="py-8 text-center">
                            <p className="text-zinc-500">No category preferences recorded yet.</p>
                        </div>
                    ) : (
                        <div className="flex flex-wrap gap-3">
                            {sortedCategories.map(([category, count], i) => (
                                <div
                                    key={category}
                                    className={`relative group ${i < 3 ? "text-lg" : "text-base"}`}
                                >
                                    <div className="absolute inset-0 bg-gradient-to-r from-amber-500/20 to-lime-500/20 rounded-xl blur-md opacity-0 group-hover:opacity-100 transition-opacity" />
                                    <div className="relative bg-zinc-800 border border-zinc-700 hover:border-amber-500/50 px-4 py-2 rounded-xl flex items-center gap-2 transition-colors">
                                        <span className={`${i < 3 ? "text-amber-400" : "text-zinc-300"}`}>{category}</span>
                                        <span className="bg-amber-500/20 text-amber-400 text-xs px-2 py-0.5 rounded-full">
                                            {count}
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Learning Timeline */}
            <Card className="bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <span>📜</span> Learning Timeline
                    </CardTitle>
                    <CardDescription>Recent feedback and decisions</CardDescription>
                </CardHeader>
                <CardContent>
                    {!summary?.patterns || summary.patterns.length === 0 ? (
                        <div className="py-12 text-center">
                            <div className="text-6xl mb-4">🧠</div>
                            <h3 className="text-xl font-semibold text-zinc-200">No feedback yet</h3>
                            <p className="text-zinc-500 mt-2 max-w-md mx-auto">
                                Accept or reject suggestions to help the system learn your preferences.
                            </p>
                        </div>
                    ) : (
                        <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
                            {summary.patterns.map((pattern, i) => (
                                <FeedbackRow key={i} pattern={pattern} />
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}

function StatCard({
    icon,
    label,
    value,
    description,
    color,
}: {
    icon: string;
    label: string;
    value: string;
    description: string;
    color: string;
}) {
    return (
        <div className="group relative">
            <div className={`absolute inset-0 bg-gradient-to-r ${color} rounded-2xl opacity-0 group-hover:opacity-20 transition-opacity blur-xl`} />
            <Card className="relative bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl h-full">
                <CardContent className="p-6">
                    <div className="flex items-center gap-4">
                        <span className="text-3xl">{icon}</span>
                        <div>
                            <p className={`text-3xl font-bold bg-gradient-to-r ${color} bg-clip-text text-transparent`}>
                                {value}
                            </p>
                            <p className="text-sm text-zinc-400">{label}</p>
                            <p className="text-xs text-zinc-600">{description}</p>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}

function FeedbackRow({ pattern }: { pattern: LearningPattern }) {
    let context: { suggested?: string; content_id?: string } = {};
    try {
        context = JSON.parse(pattern.context);
    } catch { }

    const isAccepted = pattern.outcome === "accepted";

    return (
        <div className="flex items-center gap-4 p-4 bg-zinc-800/50 rounded-xl hover:bg-zinc-800 transition-colors">
            <div className={`shrink-0 w-10 h-10 rounded-full flex items-center justify-center ${isAccepted ? "bg-green-500/20" : "bg-red-500/20"
                }`}>
                <span className={isAccepted ? "text-green-400" : "text-red-400"}>
                    {isAccepted ? "✓" : "✗"}
                </span>
            </div>
            <div className="flex-1 min-w-0">
                <p className="font-medium text-zinc-200 truncate">
                    {context.suggested || pattern.context.slice(0, 50)}
                </p>
                <p className="text-xs text-zinc-500">{pattern.type}</p>
            </div>
            <span className="text-xs text-zinc-600 shrink-0">
                {new Date(pattern.created_at).toLocaleDateString()}
            </span>
        </div>
    );
}
