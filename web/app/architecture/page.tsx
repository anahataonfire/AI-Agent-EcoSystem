"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface SystemComponent {
    name: string;
    icon: string;
    status: "ok" | "missing" | "warning" | "checking";
    description: string;
}

interface Section {
    title: string;
    icon: string;
    color: string;
    components: SystemComponent[];
}

const getInitialSections = (): Section[] => [
    {
        title: "Core Intelligence",
        icon: "🧠",
        color: "from-purple-500 to-blue-500",
        components: [
            { name: "Thinker", icon: "🧠", status: "checking", description: "Planning & Reasoning" },
            { name: "Sanitizer", icon: "🛡️", status: "checking", description: "Security & Validation" },
            { name: "Executor", icon: "⚙️", status: "checking", description: "Tool Dispatch" },
            { name: "Reporter", icon: "📝", status: "checking", description: "Grounded Output" },
        ],
    },
    {
        title: "Content & Planning",
        icon: "📋",
        color: "from-blue-500 to-cyan-500",
        components: [
            { name: "Curator", icon: "📚", status: "checking", description: "Content Management" },
            { name: "Advisor", icon: "🧠", status: "checking", description: "Review & Taxonomy" },
            { name: "Planner", icon: "📋", status: "checking", description: "Task Management" },
        ],
    },
    {
        title: "Utility & Maintenance",
        icon: "🛠️",
        color: "from-cyan-500 to-teal-500",
        components: [
            { name: "Designer", icon: "🎨", status: "checking", description: "Visual Assets" },
            { name: "Diagnostician", icon: "🔧", status: "checking", description: "Health Checks" },
            { name: "MetaAnalyst", icon: "📊", status: "checking", description: "Self-Improvement" },
        ],
    },
    {
        title: "Data Stores",
        icon: "💾",
        color: "from-teal-500 to-green-500",
        components: [
            { name: "Content Store", icon: "📚", status: "checking", description: "SQLite database" },
            { name: "Evidence Store", icon: "📦", status: "checking", description: "SQLite database" },
            { name: "Run Ledger", icon: "📒", status: "checking", description: "JSONL • Immutable" },
            { name: "Query Cache", icon: "⚡", status: "checking", description: "SQLite • Groundhog" },
        ],
    },
    {
        title: "Backend API",
        icon: "🔌",
        color: "from-green-500 to-emerald-500",
        components: [
            { name: "FastAPI (8000)", icon: "⚡", status: "checking", description: "Main backend" },
            { name: "Next.js API", icon: "◼️", status: "checking", description: "Frontend API" },
        ],
    },
];

export default function ArchitecturePage() {
    const [sections, setSections] = useState<Section[]>(getInitialSections());
    const [backendStatus, setBackendStatus] = useState<"checking" | "online" | "offline">("checking");

    useEffect(() => {
        checkHealth();
    }, []);

    const checkHealth = async () => {
        // Reset to checking state
        setSections(getInitialSections());
        setBackendStatus("checking");

        // Check FastAPI backend
        let apiOnline = false;
        try {
            const res = await fetch("http://localhost:8000/health/ping", {
                method: "GET",
                headers: { "X-API-Key": "dev-token-change-me" },
            });
            apiOnline = res.ok;
        } catch {
            apiOnline = false;
        }
        setBackendStatus(apiOnline ? "online" : "offline");

        // Update component statuses based on backend
        setSections(prev => prev.map(section => ({
            ...section,
            components: section.components.map(comp => {
                // Backend API components
                if (comp.name === "FastAPI (8000)") {
                    return { ...comp, status: apiOnline ? "ok" : "missing", description: apiOnline ? "Online • Port 8000" : "Offline • Port 8000" };
                }
                if (comp.name === "Next.js API") {
                    return { ...comp, status: "ok", description: "Online • Port 3000" };
                }
                // Core components - depend on backend for full functionality
                if (["Content Store", "Evidence Store"].includes(comp.name)) {
                    return { ...comp, status: apiOnline ? "ok" : "warning", description: apiOnline ? "Connected" : "Unreachable" };
                }
                // Static components (code always present)
                if (["Thinker", "Sanitizer", "Executor", "Reporter", "Curator", "Advisor", "Planner", "Designer", "Diagnostician", "MetaAnalyst", "Run Ledger", "Query Cache"].includes(comp.name)) {
                    return { ...comp, status: "ok" };
                }
                return comp;
            })
        })));
    };

    const totalComponents = sections.reduce((sum, s) => sum + s.components.length, 0);
    const activeComponents = sections.reduce(
        (sum, s) => sum + s.components.filter((c) => c.status === "ok").length,
        0
    );
    const warningComponents = sections.reduce(
        (sum, s) => sum + s.components.filter((c) => c.status === "warning").length,
        0
    );
    const missingComponents = sections.reduce(
        (sum, s) => sum + s.components.filter((c) => c.status === "missing").length,
        0
    );

    return (
        <div className="space-y-8">
            {/* Header */}
            <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-r from-slate-500/10 via-zinc-500/10 to-neutral-500/10 rounded-2xl blur-xl" />
                <div className="relative bg-zinc-900/80 backdrop-blur-sm border border-zinc-800 rounded-2xl p-6 flex items-center justify-between">
                    <div>
                        <h1 className="text-4xl font-bold bg-gradient-to-r from-slate-300 via-zinc-300 to-neutral-300 bg-clip-text text-transparent">
                            System Architecture
                        </h1>
                        <p className="text-zinc-400 mt-2">Live status of all system components</p>
                    </div>
                    <div className="flex items-center gap-6">
                        <div className="text-right">
                            <p className={`text-3xl font-bold ${missingComponents > 0 ? "text-red-400" : warningComponents > 0 ? "text-yellow-400" : "text-green-400"}`}>
                                {activeComponents}/{totalComponents}
                            </p>
                            <p className="text-sm text-zinc-500">
                                {backendStatus === "checking" ? "Checking..." :
                                    backendStatus === "online" ? "All Systems Go" :
                                        `${missingComponents} Offline`}
                            </p>
                        </div>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={checkHealth}
                            disabled={backendStatus === "checking"}
                            className="h-10 px-4 rounded-lg border-zinc-700"
                        >
                            {backendStatus === "checking" ? "⟳" : "↻ Refresh"}
                        </Button>
                    </div>
                </div>
            </div>

            {/* Architecture Grid */}
            <div className="space-y-6">
                {sections.map((section) => (
                    <Card key={section.title} className="bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl overflow-hidden">
                        <CardHeader className="border-b border-zinc-800 bg-zinc-900/50">
                            <CardTitle className={`flex items-center gap-3 text-lg bg-gradient-to-r ${section.color} bg-clip-text text-transparent`}>
                                <span className="text-2xl">{section.icon}</span>
                                {section.title}
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="p-4">
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                                {section.components.map((component) => (
                                    <ComponentCard key={component.name} component={component} color={section.color} />
                                ))}
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>

            {/* Neural Network Visualization */}
            <Card className="bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl overflow-hidden">
                <CardHeader className="border-b border-zinc-800">
                    <CardTitle className="flex items-center gap-2">
                        <span>🌐</span> System Flow
                    </CardTitle>
                </CardHeader>
                <CardContent className="p-8">
                    <div className="flex items-center justify-between text-center">
                        <FlowNode label="Input" icon="📥" color="from-blue-500 to-cyan-500" />
                        <FlowArrow />
                        <FlowNode label="Thinker" icon="🧠" color="from-purple-500 to-pink-500" />
                        <FlowArrow />
                        <FlowNode label="Executor" icon="⚙️" color="from-orange-500 to-red-500" />
                        <FlowArrow />
                        <FlowNode label="Reporter" icon="📝" color="from-green-500 to-emerald-500" />
                        <FlowArrow />
                        <FlowNode label="Output" icon="📤" color="from-teal-500 to-cyan-500" />
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}

function ComponentCard({ component, color }: { component: SystemComponent; color: string }) {
    const statusStyles: Record<string, string> = {
        ok: "border-green-500/30 bg-green-500/10",
        warning: "border-yellow-500/30 bg-yellow-500/10",
        missing: "border-red-500/30 bg-red-500/10",
        checking: "border-blue-500/30 bg-blue-500/10 animate-pulse",
    };

    const statusIcon: Record<string, string> = {
        ok: "✓",
        warning: "⚠",
        missing: "✗",
        checking: "⋯",
    };

    return (
        <div className={`p-4 rounded-xl border ${statusStyles[component.status]} transition-all hover:scale-105`}>
            <div className="flex items-center justify-between mb-2">
                <span className="text-2xl">{component.icon}</span>
                <span className={`text-xs ${component.status === "ok" ? "text-green-400" :
                        component.status === "warning" ? "text-yellow-400" :
                            component.status === "checking" ? "text-blue-400" :
                                "text-red-400"
                    }`}>
                    {statusIcon[component.status]}
                </span>
            </div>
            <h3 className="font-semibold text-zinc-200 text-sm">{component.name}</h3>
            <p className="text-xs text-zinc-500 mt-1">{component.description}</p>
        </div>
    );
}

function FlowNode({ label, icon, color }: { label: string; icon: string; color: string }) {
    return (
        <div className="flex flex-col items-center gap-2">
            <div className={`w-16 h-16 rounded-2xl bg-gradient-to-br ${color} flex items-center justify-center text-2xl shadow-lg`}>
                {icon}
            </div>
            <span className="text-xs text-zinc-400">{label}</span>
        </div>
    );
}

function FlowArrow() {
    return (
        <div className="flex-1 flex items-center justify-center px-2">
            <div className="h-px bg-gradient-to-r from-transparent via-zinc-600 to-transparent w-full" />
            <span className="text-zinc-600 -ml-1">→</span>
        </div>
    );
}
