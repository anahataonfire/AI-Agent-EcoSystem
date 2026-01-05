"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

interface EvidenceItem {
    evidence_id: string;
    payload: Record<string, any>;
    metadata: Record<string, any>;
    created_at: string;
    lifecycle: string;
}

export default function LibraryPage() {
    const [search, setSearch] = useState("");
    const [items, setItems] = useState<EvidenceItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchEvidence = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch("http://localhost:8000/evidence/browse?limit=50", {
                headers: { "X-API-Key": "dev-token-change-me" },
            });
            if (!res.ok) throw new Error(`API error: ${res.status}`);
            const data = await res.json();
            setItems(data);
        } catch (e: any) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchEvidence();
    }, []);

    const filteredItems = search
        ? items.filter((item) => {
            const title = item.payload?.title || "";
            const summary = item.payload?.summary || "";
            return (
                title.toLowerCase().includes(search.toLowerCase()) ||
                summary.toLowerCase().includes(search.toLowerCase())
            );
        })
        : items;

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold">📚 Content Library</h1>
                <p className="text-zinc-400 mt-1">Browse all evidence and curated knowledge</p>
            </div>

            <div className="flex gap-4">
                <Input
                    placeholder="Search your library..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="bg-zinc-800 border-zinc-700 max-w-md"
                />
                <Button variant="outline" onClick={fetchEvidence} disabled={loading}>
                    {loading ? "Loading..." : "Refresh"}
                </Button>
            </div>

            {error && (
                <Card className="bg-yellow-950/50 border-yellow-800">
                    <CardContent className="p-4">
                        <p className="text-yellow-400">⚠️ Error loading: {error}</p>
                    </CardContent>
                </Card>
            )}

            <div className="text-sm text-zinc-500">
                Showing {filteredItems.length} of {items.length} items
            </div>

            {filteredItems.length === 0 && !loading ? (
                <Card className="bg-zinc-900 border-zinc-800">
                    <CardContent className="py-12 text-center">
                        <div className="text-4xl mb-4">📚</div>
                        <h3 className="text-lg font-medium">
                            {items.length === 0 ? "Library is empty" : "No matching items"}
                        </h3>
                        <p className="text-zinc-500 mt-2">
                            {items.length === 0
                                ? "Run a mission to collect evidence, or add content via the Inbox."
                                : "Try a different search term."}
                        </p>
                    </CardContent>
                </Card>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {filteredItems.map((item) => (
                        <EvidenceCard key={item.evidence_id} item={item} />
                    ))}
                </div>
            )}
        </div>
    );
}

function EvidenceCard({ item }: { item: EvidenceItem }) {
    const [expanded, setExpanded] = useState(false);
    const title = item.payload?.title || item.evidence_id;
    const summary = item.payload?.summary || item.payload?.content || "";
    const source = item.metadata?.source_url || item.payload?.link;
    const type = item.metadata?.type || "evidence";

    return (
        <Card
            className="bg-zinc-900 border-zinc-800 hover:border-zinc-700 transition-colors cursor-pointer"
            onClick={() => setExpanded(!expanded)}
        >
            <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                    <CardTitle className="text-base line-clamp-2">{title}</CardTitle>
                    <span
                        className={`text-xs px-2 py-1 rounded ${item.lifecycle === "active"
                                ? "bg-green-500/20 text-green-400"
                                : "bg-zinc-700 text-zinc-400"
                            }`}
                    >
                        {item.lifecycle}
                    </span>
                </div>
                <CardDescription className={expanded ? "" : "line-clamp-3"}>
                    {summary}
                </CardDescription>
            </CardHeader>
            <CardContent className="pt-0">
                <div className="flex flex-wrap gap-1 mb-2">
                    <span className="text-xs bg-zinc-800 px-2 py-1 rounded">{type}</span>
                </div>
                {source && (
                    <a
                        href={source}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-400 hover:underline"
                        onClick={(e) => e.stopPropagation()}
                    >
                        {new URL(source).hostname} →
                    </a>
                )}
                <p className="text-xs text-zinc-600 mt-2">
                    ID: {item.evidence_id.slice(0, 20)}...
                </p>
            </CardContent>
        </Card>
    );
}
