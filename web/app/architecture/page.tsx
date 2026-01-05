"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface SystemComponent {
    name: string;
    icon: string;
    status: "ok" | "missing" | "warning";
    description: string;
}

const sections = [
    {
        title: "Core Intelligence",
        icon: "🧠",
        color: "from-purple-500 to-blue-500",
        components: [
            { name: "Thinker", icon: "🧠", status: "ok" as const, description: "Planning & Reasoning" },
            { name: "Sanitizer", icon: "🛡️", status: "ok" as const, description: "Security & Validation" },
            { name: "Executor", icon: "⚙️", status: "ok" as const, description: "Tool Dispatch" },
            { name: "Reporter", icon: "📝", status: "ok" as const, description: "Grounded Output" },
        ],
    },
    {
        title: "Content & Planning",
        icon: "📋",
        color: "from-blue-500 to-cyan-500",
        components: [
            { name: "Curator", icon: "📚", status: "ok" as const, description: "Content Management" },
            { name: "Advisor", icon: "🧠", status: "ok" as const, description: "Review & Taxonomy" },
            { name: "Planner", icon: "📋", status: "ok" as const, description: "Task Management" },
        ],
    },
    {
        title: "Utility & Maintenance",
        icon: "🛠️",
        color: "from-cyan-500 to-teal-500",
        components: [
            { name: "Designer", icon: "🎨", status: "ok" as const, description: "Visual Assets" },
            { name: "Diagnostician", icon: "🔧", status: "ok" as const, description: "Health Checks" },
            { name: "MetaAnalyst", icon: "📊", status: "ok" as const, description: "Self-Improvement" },
        ],
    },
    {
        title: "Data Stores",
        icon: "💾",
        color: "from-teal-500 to-green-500",
        components: [
            { name: "Content Store", icon: "📚", status: "ok" as const, description: "SQLite • 32 entries" },
            { name: "Evidence Store", icon: "📦", status: "ok" as const, description: "SQLite • 242 items" },
            { name: "Run Ledger", icon: "📒", status: "ok" as const, description: "JSONL • Immutable" },
            { name: "Query Cache", icon: "⚡", status: "ok" as const, description: "SQLite • Groundhog" },
        ],
    },
    {
        title: "Security Gates",
        icon: "🔒",
        color: "from-green-500 to-emerald-500",
        components: [
            { name: "Human Approval", icon: "👮", status: "ok" as const, description: "CLI-based ACK" },
            { name: "Patch Policy", icon: "🛑", status: "ok" as const, description: "Hash Validation" },
        ],
    },
];

export default function ArchitecturePage() {
    const totalComponents = sections.reduce((sum, s) => sum + s.components.length, 0);
    const activeComponents = sections.reduce(
        (sum, s) => sum + s.components.filter((c) => c.status === "ok").length,
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
                    <div className="text-right">
                        <p className="text-3xl font-bold text-green-400">
                            {activeComponents}/{totalComponents}
                        </p>
                        <p className="text-sm text-zinc-500">Components Online</p>
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
    const statusStyles = {
        ok: "border-green-500/30 bg-green-500/10",
        warning: "border-yellow-500/30 bg-yellow-500/10",
        missing: "border-red-500/30 bg-red-500/10",
    };

    const statusIcon = {
        ok: "✓",
        warning: "⚠",
        missing: "✗",
    };

    return (
        <div className={`p-4 rounded-xl border ${statusStyles[component.status]} transition-all hover:scale-105`}>
            <div className="flex items-center justify-between mb-2">
                <span className="text-2xl">{component.icon}</span>
                <span className={`text-xs ${component.status === "ok" ? "text-green-400" :
                        component.status === "warning" ? "text-yellow-400" : "text-red-400"
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
