"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface Report {
    id: string;
    query: string;
    markdown: string;
    grounding_score: number;
    evidence_ids: string[];
    created_at: string;
}

export default function ResearchPage() {
    const [query, setQuery] = useState("");
    const [loading, setLoading] = useState(false);
    const [report, setReport] = useState<Report | null>(null);

    const runResearch = async () => {
        if (!query) return;
        setLoading(true);

        // TODO: Call API
        await new Promise((resolve) => setTimeout(resolve, 2000));

        setReport({
            id: Date.now().toString(),
            query,
            markdown: `# Research: ${query}\n\nThis is a placeholder report. Connect to the API to see real grounded research.\n\n## Key Findings\n\n- Finding 1 [EVID: ev_example1]\n- Finding 2 [EVID: ev_example2]\n\n## Conclusion\n\nMore research needed.`,
            grounding_score: 85,
            evidence_ids: ["ev_example1", "ev_example2"],
            created_at: new Date().toISOString(),
        });
        setLoading(false);
    };

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold">Research</h1>
                <p className="text-zinc-400 mt-1">Ask anything — get grounded answers with citations</p>
            </div>

            <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader>
                    <CardTitle>New Research Query</CardTitle>
                    <CardDescription>Your library will be cited as evidence</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                    <Textarea
                        placeholder="What would you like to research?"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        className="bg-zinc-800 border-zinc-700 min-h-[100px]"
                    />
                    <Button onClick={runResearch} disabled={loading || !query}>
                        {loading ? "Researching..." : "Run Research"}
                    </Button>
                </CardContent>
            </Card>

            {report && (
                <Card className="bg-zinc-900 border-zinc-800">
                    <CardHeader>
                        <div className="flex items-center justify-between">
                            <CardTitle>Report: {report.query}</CardTitle>
                            <GroundingBadge score={report.grounding_score} />
                        </div>
                        <CardDescription>
                            {report.evidence_ids.length} evidence sources • {new Date(report.created_at).toLocaleString()}
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="prose prose-invert prose-sm max-w-none">
                            <pre className="whitespace-pre-wrap text-sm bg-zinc-800 p-4 rounded-lg">
                                {report.markdown}
                            </pre>
                        </div>
                        <div className="flex gap-2 mt-4">
                            <Button variant="outline" size="sm">👍 Useful</Button>
                            <Button variant="outline" size="sm">👎 Not helpful</Button>
                            <Button variant="outline" size="sm">📌 Save</Button>
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}

function GroundingBadge({ score }: { score: number }) {
    const color =
        score >= 80 ? "bg-green-500/20 text-green-400" :
            score >= 50 ? "bg-yellow-500/20 text-yellow-400" :
                "bg-red-500/20 text-red-400";

    return (
        <span className={`px-2 py-1 rounded text-sm font-medium ${color}`}>
            Grounding: {score}%
        </span>
    );
}
