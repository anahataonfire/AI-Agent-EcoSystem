"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";

interface DatamartTopic {
    id: string;
    name: string;
    status: string;
}

interface ResearchJob {
    research_id: string;
    status: string;
    topic: string;
    evidence_count: number;
    report_id?: string;
    datamart?: string;
    drive_synced: boolean;
    error?: string;
    created_at: string;
    completed_at?: string;
}

export default function ResearchPage() {
    // Form state
    const [topic, setTopic] = useState("");
    const [keywords, setKeywords] = useState("");
    const [targetDatamart, setTargetDatamart] = useState("auto");
    const [sources, setSources] = useState({ google_news: true, reddit: true });
    const [syncToDrive, setSyncToDrive] = useState(true);

    // UI state
    const [loading, setLoading] = useState(false);
    const [datamarts, setDatamarts] = useState<DatamartTopic[]>([]);
    const [currentJob, setCurrentJob] = useState<ResearchJob | null>(null);
    const [recentJobs, setRecentJobs] = useState<ResearchJob[]>([]);
    const [error, setError] = useState<string | null>(null);

    // Load datamarts on mount
    useEffect(() => {
        fetchDatamarts();
        fetchRecentJobs();
    }, []);

    // Poll for job status when running
    useEffect(() => {
        if (currentJob && !["completed", "failed"].includes(currentJob.status)) {
            const interval = setInterval(() => pollJobStatus(currentJob.research_id), 2000);
            return () => clearInterval(interval);
        }
    }, [currentJob]);

    const fetchDatamarts = async () => {
        try {
            const res = await fetch("http://localhost:8000/datamarts/topics", {
                headers: { "X-API-Key": "dev-token-change-me" },
            });
            if (res.ok) {
                const data = await res.json();
                setDatamarts(data);
            }
        } catch (e) {
            console.error("Failed to load datamarts:", e);
        }
    };

    const fetchRecentJobs = async () => {
        try {
            const res = await fetch("http://localhost:8000/research/jobs", {
                headers: { "X-API-Key": "dev-token-change-me" },
            });
            if (res.ok) {
                const data = await res.json();
                setRecentJobs(data);
            }
        } catch (e) {
            console.error("Failed to load jobs:", e);
        }
    };

    const pollJobStatus = async (researchId: string) => {
        try {
            const res = await fetch(`http://localhost:8000/research/${researchId}/status`, {
                headers: { "X-API-Key": "dev-token-change-me" },
            });
            if (res.ok) {
                const data = await res.json();
                setCurrentJob(data);
                if (["completed", "failed"].includes(data.status)) {
                    fetchRecentJobs();
                }
            }
        } catch (e) {
            console.error("Poll error:", e);
        }
    };

    const startResearch = async () => {
        if (!topic.trim()) return;
        setLoading(true);
        setError(null);

        try {
            const selectedSources = [];
            if (sources.google_news) selectedSources.push("google_news");
            if (sources.reddit) selectedSources.push("reddit");

            const res = await fetch("http://localhost:8000/research/start", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-API-Key": "dev-token-change-me",
                },
                body: JSON.stringify({
                    topic: topic.trim(),
                    keywords: keywords.split(",").map(k => k.trim()).filter(Boolean),
                    target_datamart: targetDatamart === "auto" ? null : targetDatamart,
                    sources: selectedSources,
                    sync_to_drive: syncToDrive,
                }),
            });

            if (!res.ok) throw new Error(`API error: ${res.status}`);
            const data = await res.json();
            setCurrentJob(data);
        } catch (e: any) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    const getStatusBadge = (status: string) => {
        const styles: Record<string, string> = {
            queued: "bg-yellow-500/20 text-yellow-400",
            fetching: "bg-blue-500/20 text-blue-400",
            synthesizing: "bg-purple-500/20 text-purple-400",
            completed: "bg-green-500/20 text-green-400",
            failed: "bg-red-500/20 text-red-400",
        };
        return <span className={`px-2 py-1 rounded-full text-xs font-medium ${styles[status] || "bg-zinc-700"}`}>{status}</span>;
    };

    return (
        <div className="space-y-8">
            {/* Header */}
            <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-r from-blue-500/10 via-indigo-500/10 to-violet-500/10 rounded-2xl blur-xl" />
                <div className="relative bg-zinc-900/80 backdrop-blur-sm border border-zinc-800 rounded-2xl p-6">
                    <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-400 via-indigo-400 to-violet-400 bg-clip-text text-transparent">
                        🔬 Deep Research
                    </h1>
                    <p className="text-zinc-400 mt-2">Multi-source research → LLM synthesis → Datamart → NotebookLM</p>
                </div>
            </div>

            {/* Research Form */}
            <Card className="bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <span className="text-2xl">📝</span>
                        Start Research
                    </CardTitle>
                    <CardDescription>Enter a topic and configure your research parameters</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    {/* Topic */}
                    <div className="space-y-2">
                        <Label htmlFor="topic">Research Topic</Label>
                        <Input
                            id="topic"
                            placeholder="e.g., AI agents, prediction markets, transformer architectures..."
                            value={topic}
                            onChange={(e) => setTopic(e.target.value)}
                            className="bg-zinc-800/50 border-zinc-700 rounded-xl"
                        />
                    </div>

                    {/* Keywords */}
                    <div className="space-y-2">
                        <Label htmlFor="keywords">Keywords (optional, comma-separated)</Label>
                        <Input
                            id="keywords"
                            placeholder="LangChain, AutoGPT, CrewAI..."
                            value={keywords}
                            onChange={(e) => setKeywords(e.target.value)}
                            className="bg-zinc-800/50 border-zinc-700 rounded-xl"
                        />
                    </div>

                    {/* Datamart Selector */}
                    <div className="space-y-2">
                        <Label>Target Datamart</Label>
                        <Select value={targetDatamart} onValueChange={setTargetDatamart}>
                            <SelectTrigger className="bg-zinc-800/50 border-zinc-700 rounded-xl">
                                <SelectValue placeholder="Auto-detect..." />
                            </SelectTrigger>
                            <SelectContent className="bg-zinc-900 border-zinc-700">
                                <SelectItem value="auto">🔮 Auto-detect from topic</SelectItem>
                                {datamarts.map((d) => (
                                    <SelectItem key={d.id} value={d.id}>
                                        📁 {d.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Sources */}
                    <div className="space-y-2">
                        <Label>Sources</Label>
                        <div className="flex gap-6">
                            <div className="flex items-center gap-2">
                                <Checkbox
                                    id="google_news"
                                    checked={sources.google_news}
                                    onCheckedChange={(checked) => setSources(s => ({ ...s, google_news: !!checked }))}
                                />
                                <Label htmlFor="google_news" className="text-sm cursor-pointer">📰 Google News</Label>
                            </div>
                            <div className="flex items-center gap-2">
                                <Checkbox
                                    id="reddit"
                                    checked={sources.reddit}
                                    onCheckedChange={(checked) => setSources(s => ({ ...s, reddit: !!checked }))}
                                />
                                <Label htmlFor="reddit" className="text-sm cursor-pointer">🗣️ Reddit</Label>
                            </div>
                        </div>
                    </div>

                    {/* Sync to Drive */}
                    <div className="flex items-center gap-2">
                        <Checkbox
                            id="sync_drive"
                            checked={syncToDrive}
                            onCheckedChange={(checked) => setSyncToDrive(!!checked)}
                        />
                        <Label htmlFor="sync_drive" className="text-sm cursor-pointer">
                            📤 Sync to Google Drive after research (for NotebookLM)
                        </Label>
                    </div>

                    {/* Submit */}
                    <Button
                        onClick={startResearch}
                        disabled={loading || !topic.trim()}
                        className="w-full h-14 text-lg rounded-xl bg-gradient-to-r from-blue-500 to-indigo-500 hover:from-blue-600 hover:to-indigo-600"
                    >
                        {loading ? "⟳ Starting..." : "🚀 Start Research"}
                    </Button>
                </CardContent>
            </Card>

            {error && (
                <div className="bg-red-950/30 border border-red-800/50 rounded-2xl p-6">
                    <p className="text-red-400">❌ Error: {error}</p>
                </div>
            )}

            {/* Current Job Status */}
            {currentJob && (
                <Card className="bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <span className="text-2xl">⚡</span>
                            Current Research
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="font-semibold text-lg">{currentJob.topic}</p>
                                <p className="text-sm text-zinc-500 font-mono">{currentJob.research_id}</p>
                            </div>
                            {getStatusBadge(currentJob.status)}
                        </div>

                        {/* Progress */}
                        <div className="grid grid-cols-4 gap-4 text-center">
                            <div className={`p-3 rounded-xl ${currentJob.status === "fetching" ? "bg-blue-500/20 ring-2 ring-blue-500" : "bg-zinc-800"}`}>
                                <p className="text-2xl">📥</p>
                                <p className="text-xs text-zinc-400 mt-1">Fetching</p>
                            </div>
                            <div className={`p-3 rounded-xl ${currentJob.status === "synthesizing" ? "bg-purple-500/20 ring-2 ring-purple-500" : "bg-zinc-800"}`}>
                                <p className="text-2xl">🧠</p>
                                <p className="text-xs text-zinc-400 mt-1">Synthesizing</p>
                            </div>
                            <div className={`p-3 rounded-xl ${currentJob.datamart && currentJob.status === "completed" ? "bg-green-500/20" : "bg-zinc-800"}`}>
                                <p className="text-2xl">📁</p>
                                <p className="text-xs text-zinc-400 mt-1">{currentJob.datamart || "Routing"}</p>
                            </div>
                            <div className={`p-3 rounded-xl ${currentJob.drive_synced ? "bg-green-500/20" : "bg-zinc-800"}`}>
                                <p className="text-2xl">{currentJob.drive_synced ? "✅" : "📤"}</p>
                                <p className="text-xs text-zinc-400 mt-1">Drive Sync</p>
                            </div>
                        </div>

                        {currentJob.evidence_count > 0 && (
                            <p className="text-sm text-zinc-400">
                                📊 Collected {currentJob.evidence_count} evidence items
                            </p>
                        )}

                        {currentJob.error && (
                            <div className="bg-red-950/30 border border-red-800/50 rounded-xl p-4">
                                <p className="text-red-400 text-sm">⚠️ {currentJob.error}</p>
                            </div>
                        )}

                        {currentJob.status === "completed" && (
                            <div className="bg-green-950/30 border border-green-800/50 rounded-xl p-4">
                                <p className="text-green-400">✅ Research complete! {currentJob.drive_synced ? "Synced to Drive." : ""}</p>
                                {currentJob.datamart && (
                                    <p className="text-sm text-zinc-400 mt-1">Routed to: <span className="text-blue-400">{currentJob.datamart}</span></p>
                                )}
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}

            {/* Recent Jobs */}
            {recentJobs.length > 0 && (
                <Card className="bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <span className="text-2xl">📋</span>
                            Recent Research Jobs
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-3">
                            {recentJobs.slice(0, 5).map((job) => (
                                <div key={job.research_id} className="flex items-center justify-between p-4 bg-zinc-800/50 rounded-xl">
                                    <div>
                                        <p className="font-medium">{job.topic}</p>
                                        <p className="text-xs text-zinc-500">{new Date(job.created_at).toLocaleString()}</p>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <span className="text-sm text-zinc-400">{job.evidence_count} items</span>
                                        {getStatusBadge(job.status)}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Empty State */}
            {!currentJob && recentJobs.length === 0 && (
                <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-12 text-center">
                    <div className="text-6xl mb-4">🔬</div>
                    <h3 className="text-xl font-semibold text-zinc-200">Start Your Research</h3>
                    <p className="text-zinc-500 mt-2 max-w-md mx-auto">
                        Enter a topic above to fetch from Google News and Reddit,
                        synthesize with AI, and route to your NotebookLM datamarts.
                    </p>
                </div>
            )}
        </div>
    );
}
