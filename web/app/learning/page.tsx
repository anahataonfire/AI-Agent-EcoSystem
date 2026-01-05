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

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold">📈 Learning</h1>
                    <p className="text-zinc-400 mt-1">How the system adapts to your preferences</p>
                </div>
                <Button variant="outline" onClick={fetchSummary} disabled={loading}>
                    {loading ? "Loading..." : "Refresh"}
                </Button>
            </div>

            {error && (
                <Card className="bg-yellow-950/50 border-yellow-800">
                    <CardContent className="p-4">
                        <p className="text-yellow-400">⚠️ Error: {error}</p>
                    </CardContent>
                </Card>
            )}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card className="bg-zinc-900 border-zinc-800">
                    <CardHeader>
                        <CardTitle>Feedback Given</CardTitle>
                        <CardDescription>Your input shapes the system</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="text-3xl font-bold">{summary?.feedback_count || 0}</div>
                        <p className="text-sm text-zinc-500">total feedback signals</p>
                    </CardContent>
                </Card>

                <Card className="bg-zinc-900 border-zinc-800">
                    <CardHeader>
                        <CardTitle>Categories Learned</CardTitle>
                        <CardDescription>Topics you engage with</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="text-3xl font-bold">{sortedCategories.length}</div>
                        <p className="text-sm text-zinc-500">unique categories</p>
                    </CardContent>
                </Card>

                <Card className="bg-zinc-900 border-zinc-800">
                    <CardHeader>
                        <CardTitle>Acceptance Rate</CardTitle>
                        <CardDescription>Suggestions you approved</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="text-3xl font-bold">
                            {summary?.patterns
                                ? Math.round(
                                    (summary.patterns.filter((p) => p.outcome === "accepted").length /
                                        summary.patterns.length) *
                                    100
                                ) || 0
                                : 0}%
                        </div>
                        <p className="text-sm text-zinc-500">of suggestions accepted</p>
                    </CardContent>
                </Card>
            </div>

            <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader>
                    <CardTitle>🏷️ Category Preferences</CardTitle>
                    <CardDescription>Topics you've expressed interest in</CardDescription>
                </CardHeader>
                <CardContent>
                    {sortedCategories.length === 0 ? (
                        <p className="text-zinc-500">No category preferences recorded yet.</p>
                    ) : (
                        <div className="flex flex-wrap gap-2">
                            {sortedCategories.map(([category, count]) => (
                                <div
                                    key={category}
                                    className="bg-blue-500/20 text-blue-400 px-3 py-1.5 rounded-lg text-sm flex items-center gap-2"
                                >
                                    <span>{category}</span>
                                    <span className="bg-blue-500/30 px-1.5 py-0.5 rounded text-xs">
                                        {count}
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader>
                    <CardTitle>📜 Recent Feedback</CardTitle>
                    <CardDescription>Your recent interactions and decisions</CardDescription>
                </CardHeader>
                <CardContent>
                    {!summary?.patterns || summary.patterns.length === 0 ? (
                        <div className="py-8 text-center">
                            <div className="text-4xl mb-4">🧠</div>
                            <h3 className="text-lg font-medium">No feedback yet</h3>
                            <p className="text-zinc-500 mt-2">
                                Accept or reject category suggestions to teach the system.
                            </p>
                        </div>
                    ) : (
                        <div className="space-y-2 max-h-80 overflow-y-auto">
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

function FeedbackRow({ pattern }: { pattern: LearningPattern }) {
    let context: { suggested?: string; content_id?: string } = {};
    try {
        context = JSON.parse(pattern.context);
    } catch { }

    const isAccepted = pattern.outcome === "accepted";

    return (
        <div className="flex items-center gap-3 p-2 bg-zinc-800 rounded-lg">
            <span className={isAccepted ? "text-green-400" : "text-red-400"}>
                {isAccepted ? "✓" : "✗"}
            </span>
            <span className="text-xs bg-zinc-700 px-2 py-1 rounded">{pattern.type}</span>
            <span className="flex-1 text-sm truncate">
                {context.suggested || pattern.context.slice(0, 50)}
            </span>
            <span className="text-xs text-zinc-500">
                {new Date(pattern.created_at).toLocaleDateString()}
            </span>
        </div>
    );
}
