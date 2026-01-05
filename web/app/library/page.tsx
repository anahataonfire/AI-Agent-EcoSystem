"use client";

import { useState, useEffect, useMemo } from "react";
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
    planner_status?: string | null;  // 'queued' | 'in_progress' | 'done' | null
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
    "Productivity", "Development", "News", "Reference"
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
            const res = await fetch("http://localhost:8000/content/browse?limit=100", {
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
        try {
            const res = await fetch("http://localhost:8000/evidence/browse?limit=50", {
                headers: { "X-API-Key": "dev-token-change-me" },
            });
            if (!res.ok) throw new Error(`API error: ${res.status}`);
            const data = await res.json();
            setEvidenceItems(data);
        } catch (e: any) {
            // Silently fail for evidence
        }
    };

    useEffect(() => {
        fetchContent();
        fetchEvidence();
    }, []);

    const handleDelete = async (id: string) => {
        try {
            const res = await fetch(`http://localhost:8000/content/${id}`, {
                method: "DELETE",
                headers: { "X-API-Key": "dev-token-change-me" },
            });
            if (res.ok) {
                setContentItems((prev) => prev.filter((item) => item.id !== id));
            }
        } catch (e) {
            console.error("Delete error:", e);
        }
    };

    const handleCategorize = async (id: string, categories: string[]) => {
        try {
            const res = await fetch(`http://localhost:8000/content/${id}/categories`, {
                method: "PATCH",
                headers: {
                    "X-API-Key": "dev-token-change-me",
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(categories),
            });
            if (res.ok) {
                // Update local state
                setContentItems((prev) =>
                    prev.map((item) =>
                        item.id === id ? { ...item, categories } : item
                    )
                );
            }
        } catch (e) {
            console.error("Categorize error:", e);
        }
    };

    const filtered = useMemo(() => {
        const items = search
            ? contentItems.filter((item) =>
                item.title.toLowerCase().includes(search.toLowerCase()) ||
                item.summary.toLowerCase().includes(search.toLowerCase())
            )
            : contentItems;

        // Treat items with no categories OR only 'uncategorized' as needing triage
        const isUncategorized = (c: ContentItem) =>
            c.categories.length === 0 ||
            (c.categories.length === 1 && c.categories[0].toLowerCase() === "uncategorized");

        return {
            uncategorized: items.filter(isUncategorized),
            categorized: items.filter((c) => !isUncategorized(c)),
        };
    }, [contentItems, search]);

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
        <div className="space-y-6">
            {/* Header */}
            <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-r from-purple-500/10 via-blue-500/10 to-cyan-500/10 rounded-2xl blur-xl" />
                <div className="relative bg-zinc-900/80 backdrop-blur-sm border border-zinc-800 rounded-2xl p-6">
                    <div className="flex items-center justify-between">
                        <div>
                            <h1 className="text-3xl font-bold bg-gradient-to-r from-purple-400 via-blue-400 to-cyan-400 bg-clip-text text-transparent">
                                Content Library
                            </h1>
                            <p className="text-zinc-500 text-sm mt-1">
                                {filtered.uncategorized.length} items need triage • {filtered.categorized.length} organized
                            </p>
                        </div>
                        <div className="flex gap-3">
                            <Input
                                placeholder="Search..."
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                                className="w-48 bg-zinc-800/50 border-zinc-700 h-10 rounded-lg"
                            />
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => { fetchContent(); fetchEvidence(); }}
                                disabled={loading}
                                className="h-10 px-4 rounded-lg border-zinc-700"
                            >
                                {loading ? "⟳" : "↻"}
                            </Button>
                        </div>
                    </div>
                </div>
            </div>

            {error && (
                <div className="bg-red-950/30 border border-red-800/50 rounded-xl p-3 text-sm">
                    <p className="text-red-400">⚠️ {error}</p>
                </div>
            )}

            <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList className="bg-zinc-800/50 p-1 rounded-lg border border-zinc-700">
                    <TabsTrigger
                        value="content"
                        className="data-[state=active]:bg-gradient-to-r data-[state=active]:from-purple-500 data-[state=active]:to-blue-500 rounded-md px-4 py-1.5 text-sm"
                    >
                        📎 Links ({contentItems.length})
                    </TabsTrigger>
                    <TabsTrigger
                        value="evidence"
                        className="data-[state=active]:bg-gradient-to-r data-[state=active]:from-blue-500 data-[state=active]:to-cyan-500 rounded-md px-4 py-1.5 text-sm"
                    >
                        📦 Evidence ({evidenceItems.length})
                    </TabsTrigger>
                </TabsList>

                <TabsContent value="content" className="mt-4 space-y-6">
                    {/* TRIAGE SECTION - Uncategorized */}
                    {filtered.uncategorized.length > 0 && (
                        <section>
                            <div className="flex items-center gap-3 mb-3">
                                <div className="flex items-center gap-2">
                                    <span className="text-lg">📥</span>
                                    <h2 className="text-lg font-semibold text-amber-400">Needs Triage</h2>
                                </div>
                                <span className="text-xs bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded-full">
                                    {filtered.uncategorized.length} items
                                </span>
                            </div>
                            <div className="bg-amber-500/5 border border-amber-500/20 rounded-xl p-4">
                                <div className="space-y-2">
                                    {filtered.uncategorized.map((item) => (
                                        <TriageCard
                                            key={item.id}
                                            item={item}
                                            onCategorize={(cats) => handleCategorize(item.id, cats)}
                                            onDelete={() => handleDelete(item.id)}
                                        />
                                    ))}
                                </div>
                            </div>
                        </section>
                    )}

                    {/* ORGANIZED SECTION - Categorized */}
                    <section>
                        <div className="flex items-center gap-3 mb-3">
                            <div className="flex items-center gap-2">
                                <span className="text-lg">📚</span>
                                <h2 className="text-lg font-semibold text-purple-400">Organized</h2>
                            </div>
                            <span className="text-xs bg-purple-500/20 text-purple-300 px-2 py-0.5 rounded-full">
                                {filtered.categorized.length} items
                            </span>
                        </div>
                        {filtered.categorized.length === 0 ? (
                            <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-8 text-center">
                                <p className="text-zinc-500">No organized content yet. Categorize items above.</p>
                            </div>
                        ) : (
                            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                                {filtered.categorized.map((item) => (
                                    <OrganizedCard
                                        key={item.id}
                                        item={item}
                                        onCategorize={(cats) => handleCategorize(item.id, cats)}
                                        onDelete={() => handleDelete(item.id)}
                                    />
                                ))}
                            </div>
                        )}
                    </section>
                </TabsContent>

                <TabsContent value="evidence" className="mt-4">
                    {filteredEvidence.length === 0 ? (
                        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-8 text-center">
                            <div className="text-4xl mb-3">📦</div>
                            <p className="text-zinc-500">No evidence yet. Run a mission to collect research.</p>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
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

// Triage card - horizontal, compact, focus on quick categorization
function TriageCard({
    item,
    onCategorize,
    onDelete,
}: {
    item: ContentItem;
    onCategorize: (categories: string[]) => void;
    onDelete: () => void;
}) {
    const [showCategories, setShowCategories] = useState(false);
    const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
    const [autoSuggesting, setAutoSuggesting] = useState(false);
    const [suggestedCategories, setSuggestedCategories] = useState<string[] | null>(null);

    const cleanSummary = item.summary
        .replace(/Fallback analysis:.*$/gm, "")
        .replace(/400 INVALID_ARGUMENT.*$/gm, "")
        .trim();

    const handleQuickCategorize = (cat: string) => {
        onCategorize([cat]);
    };

    const handleAutoCategorize = async () => {
        setAutoSuggesting(true);
        setSuggestedCategories(null);
        try {
            const res = await fetch(`http://localhost:8000/content/${item.id}/auto-categorize`, {
                method: "POST",
                headers: { "X-API-Key": "dev-token-change-me" },
            });
            const data = await res.json();
            if (data.success && data.suggested_categories) {
                setSuggestedCategories(data.suggested_categories);
            }
        } catch (e) {
            console.error("Auto-categorize error:", e);
        } finally {
            setAutoSuggesting(false);
        }
    };

    const handleAcceptSuggestion = () => {
        if (suggestedCategories) {
            onCategorize(suggestedCategories);
            setSuggestedCategories(null);
        }
    };

    const handleRejectSuggestion = () => {
        setSuggestedCategories(null);
    };

    return (
        <div className="bg-zinc-900/80 border border-zinc-800 rounded-lg p-3 hover:border-amber-500/30 transition-all">
            <div className="flex items-start gap-3">
                {/* Content */}
                <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-sm text-zinc-100 truncate">{item.title}</h3>
                    <p className="text-xs text-zinc-500 line-clamp-1 mt-0.5">
                        {cleanSummary || "No description"}
                    </p>
                    {item.source_url && (
                        <a
                            href={item.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[10px] text-blue-400 hover:underline mt-1 inline-block"
                        >
                            🔗 {(() => { try { return new URL(item.source_url).hostname; } catch { return "link"; } })()}
                        </a>
                    )}

                    {/* AI Suggestion Banner */}
                    {suggestedCategories && suggestedCategories.length > 0 && (
                        <div className="mt-2 flex items-center gap-2 bg-gradient-to-r from-cyan-500/10 to-purple-500/10 border border-cyan-500/30 rounded-lg p-2">
                            <span className="text-xs text-cyan-300">✨ AI suggests:</span>
                            <div className="flex gap-1 flex-1 flex-wrap">
                                {suggestedCategories.map((cat) => (
                                    <span
                                        key={cat}
                                        className="text-xs bg-cyan-500/30 text-cyan-200 px-2 py-0.5 rounded-full flex items-center gap-1"
                                    >
                                        {cat}
                                        <button
                                            onClick={() => setSuggestedCategories(prev => prev?.filter(c => c !== cat) || null)}
                                            className="text-cyan-400 hover:text-red-400 ml-0.5"
                                            title="Remove this category"
                                        >
                                            ×
                                        </button>
                                    </span>
                                ))}
                            </div>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={handleAcceptSuggestion}
                                className="h-6 px-2 text-xs text-green-400 hover:text-green-300 hover:bg-green-500/10"
                            >
                                ✓ Accept
                            </Button>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={handleRejectSuggestion}
                                className="h-6 px-2 text-xs text-zinc-500 hover:text-zinc-300"
                            >
                                ✕
                            </Button>
                        </div>
                    )}
                </div>

                {/* Quick Actions */}
                <div className="flex items-center gap-1 shrink-0">
                    {/* Auto-categorize button */}
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={handleAutoCategorize}
                        disabled={autoSuggesting}
                        className="h-7 px-2 text-[10px] text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/10"
                        title="Auto-categorize with AI"
                    >
                        {autoSuggesting ? "⏳" : "✨ Auto"}
                    </Button>

                    {/* Quick category buttons */}
                    <div className="hidden lg:flex gap-1">
                        {CATEGORY_OPTIONS.slice(0, 3).map((cat) => (
                            <Button
                                key={cat}
                                variant="ghost"
                                size="sm"
                                onClick={() => handleQuickCategorize(cat)}
                                className="h-7 px-2 text-[10px] text-zinc-500 hover:text-purple-400 hover:bg-purple-500/10"
                            >
                                {cat}
                            </Button>
                        ))}
                    </div>

                    {/* More categories dialog */}
                    <Dialog open={showCategories} onOpenChange={setShowCategories}>
                        <DialogTrigger asChild>
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 w-7 p-0 text-zinc-500 hover:text-purple-400"
                            >
                                ⋯
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="bg-zinc-900 border-zinc-800">
                            <DialogHeader>
                                <DialogTitle>Categorize: {item.title}</DialogTitle>
                                <DialogDescription>Select one or more categories</DialogDescription>
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
                                        className={
                                            selectedCategories.includes(cat)
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
                                <Button
                                    onClick={() => {
                                        if (selectedCategories.length > 0) {
                                            onCategorize(selectedCategories);
                                            setShowCategories(false);
                                            setSelectedCategories([]);
                                        }
                                    }}
                                    disabled={selectedCategories.length === 0}
                                    className="bg-gradient-to-r from-purple-500 to-blue-500"
                                >
                                    Save
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>

                    {/* Delete */}
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={onDelete}
                        className="h-7 w-7 p-0 text-zinc-600 hover:text-red-400 hover:bg-red-500/10"
                    >
                        ✕
                    </Button>
                </div>
            </div>
        </div>
    );
}

// Organized card - visual, shows categories prominently
function OrganizedCard({
    item,
    onCategorize,
    onDelete,
}: {
    item: ContentItem;
    onCategorize: (categories: string[]) => void;
    onDelete: () => void;
}) {
    const [showEdit, setShowEdit] = useState(false);
    const [selectedCategories, setSelectedCategories] = useState<string[]>(item.categories);
    const [autoSuggesting, setAutoSuggesting] = useState(false);
    const [suggestedCategories, setSuggestedCategories] = useState<string[] | null>(null);

    const cleanSummary = item.summary
        .replace(/Fallback analysis:.*$/gm, "")
        .replace(/400 INVALID_ARGUMENT.*$/gm, "")
        .trim();

    const handleAutoCategorize = async () => {
        setAutoSuggesting(true);
        setSuggestedCategories(null);
        try {
            const res = await fetch(`http://localhost:8000/content/${item.id}/auto-categorize`, {
                method: "POST",
                headers: { "X-API-Key": "dev-token-change-me" },
            });
            const data = await res.json();
            if (data.success && data.suggested_categories) {
                setSuggestedCategories(data.suggested_categories);
            }
        } catch (e) {
            console.error("Auto-categorize error:", e);
        } finally {
            setAutoSuggesting(false);
        }
    };

    const handleAcceptSuggestion = () => {
        if (suggestedCategories) {
            onCategorize(suggestedCategories);
            setSuggestedCategories(null);
        }
    };

    return (
        <Card className="bg-gradient-to-br from-zinc-900/90 to-purple-900/10 border-purple-500/20 hover:border-purple-400/40 rounded-xl transition-all group">
            <CardHeader className="pb-2">
                {/* Category badges */}
                <div className="flex flex-wrap gap-1 mb-2">
                    {item.categories.map((cat) => (
                        <span
                            key={cat}
                            className="text-[10px] bg-purple-500/30 text-purple-200 px-2 py-0.5 rounded-full"
                        >
                            {cat}
                        </span>
                    ))}
                </div>
                <CardTitle className="text-sm font-medium line-clamp-2 text-zinc-100">
                    {item.title}
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 pb-3">
                <CardDescription className="text-xs line-clamp-2 text-zinc-500">
                    {cleanSummary || "No description"}
                </CardDescription>

                {item.source_url && (
                    <a
                        href={item.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[10px] text-blue-400 hover:underline"
                    >
                        🔗 {(() => { try { return new URL(item.source_url).hostname; } catch { return "link"; } })()}
                    </a>
                )}

                {/* AI Suggestion Banner */}
                {suggestedCategories && suggestedCategories.length > 0 && (
                    <div className="flex items-center gap-2 bg-gradient-to-r from-cyan-500/10 to-purple-500/10 border border-cyan-500/30 rounded-lg p-2">
                        <span className="text-xs text-cyan-300">✨</span>
                        <div className="flex gap-1 flex-1 flex-wrap">
                            {suggestedCategories.map((cat) => (
                                <span
                                    key={cat}
                                    className="text-xs bg-cyan-500/30 text-cyan-200 px-2 py-0.5 rounded-full flex items-center gap-1 group/tag"
                                >
                                    {cat}
                                    <button
                                        onClick={() => setSuggestedCategories(prev => prev?.filter(c => c !== cat) || null)}
                                        className="text-cyan-400 hover:text-red-400 ml-0.5"
                                        title="Remove this category"
                                    >
                                        ×
                                    </button>
                                </span>
                            ))}
                        </div>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleAcceptSuggestion}
                            className="h-5 px-2 text-[10px] text-green-400 hover:text-green-300"
                        >
                            ✓
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setSuggestedCategories(null)}
                            className="h-5 px-1 text-[10px] text-zinc-500"
                        >
                            ✕
                        </Button>
                    </div>
                )}

                {/* Actions */}
                <div className="flex gap-1 pt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={async () => {
                            try {
                                const res = await fetch(`http://localhost:8000/content/${item.id}/planner-status?status=queued`, {
                                    method: "PATCH",
                                    headers: { "X-API-Key": "dev-token-change-me" },
                                });
                                if (res.ok) {
                                    // Show brief feedback
                                    alert("Queued for planner!");
                                }
                            } catch (e) {
                                console.error("Queue error:", e);
                            }
                        }}
                        disabled={item.planner_status === "queued"}
                        className={`h-6 text-[10px] ${item.planner_status === "queued" ? "text-green-400" : "text-violet-400 hover:text-violet-300"}`}
                        title={item.planner_status === "queued" ? "Already queued" : "Queue for planner"}
                    >
                        {item.planner_status === "queued" ? "✓ Queued" : "📋 Queue"}
                    </Button>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={handleAutoCategorize}
                        disabled={autoSuggesting}
                        className="h-6 text-[10px] text-cyan-400 hover:text-cyan-300"
                        title="AI auto-categorize"
                    >
                        {autoSuggesting ? "⏳" : "✨ Auto"}
                    </Button>
                    <Dialog open={showEdit} onOpenChange={setShowEdit}>
                        <DialogTrigger asChild>
                            <Button variant="ghost" size="sm" className="h-6 text-[10px] text-zinc-500">
                                Edit
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="bg-zinc-900 border-zinc-800">
                            <DialogHeader>
                                <DialogTitle>Edit Categories</DialogTitle>
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
                                        className={
                                            selectedCategories.includes(cat)
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
                                <Button
                                    onClick={() => {
                                        onCategorize(selectedCategories);
                                        setShowEdit(false);
                                    }}
                                    className="bg-gradient-to-r from-purple-500 to-blue-500"
                                >
                                    Save
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={onDelete}
                        className="h-6 text-[10px] text-zinc-500 hover:text-red-400"
                    >
                        Delete
                    </Button>
                </div>
            </CardContent>
        </Card>
    );
}

function EvidenceCard({ item }: { item: EvidenceItem }) {
    const title = item.payload?.title || item.evidence_id;
    const summary = item.payload?.summary || item.payload?.content || "";
    const source = item.metadata?.source_url || item.payload?.link;

    return (
        <Card className="bg-zinc-900/80 border-zinc-800 hover:border-cyan-500/30 rounded-xl transition-all">
            <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-2">
                    <CardTitle className="text-sm font-medium line-clamp-2 text-zinc-100">
                        {title}
                    </CardTitle>
                    <span
                        className={`shrink-0 text-[10px] px-2 py-0.5 rounded-full ${item.lifecycle === "active"
                            ? "bg-green-500/20 text-green-400"
                            : "bg-zinc-700 text-zinc-400"
                            }`}
                    >
                        {item.lifecycle}
                    </span>
                </div>
            </CardHeader>
            <CardContent>
                <CardDescription className="text-xs line-clamp-2 text-zinc-500">
                    {summary}
                </CardDescription>
                {source && (
                    <a
                        href={source}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[10px] text-cyan-400 hover:underline mt-2 inline-block"
                    >
                        🔗 View source
                    </a>
                )}
            </CardContent>
        </Card>
    );
}
