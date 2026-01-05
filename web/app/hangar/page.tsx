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
        await new Promise((resolve) => setTimeout(resolve, 2000));

        setQaResults({
            total: 12,
            passed: 11,
            failed: 1,
            errors: 0,
            results: [
                { test_id: "grounding_001", status: "PASS", input: "Citation format" },
                { test_id: "grounding_002", status: "PASS", input: "Evidence ID exists" },
                { test_id: "grounding_003", status: "PASS", input: "No fabrication" },
                { test_id: "sanitizer_001", status: "PASS", input: "Block malicious URL" },
                { test_id: "sanitizer_002", status: "PASS", input: "XSS prevention" },
                { test_id: "sanitizer_003", status: "FAIL", input: "Injection edge case", expected: "Block", actual: "Pass" },
                { test_id: "pipeline_001", status: "PASS", input: "Full RSS flow" },
                { test_id: "pipeline_002", status: "PASS", input: "Error recovery" },
                { test_id: "cache_001", status: "PASS", input: "Query dedup" },
                { test_id: "evidence_001", status: "PASS", input: "Store write" },
                { test_id: "evidence_002", status: "PASS", input: "Lifecycle transition" },
                { test_id: "identity_001", status: "PASS", input: "Provenance footer" },
            ],
        });
        setLoading(false);
    };

    const skillFiles = [
        { name: "Grounding", icon: "🎯", file: "skill_grounding.md" },
        { name: "Sanitizer", icon: "🛡️", file: "skill_sanitizer.md" },
        { name: "Thinker", icon: "🧠", file: "skill_thinker.md" },
        { name: "Reporter", icon: "📝", file: "skill_reporter.md" },
        { name: "Identity", icon: "🆔", file: "skill_identity_usage.md" },
    ];

    return (
        <div className="space-y-8">
            {/* Header */}
            <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-r from-red-500/10 via-orange-500/10 to-yellow-500/10 rounded-2xl blur-xl" />
                <div className="relative bg-zinc-900/80 backdrop-blur-sm border border-zinc-800 rounded-2xl p-6">
                    <h1 className="text-4xl font-bold bg-gradient-to-r from-red-400 via-orange-400 to-yellow-400 bg-clip-text text-transparent">
                        The Hangar
                    </h1>
                    <p className="text-zinc-400 mt-2">Regression testing and skill configuration</p>
                </div>
            </div>

            {/* Regression Suite */}
            <Card className="bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <span className="text-2xl">🧪</span>
                        Regression Suite
                    </CardTitle>
                    <CardDescription>Run the full test suite to validate system integrity</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    <Button
                        onClick={runRegression}
                        disabled={loading}
                        className="w-full h-14 text-lg rounded-xl bg-gradient-to-r from-red-500 to-orange-500 hover:from-red-600 hover:to-orange-600"
                    >
                        {loading ? "⟳ Running tests..." : "▶️ Run Full Suite"}
                    </Button>

                    {qaResults && (
                        <>
                            {/* Stats */}
                            <div className="grid grid-cols-4 gap-4">
                                <StatCard label="Total" value={qaResults.total} color="text-zinc-300" bg="bg-zinc-800" />
                                <StatCard label="Passed" value={qaResults.passed} color="text-green-400" bg="bg-green-500/10 border-green-500/30" />
                                <StatCard label="Failed" value={qaResults.failed} color="text-red-400" bg="bg-red-500/10 border-red-500/30" />
                                <StatCard label="Errors" value={qaResults.errors} color="text-yellow-400" bg="bg-yellow-500/10 border-yellow-500/30" />
                            </div>

                            {/* Progress Bar */}
                            <div className="relative h-3 bg-zinc-800 rounded-full overflow-hidden">
                                <div
                                    className="absolute inset-y-0 left-0 bg-gradient-to-r from-green-500 to-emerald-500 rounded-full transition-all"
                                    style={{ width: `${(qaResults.passed / qaResults.total) * 100}%` }}
                                />
                            </div>

                            {/* Test Results */}
                            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                                {qaResults.results.map((r) => (
                                    <TestResultCard key={r.test_id} result={r} />
                                ))}
                            </div>
                        </>
                    )}
                </CardContent>
            </Card>

            {/* Skill Sandbox */}
            <Card className="bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <span className="text-2xl">📝</span>
                        Skill Sandbox
                    </CardTitle>
                    <CardDescription>Inspect agent skill manifests</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="flex flex-wrap gap-3">
                        {skillFiles.map((skill) => (
                            <Button
                                key={skill.file}
                                variant={selectedSkill === skill.file ? "default" : "outline"}
                                onClick={() => setSelectedSkill(selectedSkill === skill.file ? null : skill.file)}
                                className={`rounded-xl ${selectedSkill === skill.file
                                        ? "bg-gradient-to-r from-red-500 to-orange-500"
                                        : "border-zinc-700 hover:border-orange-500/50"
                                    }`}
                            >
                                <span className="mr-2">{skill.icon}</span>
                                {skill.name}
                            </Button>
                        ))}
                    </div>

                    {selectedSkill && (
                        <div className="mt-6 bg-zinc-800/50 p-6 rounded-xl border border-zinc-700">
                            <p className="text-sm text-zinc-400 mb-3">📄 {selectedSkill}</p>
                            <pre className="text-sm whitespace-pre-wrap text-zinc-300 font-mono leading-relaxed">
                                {`# ${selectedSkill.replace("skill_", "").replace(".md", "").toUpperCase()} Skill

## Capabilities
- Validate inputs against schema
- Enforce grounding requirements  
- Track citation integrity
- Maintain evidence chain

## Constraints
- No fabricated evidence
- Must cite sources
- Respect rate limits
- Log all decisions

(Connect to API for live content)`}
                            </pre>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}

function StatCard({ label, value, color, bg }: { label: string; value: number; color: string; bg: string }) {
    return (
        <div className={`p-4 rounded-xl border ${bg}`}>
            <p className={`text-3xl font-bold ${color}`}>{value}</p>
            <p className="text-sm text-zinc-500">{label}</p>
        </div>
    );
}

function TestResultCard({ result }: { result: TestResult }) {
    const statusConfig = {
        PASS: { icon: "✓", bg: "bg-green-500/10 border-green-500/30", text: "text-green-400" },
        FAIL: { icon: "✗", bg: "bg-red-500/10 border-red-500/30", text: "text-red-400" },
        ERROR: { icon: "⚠", bg: "bg-yellow-500/10 border-yellow-500/30", text: "text-yellow-400" },
    };

    const config = statusConfig[result.status];

    return (
        <div className={`p-3 rounded-xl border ${config.bg} transition-all hover:scale-105`}>
            <div className="flex items-center gap-2 mb-1">
                <span className={`${config.text}`}>{config.icon}</span>
                <span className="text-xs font-mono text-zinc-400">{result.test_id}</span>
            </div>
            <p className="text-xs text-zinc-500 truncate">{result.input}</p>
        </div>
    );
}
