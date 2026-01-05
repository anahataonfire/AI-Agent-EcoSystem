"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface TestResult {
    test_id: string;
    status: "PASS" | "FAIL" | "ERROR";
    input?: string;
    actual?: string;
    expected?: string;
    error?: string;
}

interface QAResults {
    total: number;
    passed: number;
    failed: number;
    errors: number;
    results: TestResult[];
}

export default function HangarPage() {
    const [loading, setLoading] = useState(false);
    const [qaResults, setQaResults] = useState<QAResults | null>(null);
    const [selectedSkill, setSelectedSkill] = useState<string | null>(null);

    const runRegression = async () => {
        setLoading(true);
        // Simulate regression run (would call API in real implementation)
        await new Promise((resolve) => setTimeout(resolve, 2000));

        setQaResults({
            total: 12,
            passed: 10,
            failed: 1,
            errors: 1,
            results: [
                { test_id: "grounding_001", status: "PASS", input: "Test citation format" },
                { test_id: "grounding_002", status: "PASS", input: "Evidence ID exists" },
                { test_id: "sanitizer_001", status: "PASS", input: "Block malicious URL" },
                { test_id: "sanitizer_002", status: "FAIL", input: "Injection attempt", expected: "Block", actual: "Pass" },
                { test_id: "pipeline_001", status: "PASS", input: "Full RSS flow" },
                { test_id: "pipeline_002", status: "ERROR", input: "Timeout test", error: "Connection timeout" },
            ],
        });
        setLoading(false);
    };

    const skillFiles = [
        "skill_grounding.md",
        "skill_sanitizer.md",
        "skill_thinker.md",
        "skill_reporter.md",
        "skill_identity_usage.md",
    ];

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold">🛠️ The Hangar</h1>
                <p className="text-zinc-400 mt-1">Regression testing and skill configuration</p>
            </div>

            {/* Regression Suite */}
            <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader>
                    <CardTitle>🧪 Regression Suite</CardTitle>
                    <CardDescription>Run the full test suite to validate system integrity</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <Button onClick={runRegression} disabled={loading}>
                        {loading ? "Running tests..." : "▶️ Run Full Suite"}
                    </Button>

                    {qaResults && (
                        <div className="space-y-4">
                            <div className="grid grid-cols-4 gap-4">
                                <MetricCard label="Total Tests" value={qaResults.total} />
                                <MetricCard label="Passed" value={qaResults.passed} color="text-green-400" />
                                <MetricCard label="Failed" value={qaResults.failed} color="text-red-400" />
                                <MetricCard label="Errors" value={qaResults.errors} color="text-yellow-400" />
                            </div>

                            <div className="space-y-2">
                                {qaResults.results.map((r) => (
                                    <TestResultCard key={r.test_id} result={r} />
                                ))}
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Skill Sandbox */}
            <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader>
                    <CardTitle>📝 Skill Sandbox</CardTitle>
                    <CardDescription>Inspect agent skill manifests</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex flex-wrap gap-2">
                        {skillFiles.map((skill) => (
                            <Button
                                key={skill}
                                variant={selectedSkill === skill ? "default" : "outline"}
                                size="sm"
                                onClick={() => setSelectedSkill(skill)}
                            >
                                {skill.replace("skill_", "").replace(".md", "")}
                            </Button>
                        ))}
                    </div>

                    {selectedSkill && (
                        <div className="bg-zinc-800 p-4 rounded-lg border border-zinc-700">
                            <p className="text-sm text-zinc-400 mb-2">📄 {selectedSkill}</p>
                            <pre className="text-sm whitespace-pre-wrap text-zinc-300">
                                {`# ${selectedSkill.replace("skill_", "").replace(".md", "").toUpperCase()} Skill

## Capabilities
- Validate inputs against schema
- Enforce grounding requirements
- Track citation integrity

## Constraints
- No fabricated evidence
- Must cite sources
- Respect rate limits

(This is a placeholder - connect to API for real content)`}
                            </pre>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}

function MetricCard({ label, value, color }: { label: string; value: number; color?: string }) {
    return (
        <div className="bg-zinc-800 p-3 rounded-lg">
            <p className="text-xs text-zinc-500">{label}</p>
            <p className={`text-2xl font-bold ${color || ""}`}>{value}</p>
        </div>
    );
}

function TestResultCard({ result }: { result: TestResult }) {
    const [expanded, setExpanded] = useState(false);
    const icon = result.status === "PASS" ? "✅" : result.status === "FAIL" ? "❌" : "⚠️";
    const color = result.status === "PASS" ? "text-green-400" : result.status === "FAIL" ? "text-red-400" : "text-yellow-400";

    return (
        <div className="bg-zinc-800 rounded-lg border border-zinc-700">
            <button
                onClick={() => setExpanded(!expanded)}
                className="w-full p-3 text-left flex items-center justify-between hover:bg-zinc-700/50 transition-colors"
            >
                <span>
                    {icon} <strong className={color}>{result.test_id}</strong>
                </span>
                <span className="text-zinc-500">{expanded ? "▼" : "▶"}</span>
            </button>
            {expanded && (
                <div className="p-3 border-t border-zinc-700 space-y-2 text-sm">
                    {result.input && <p><span className="text-zinc-500">Input:</span> {result.input}</p>}
                    {result.expected && <p><span className="text-zinc-500">Expected:</span> {result.expected}</p>}
                    {result.actual && <p><span className="text-zinc-500">Actual:</span> {result.actual}</p>}
                    {result.error && <p className="text-red-400">Error: {result.error}</p>}
                </div>
            )}
        </div>
    );
}
