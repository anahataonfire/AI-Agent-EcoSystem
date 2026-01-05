"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

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
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold">📚 Content Library</h1>
                <p className="text-zinc-400 mt-1">Your curated links and research evidence</p>
            </div>

            <div className="flex gap-4">
                <Input
                    placeholder="Search..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="bg-zinc-800 border-zinc-700 max-w-md"
                />
                <Button
                    variant="outline"
                    onClick={() => { fetchContent(); fetchEvidence(); }}
                    disabled={loading}
                >
                    {loading ? "Loading..." : "Refresh"}
                </Button>
            </div>

            {error && (
                <Card className="bg-yellow-950/50 border-yellow-800">
                    <CardContent className="p-4">
                        <p className="text-yellow-400">⚠️ API error: {error}</p>
                    </CardContent>
                </Card>
            )}

            <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList className="bg-zinc-800">
                    <TabsTrigger value="content">
                        📎 Curated Links ({contentItems.length})
                    </TabsTrigger>
                    <TabsTrigger value="evidence">
                        📦 Evidence ({evidenceItems.length})
                    </TabsTrigger>
                </TabsList>

                <TabsContent value="content" className="mt-4">
                    {filteredContent.length === 0 ? (
                        <EmptyState
                            icon="📎"
                            title="No curated links yet"
                            description="Add links via the Inbox to start your collection."
                        />
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {filteredContent.map((item) => (
                                <ContentCard key={item.id} item={item} />
                            ))}
                        </div>
                    )}
                </TabsContent>

                <TabsContent value="evidence" className="mt-4">
                    {filteredEvidence.length === 0 ? (
                        <EmptyState
                            icon="📦"
                            title="No evidence collected"
                            description="Run a mission to collect research evidence."
                        />
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
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
        <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="py-12 text-center">
                <div className="text-4xl mb-4">{icon}</div>
                <h3 className="text-lg font-medium">{title}</h3>
                <p className="text-zinc-500 mt-2">{description}</p>
            </CardContent>
        </Card>
    );
}

function ContentCard({ item }: { item: ContentItem }) {
    return (
        <Card className="bg-zinc-900 border-zinc-800 hover:border-zinc-700 transition-colors">
            <CardHeader className="pb-2">
                <CardTitle className="text-base line-clamp-2">{item.title}</CardTitle>
                <CardDescription className="line-clamp-3">{item.summary}</CardDescription>
            </CardHeader>
            <CardContent className="pt-0">
                {item.categories.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-2">
                        {item.categories.map((cat) => (
                            <span key={cat} className="text-xs bg-blue-500/20 text-blue-400 px-2 py-1 rounded">
                                {cat}
                            </span>
                        ))}
                    </div>
                )}
                {item.source_url && (
                    <a
                        href={item.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-400 hover:underline"
                    >
                        {new URL(item.source_url).hostname} →
                    </a>
                )}
            </CardContent>
        </Card>
    );
}

function EvidenceCard({ item }: { item: EvidenceItem }) {
    const title = item.payload?.title || item.evidence_id;
    const summary = item.payload?.summary || item.payload?.content || "";
    const source = item.metadata?.source_url || item.payload?.link;

    return (
        <Card className="bg-zinc-900 border-zinc-800 hover:border-zinc-700 transition-colors">
            <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                    <CardTitle className="text-base line-clamp-2">{title}</CardTitle>
                    <span className={`text-xs px-2 py-1 rounded ${item.lifecycle === "active"
                            ? "bg-green-500/20 text-green-400"
                            : "bg-zinc-700 text-zinc-400"
                        }`}>
                        {item.lifecycle}
                    </span>
                </div>
                <CardDescription className="line-clamp-3">{summary}</CardDescription>
            </CardHeader>
            <CardContent className="pt-0">
                {source && (
                    <a
                        href={source}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-400 hover:underline"
                    >
                        View source →
                    </a>
                )}
            </CardContent>
        </Card>
    );
}
