"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
    DialogFooter,
    DialogClose,
} from "@/components/ui/dialog";

interface ContentItem {
    id: string;
    title: string;
    summary: string;
    source_url?: string;
    categories: string[];
    action_items: string[];
    created_at: string;
}

interface EvidenceItem {
    evidence_id: string;
    payload: Record<string, any>;
    metadata: Record<string, any>;
    created_at: string;
    lifecycle: string;
}

const CATEGORY_OPTIONS = [
    "AI/ML", "Trading", "Research", "Learning", "Baking", "Fitness",
    "Productivity", "Development", "News", "Reference", "To Review"
];

export default function LibraryPage() {
    const [activeTab, setActiveTab] = useState("content");
    const [search, setSearch] = useState("");
    const [contentItems, setContentItems] = useState<ContentItem[]>([]);
    const [evidenceItems, setEvidenceItems] = useState<EvidenceItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchContent = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch("http://localhost:8000/content/browse?limit=50", {
                headers: { "X-API-Key": "dev-token-change-me" },
            });
            if (!res.ok) throw new Error(`API error: ${res.status}`);
            const data = await res.json();
            setContentItems(data);
        } catch (e: any) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    const fetchEvidence = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch("http://localhost:8000/evidence/browse?limit=50", {
                headers: { "X-API-Key": "dev-token-change-me" },
            });
            if (!res.ok) throw new Error(`API error: ${res.status}`);
            const data = await res.json();
            setEvidenceItems(data);
        } catch (e: any) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchContent();
        fetchEvidence();
    }, []);

    const filteredContent = search
        ? contentItems.filter((item) =>
            item.title.toLowerCase().includes(search.toLowerCase()) ||
            item.summary.toLowerCase().includes(search.toLowerCase())
        )
        : contentItems;

    const filteredEvidence = search
        ? evidenceItems.filter((item) => {
            const title = item.payload?.title || "";
            const summary = item.payload?.summary || "";
            return (
                title.toLowerCase().includes(search.toLowerCase()) ||
                summary.toLowerCase().includes(search.toLowerCase())
            );
        })
        : evidenceItems;

    return (
        <div className="space-y-8">
            {/* Header */}
            <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-r from-purple-500/10 via-blue-500/10 to-cyan-500/10 rounded-2xl blur-xl" />
                <div className="relative bg-zinc-900/80 backdrop-blur-sm border border-zinc-800 rounded-2xl p-6">
                    <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-400 via-blue-400 to-cyan-400 bg-clip-text text-transparent">
                        Content Library
                    </h1>
                    <p className="text-zinc-400 mt-2">Your curated knowledge and research evidence</p>

                    <div className="flex gap-4 mt-6">
                        <div className="relative flex-1 max-w-md">
                            <Input
                                placeholder="Search your library..."
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                                className="bg-zinc-800/50 border-zinc-700 pl-10 h-12 rounded-xl"
                            />
                            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500">🔍</span>
                        </div>
                        <Button
                            variant="outline"
                            onClick={() => { fetchContent(); fetchEvidence(); }}
                            disabled={loading}
                            className="h-12 px-6 rounded-xl border-zinc-700 hover:bg-zinc-800"
                        >
                            {loading ? "⟳ Loading..." : "↻ Refresh"}
                        </Button>
                    </div>
                </div>
            </div>

            {error && (
                <div className="bg-red-950/30 border border-red-800/50 rounded-xl p-4">
                    <p className="text-red-400">⚠️ {error}</p>
                </div>
            )}

            <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList className="bg-zinc-800/50 p-1 rounded-xl border border-zinc-700">
                    <TabsTrigger
                        value="content"
                        className="data-[state=active]:bg-gradient-to-r data-[state=active]:from-purple-500 data-[state=active]:to-blue-500 rounded-lg px-6 py-2"
                    >
                        📎 Curated Links ({contentItems.length})
                    </TabsTrigger>
                    <TabsTrigger
                        value="evidence"
                        className="data-[state=active]:bg-gradient-to-r data-[state=active]:from-blue-500 data-[state=active]:to-cyan-500 rounded-lg px-6 py-2"
                    >
                        📦 Evidence ({evidenceItems.length})
                    </TabsTrigger>
                </TabsList>

                <TabsContent value="content" className="mt-6">
                    {filteredContent.length === 0 ? (
                        <EmptyState
                            icon="📎"
                            title="No curated links yet"
                            description="Add links via the Inbox to start your collection."
                        />
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                            {filteredContent.map((item) => (
                                <InteractiveContentCard key={item.id} item={item} onUpdate={fetchContent} />
                            ))}
                        </div>
                    )}
                </TabsContent>

                <TabsContent value="evidence" className="mt-6">
                    {filteredEvidence.length === 0 ? (
                        <EmptyState
                            icon="📦"
                            title="No evidence collected"
                            description="Run a mission to collect research evidence."
                        />
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                            {filteredEvidence.map((item) => (
                                <EvidenceCard key={item.evidence_id} item={item} />
                            ))}
                        </div>
                    )}
                </TabsContent>
            </Tabs>
        </div>
    );
}

function EmptyState({ icon, title, description }: { icon: string; title: string; description: string }) {
    return (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-12 text-center">
            <div className="text-6xl mb-4">{icon}</div>
            <h3 className="text-xl font-semibold text-zinc-200">{title}</h3>
            <p className="text-zinc-500 mt-2 max-w-md mx-auto">{description}</p>
        </div>
    );
}

function InteractiveContentCard({ item, onUpdate }: { item: ContentItem; onUpdate: () => void }) {
    const [showCategoryDialog, setShowCategoryDialog] = useState(false);
    const [selectedCategories, setSelectedCategories] = useState<string[]>(item.categories);
    const [addingToPlanner, setAddingToPlanner] = useState(false);

    const handleCategorize = async () => {
        // TODO: Call API to update categories
        console.log("Updating categories:", selectedCategories);
        setShowCategoryDialog(false);
        onUpdate();
    };

    const [plannerMessage, setPlannerMessage] = useState<string | null>(null);

    const handleAddToPlanner = async () => {
        setAddingToPlanner(true);
        setPlannerMessage(null);
        try {
            const res = await fetch("http://localhost:8000/planner/task?title=" + encodeURIComponent(`Review: ${item.title}`), {
                method: "POST",
                headers: { "X-API-Key": "dev-token-change-me" },
            });
            if (res.ok) {
                setPlannerMessage("✓ Added to planner!");
                setTimeout(() => setPlannerMessage(null), 3000);
            } else {
                setPlannerMessage("✗ Failed to add");
            }
        } catch (e) {
            console.error("Failed to add to planner:", e);
            setPlannerMessage("✗ Error adding to planner");
        } finally {
            setAddingToPlanner(false);
        }
    };

    return (
        <div className="group relative">
            <div className="absolute inset-0 bg-gradient-to-r from-purple-500/20 to-blue-500/20 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity blur-xl" />
            <Card className="relative bg-zinc-900/80 backdrop-blur-sm border-zinc-800 hover:border-zinc-600 transition-all rounded-2xl overflow-hidden">
                <CardHeader className="pb-3">
                    <CardTitle className="text-lg font-semibold line-clamp-2 text-zinc-100">
                        {item.title}
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <CardDescription className="line-clamp-3 text-zinc-400">
                        {item.summary}
                    </CardDescription>

                    {/* Categories */}
                    <div className="flex flex-wrap gap-1.5">
                        {item.categories.map((cat) => (
                            <span
                                key={cat}
                                className="text-xs bg-gradient-to-r from-purple-500/20 to-blue-500/20 text-purple-300 px-2.5 py-1 rounded-full border border-purple-500/30"
                            >
                                {cat}
                            </span>
                        ))}
                    </div>

                    {/* Source Link */}
                    {item.source_url && (
                        <a
                            href={item.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-sm text-blue-400 hover:text-blue-300 transition-colors"
                        >
                            <span>🔗</span>
                            <span className="hover:underline">{new URL(item.source_url).hostname}</span>
                        </a>
                    )}

                    {/* Action Buttons */}
                    <div className="flex gap-2 pt-2 border-t border-zinc-800">
                        <Dialog open={showCategoryDialog} onOpenChange={setShowCategoryDialog}>
                            <DialogTrigger asChild>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="flex-1 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800"
                                >
                                    🏷️ Categorize
                                </Button>
                            </DialogTrigger>
                            <DialogContent className="bg-zinc-900 border-zinc-800">
                                <DialogHeader>
                                    <DialogTitle>Categorize Content</DialogTitle>
                                    <DialogDescription>Select categories for this content</DialogDescription>
                                </DialogHeader>
                                <div className="grid grid-cols-2 gap-2 py-4">
                                    {CATEGORY_OPTIONS.map((cat) => (
                                        <Button
                                            key={cat}
                                            variant={selectedCategories.includes(cat) ? "default" : "outline"}
                                            size="sm"
                                            onClick={() => {
                                                setSelectedCategories((prev) =>
                                                    prev.includes(cat)
                                                        ? prev.filter((c) => c !== cat)
                                                        : [...prev, cat]
                                                );
                                            }}
                                            className={selectedCategories.includes(cat)
                                                ? "bg-gradient-to-r from-purple-500 to-blue-500"
                                                : "border-zinc-700"
                                            }
                                        >
                                            {cat}
                                        </Button>
                                    ))}
                                </div>
                                <DialogFooter>
                                    <DialogClose asChild>
                                        <Button variant="ghost">Cancel</Button>
                                    </DialogClose>
                                    <Button onClick={handleCategorize} className="bg-gradient-to-r from-purple-500 to-blue-500">
                                        Save Categories
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>

                        <Button
                            variant="ghost"
                            size="sm"
                            className={`flex-1 transition-all ${plannerMessage?.includes("✓")
                                    ? "text-green-400 bg-green-500/10"
                                    : plannerMessage?.includes("✗")
                                        ? "text-red-400 bg-red-500/10"
                                        : "text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800"
                                }`}
                            onClick={handleAddToPlanner}
                            disabled={addingToPlanner}
                        >
                            {plannerMessage || (addingToPlanner ? "⟳ Adding..." : "📋 Add to Planner")}
                        </Button>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}

function EvidenceCard({ item }: { item: EvidenceItem }) {
    const title = item.payload?.title || item.evidence_id;
    const summary = item.payload?.summary || item.payload?.content || "";
    const source = item.metadata?.source_url || item.payload?.link;

    return (
        <div className="group relative">
            <div className="absolute inset-0 bg-gradient-to-r from-blue-500/20 to-cyan-500/20 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity blur-xl" />
            <Card className="relative bg-zinc-900/80 backdrop-blur-sm border-zinc-800 hover:border-zinc-600 transition-all rounded-2xl overflow-hidden">
                <CardHeader className="pb-3">
                    <div className="flex items-start justify-between gap-2">
                        <CardTitle className="text-lg font-semibold line-clamp-2 text-zinc-100">
                            {title}
                        </CardTitle>
                        <span className={`shrink-0 text-xs px-2.5 py-1 rounded-full ${item.lifecycle === "active"
                            ? "bg-green-500/20 text-green-400 border border-green-500/30"
                            : "bg-zinc-700 text-zinc-400"
                            }`}>
                            {item.lifecycle}
                        </span>
                    </div>
                </CardHeader>
                <CardContent>
                    <CardDescription className="line-clamp-3 text-zinc-400">
                        {summary}
                    </CardDescription>
                    {source && (
                        <a
                            href={source}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-sm text-cyan-400 hover:text-cyan-300 transition-colors mt-4"
                        >
                            <span>🔗</span>
                            <span className="hover:underline">View source</span>
                        </a>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
