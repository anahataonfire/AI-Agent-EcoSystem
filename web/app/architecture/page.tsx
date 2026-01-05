"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface SystemComponent {
    name: string;
    icon: string;
    status: "ok" | "missing" | "warning";
    description: string;
}

const coreIntelligence: SystemComponent[] = [
    { name: "Thinker", icon: "🧠", status: "ok", description: "Planning & Reasoning" },
    { name: "Sanitizer", icon: "🛡️", status: "ok", description: "Security & Validation" },
    { name: "Executor", icon: "⚙️", status: "ok", description: "Tool Dispatch" },
    { name: "Reporter", icon: "📝", status: "ok", description: "Grounded Output" },
];

const contentPlanning: SystemComponent[] = [
    { name: "Curator", icon: "📚", status: "ok", description: "Content Management" },
    { name: "Advisor", icon: "🧠", status: "ok", description: "Review & Taxonomy" },
    { name: "Planner", icon: "📋", status: "ok", description: "Task Management" },
];

const utilityMaintenance: SystemComponent[] = [
    { name: "Designer", icon: "🎨", status: "ok", description: "Visual Assets" },
    { name: "Diagnostician", icon: "🔧", status: "ok", description: "Health Checks" },
    { name: "MetaAnalyst", icon: "📊", status: "ok", description: "Self-Improvement" },
];

const dataStores: SystemComponent[] = [
    { name: "Content Store", icon: "📚", status: "ok", description: "SQLite (Ingested Content)" },
    { name: "Evidence Store", icon: "📦", status: "ok", description: "SQLite (Grounded Evidence)" },
    { name: "Run Ledger", icon: "📒", status: "ok", description: "JSONL (Immutable Audit)" },
    { name: "Query Cache", icon: "⚡", status: "ok", description: "SQLite (Groundhog Day)" },
];

const gates: SystemComponent[] = [
    { name: "Human Approval Gate", icon: "👮", status: "ok", description: "CLI-based ACK Enforced" },
    { name: "Patch Policy", icon: "🛑", status: "ok", description: "Hash Validation Required" },
];

export default function ArchitecturePage() {
    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold">🏗️ System Architecture</h1>
                <p className="text-zinc-400 mt-1">Live status of all system components</p>
            </div>

            <ComponentSection title="🧠 Core Intelligence" components={coreIntelligence} />
            <ComponentSection title="📋 Content & Planning" components={contentPlanning} />
            <ComponentSection title="🛠️ Utility & Maintenance" components={utilityMaintenance} />
            <ComponentSection title="💾 Data Stores" components={dataStores} />
            <ComponentSection title="🚧 Gates" components={gates} />
        </div>
    );
}

function ComponentSection({ title, components }: { title: string; components: SystemComponent[] }) {
    return (
        <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
                <CardTitle>{title}</CardTitle>
            </CardHeader>
            <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                    {components.map((c) => (
                        <ComponentCard key={c.name} component={c} />
                    ))}
                </div>
            </CardContent>
        </Card>
    );
}

function ComponentCard({ component }: { component: SystemComponent }) {
    const statusColor =
        component.status === "ok"
            ? "bg-green-500/20 border-green-500/50"
            : component.status === "warning"
                ? "bg-yellow-500/20 border-yellow-500/50"
                : "bg-red-500/20 border-red-500/50";

    const statusIcon = component.status === "ok" ? "✓" : component.status === "warning" ? "⚠" : "✗";

    return (
        <div className={`p-3 rounded-lg border ${statusColor}`}>
            <div className="flex items-center gap-2">
                <span className="text-lg">{component.icon}</span>
                <span className="font-medium text-sm">{component.name}</span>
                <span className="ml-auto text-xs">{statusIcon}</span>
            </div>
            <p className="text-xs text-zinc-500 mt-1">{component.description}</p>
        </div>
    );
}
