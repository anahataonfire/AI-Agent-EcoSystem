"use client";

import { useState, useEffect, useMemo } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface Document {
    url: string;
    title: string;
    category: string;
    local_path: string;
    sha256: string;
    downloaded_at: string;
    size_bytes: number;
    version: string;
    product_version: string;
    release_date: string;
    last_updated: string;
    updated: boolean;
    doc_type: string;
}

interface DiscoveredDoc {
    url: string;
    title: string;
    category: string;
    version: string;
    product_version: string;
    release_date: string;
    last_updated: string;
    doc_type: "pdf" | "zip";
}

interface Manifest {
    last_run: string;
    documents: Document[];
}

interface Stats {
    total_documents: number;
    total_size_bytes: number;
    total_size_mb: number;
    updated_count: number;
    last_run: string;
    by_category: Record<string, { count: number; size: number }>;
}

type TabType = "downloaded" | "discover";

export default function InformaticaPage() {
    const [activeTab, setActiveTab] = useState<TabType>("discover");
    const [manifest, setManifest] = useState<Manifest | null>(null);
    const [stats, setStats] = useState<Stats | null>(null);
    const [loading, setLoading] = useState(true);
    const [syncing, setSyncing] = useState(false);
    const [syncProgress, setSyncProgress] = useState<string>("");
    const [search, setSearch] = useState("");
    const [error, setError] = useState<string | null>(null);
    const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());
    const [latestOnly, setLatestOnly] = useState(true);

    // Discovery state
    const [discovering, setDiscovering] = useState(false);
    const [discoveryProgress, setDiscoveryProgress] = useState("");
    const [discoveredDocs, setDiscoveredDocs] = useState<DiscoveredDoc[]>([]);
    const [discoveryComplete, setDiscoveryComplete] = useState(false);

    const fetchData = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch("/api/informatica");
            if (!res.ok) throw new Error(`API error: ${res.status}`);
            const data = await res.json();
            setManifest(data.manifest);
            setStats(data.stats);
        } catch (e: any) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
        // Also check if there's a discovery in progress
        checkDiscoveryStatus();
    }, []);

    const checkDiscoveryStatus = async () => {
        try {
            const res = await fetch("/api/informatica/discover");
            if (!res.ok) return;
            const data = await res.json();
            if (data.running) {
                setDiscovering(true);
                setDiscoveryProgress(data.message);
                setTimeout(checkDiscoveryStatus, 2000);
            } else if (data.complete && data.documents?.length > 0) {
                setDiscoveredDocs(data.documents);
                setDiscoveryComplete(true);
                setDiscovering(false);
                setDiscoveryProgress(data.message);
            }
        } catch {
            // Ignore
        }
    };

    const handleDiscover = async (maxPages: number = 100) => {
        setDiscovering(true);
        setDiscoveryProgress("Starting discovery...");
        setDiscoveredDocs([]);
        setDiscoveryComplete(false);

        try {
            const res = await fetch("/api/informatica/discover", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ maxPages, allVersions: !latestOnly })
            });
            if (!res.ok) throw new Error(`Discovery failed: ${res.status}`);

            // Poll for status
            const pollStatus = async () => {
                const statusRes = await fetch("/api/informatica/discover");
                if (!statusRes.ok) return;
                const status = await statusRes.json();
                setDiscoveryProgress(status.message || "Discovering...");

                if (status.running) {
                    setTimeout(pollStatus, 2000);
                } else {
                    setDiscovering(false);
                    if (status.complete && status.documents) {
                        setDiscoveredDocs(status.documents);
                        setDiscoveryComplete(true);
                    }
                }
            };
            pollStatus();
        } catch (e: any) {
            setError(e.message);
            setDiscovering(false);
            setDiscoveryProgress("");
        }
    };

    const handleSync = async () => {
        setSyncing(true);
        setSyncProgress("Starting sync...");
        try {
            const res = await fetch("/api/informatica/sync", { method: "POST" });
            if (!res.ok) throw new Error(`Sync failed: ${res.status}`);

            // Poll for status
            const pollStatus = async () => {
                const statusRes = await fetch("/api/informatica/sync");
                if (!statusRes.ok) return;
                const status = await statusRes.json();
                setSyncProgress(status.message || "Syncing...");
                if (status.running) {
                    setTimeout(pollStatus, 2000);
                } else {
                    setSyncing(false);
                    setSyncProgress("");
                    fetchData();
                }
            };
            pollStatus();
        } catch (e: any) {
            setError(e.message);
            setSyncing(false);
            setSyncProgress("");
        }
    };

    const toggleCategory = (category: string) => {
        setExpandedCategories(prev => {
            const next = new Set(prev);
            if (next.has(category)) {
                next.delete(category);
            } else {
                next.add(category);
            }
            return next;
        });
    };

    // Group documents by category
    const documentsByCategory = useMemo(() => {
        if (!manifest) return {};
        const grouped: Record<string, Document[]> = {};
        for (const doc of manifest.documents) {
            if (!grouped[doc.category]) {
                grouped[doc.category] = [];
            }
            if (search) {
                if (doc.title.toLowerCase().includes(search.toLowerCase()) ||
                    doc.category.toLowerCase().includes(search.toLowerCase())) {
                    grouped[doc.category].push(doc);
                }
            } else {
                grouped[doc.category].push(doc);
            }
        }
        for (const cat of Object.keys(grouped)) {
            if (grouped[cat].length === 0) {
                delete grouped[cat];
            }
        }
        return grouped;
    }, [manifest, search]);

    // Group discovered docs by category
    const discoveredByCategory = useMemo(() => {
        const grouped: Record<string, DiscoveredDoc[]> = {};
        for (const doc of discoveredDocs) {
            if (!grouped[doc.category]) {
                grouped[doc.category] = [];
            }
            if (search) {
                if (doc.title.toLowerCase().includes(search.toLowerCase()) ||
                    doc.category.toLowerCase().includes(search.toLowerCase())) {
                    grouped[doc.category].push(doc);
                }
            } else {
                grouped[doc.category].push(doc);
            }
        }
        for (const cat of Object.keys(grouped)) {
            if (grouped[cat].length === 0) {
                delete grouped[cat];
            }
        }
        return grouped;
    }, [discoveredDocs, search]);

    const recentlyUpdated = useMemo(() => {
        if (!manifest) return [];
        return manifest.documents
            .filter(d => d.updated)
            .sort((a, b) => new Date(b.downloaded_at).getTime() - new Date(a.downloaded_at).getTime())
            .slice(0, 10);
    }, [manifest]);

    const formatSize = (bytes: number) => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    };

    const formatDate = (dateStr: string) => {
        if (!dateStr) return "Never";
        const date = new Date(dateStr);
        return date.toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit"
        });
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-r from-orange-500/10 via-amber-500/10 to-yellow-500/10 rounded-2xl blur-xl" />
                <div className="relative bg-zinc-900/80 backdrop-blur-sm border border-zinc-800 rounded-2xl p-6">
                    <div className="flex items-center justify-between">
                        <div>
                            <h1 className="text-3xl font-bold bg-gradient-to-r from-orange-400 via-amber-400 to-yellow-400 bg-clip-text text-transparent">
                                Informatica Documentation
                            </h1>
                            <p className="text-zinc-500 text-sm mt-1">
                                {stats?.total_documents || 0} downloaded • {stats?.total_size_mb || 0} MB • Last sync: {formatDate(stats?.last_run || "")}
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
                                onClick={fetchData}
                                disabled={loading}
                                className="h-10 px-4 rounded-lg border-zinc-700"
                            >
                                {loading ? "⟳" : "↻"}
                            </Button>
                        </div>
                    </div>

                    {/* Tabs */}
                    <div className="flex gap-2 mt-4">
                        <button
                            onClick={() => setActiveTab("discover")}
                            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === "discover"
                                ? "bg-orange-500/20 text-orange-300 border border-orange-500/30"
                                : "bg-zinc-800/50 text-zinc-400 border border-zinc-700 hover:text-zinc-200"
                                }`}
                        >
                            🔍 Discover Available
                        </button>
                        <button
                            onClick={() => setActiveTab("downloaded")}
                            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === "downloaded"
                                ? "bg-orange-500/20 text-orange-300 border border-orange-500/30"
                                : "bg-zinc-800/50 text-zinc-400 border border-zinc-700 hover:text-zinc-200"
                                }`}
                        >
                            📥 Downloaded ({stats?.total_documents || 0})
                        </button>
                    </div>
                </div>
            </div>

            {error && (
                <div className="bg-red-950/30 border border-red-800/50 rounded-xl p-4 flex items-center justify-between">
                    <div>
                        <p className="text-red-400 font-medium">⚠️ Error</p>
                        <p className="text-red-400/70 text-sm">{error}</p>
                    </div>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={fetchData}
                        className="border-red-800 text-red-400 hover:bg-red-900/30"
                    >
                        ↻ Retry
                    </Button>
                </div>
            )}

            {/* Discover Tab */}
            {activeTab === "discover" && (
                <div className="space-y-6">
                    {/* Discovery Controls */}
                    <div className="bg-zinc-900/80 border border-zinc-800 rounded-xl p-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <h2 className="text-lg font-semibold text-orange-400">Discover Available Documentation</h2>
                                <p className="text-zinc-500 text-sm mt-1">
                                    Scan docs.informatica.com to see what documentation is available before downloading.
                                </p>
                            </div>
                            <div className="flex gap-3">
                                <Button
                                    onClick={() => handleDiscover(50)}
                                    disabled={discovering}
                                    variant="outline"
                                    className="border-zinc-700"
                                >
                                    {discovering ? "⏳ Scanning..." : "🔍 Quick Scan (50 pages)"}
                                </Button>
                                <Button
                                    onClick={() => handleDiscover(200)}
                                    disabled={discovering}
                                    className="bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600"
                                >
                                    {discovering ? "⏳ Scanning..." : "🔍 Full Scan (200 pages)"}
                                </Button>
                            </div>
                        </div>

                        {/* Latest versions only toggle */}
                        <div className="mt-4 flex items-center gap-3 pt-4 border-t border-zinc-800">
                            <label className="flex items-center gap-2 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={latestOnly}
                                    onChange={(e) => setLatestOnly(e.target.checked)}
                                    className="w-4 h-4 rounded border-zinc-600 bg-zinc-800 text-orange-500 focus:ring-orange-500 focus:ring-offset-zinc-900"
                                />
                                <span className="text-sm text-zinc-300">Latest versions only</span>
                            </label>
                            <span className="text-xs text-zinc-500">
                                {latestOnly
                                    ? "Excludes historical versions (recommended)"
                                    : "Includes all historical versions of each document"
                                }
                            </span>
                        </div>

                        {discovering && (
                            <div className="mt-4 bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
                                <p className="text-amber-400 text-sm">{discoveryProgress}</p>
                                <div className="mt-2 h-1 bg-zinc-800 rounded-full overflow-hidden">
                                    <div className="h-full bg-amber-500 animate-pulse" style={{ width: "60%" }} />
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Discovery Results */}
                    {discoveryComplete && discoveredDocs.length > 0 && (
                        <>
                            {/* Stats */}
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                <Card className="bg-zinc-900/80 border-zinc-800">
                                    <CardHeader className="pb-2">
                                        <CardDescription className="text-zinc-500">Available Documents</CardDescription>
                                        <CardTitle className="text-3xl font-bold text-orange-400">
                                            {discoveredDocs.length}
                                        </CardTitle>
                                    </CardHeader>
                                </Card>
                                <Card className="bg-zinc-900/80 border-zinc-800">
                                    <CardHeader className="pb-2">
                                        <CardDescription className="text-zinc-500">Categories</CardDescription>
                                        <CardTitle className="text-3xl font-bold text-amber-400">
                                            {Object.keys(discoveredByCategory).length}
                                        </CardTitle>
                                    </CardHeader>
                                </Card>
                                <Card className="bg-zinc-900/80 border-zinc-800">
                                    <CardHeader className="pb-2">
                                        <CardDescription className="text-zinc-500">Doc Sets (ZIPs)</CardDescription>
                                        <CardTitle className="text-3xl font-bold text-yellow-400">
                                            {discoveredDocs.filter(d => d.doc_type === "zip").length}
                                        </CardTitle>
                                    </CardHeader>
                                </Card>
                            </div>

                            {/* Download All Button */}
                            <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4 flex items-center justify-between">
                                <div>
                                    <h3 className="text-green-400 font-medium">Ready to Download</h3>
                                    <p className="text-green-400/70 text-sm">
                                        {discoveredDocs.length} documents found. Documentation sets (ZIPs) contain multiple PDFs each.
                                    </p>
                                </div>
                                <Button
                                    onClick={handleSync}
                                    disabled={syncing}
                                    className="bg-green-600 hover:bg-green-700"
                                >
                                    {syncing ? "⏳ Downloading..." : "📥 Download All"}
                                </Button>
                            </div>

                            {syncProgress && (
                                <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
                                    <p className="text-amber-400 text-sm">{syncProgress}</p>
                                </div>
                            )}

                            {/* Category Browser */}
                            <div>
                                <div className="flex items-center gap-3 mb-3">
                                    <span className="text-lg">📂</span>
                                    <h2 className="text-lg font-semibold text-orange-400">Available by Category</h2>
                                </div>

                                <div className="space-y-3">
                                    {Object.entries(discoveredByCategory)
                                        .sort(([a], [b]) => a.localeCompare(b))
                                        .map(([category, docs]) => (
                                            <div key={category} className="bg-zinc-900/80 border border-zinc-800 rounded-xl overflow-hidden">
                                                <button
                                                    onClick={() => toggleCategory(category)}
                                                    className="w-full flex items-center justify-between p-4 hover:bg-zinc-800/50 transition-colors"
                                                >
                                                    <div className="flex items-center gap-3">
                                                        <span className="text-lg">
                                                            {expandedCategories.has(category) ? "📂" : "📁"}
                                                        </span>
                                                        <span className="font-medium text-zinc-100">{category}</span>
                                                        <span className="text-xs bg-orange-500/20 text-orange-300 px-2 py-0.5 rounded-full">
                                                            {docs.length} docs
                                                        </span>
                                                        <span className="text-xs text-zinc-500">
                                                            {docs.filter(d => d.doc_type === "zip").length} ZIPs, {docs.filter(d => d.doc_type === "pdf").length} PDFs
                                                        </span>
                                                    </div>
                                                    <span className="text-zinc-500">
                                                        {expandedCategories.has(category) ? "▼" : "▶"}
                                                    </span>
                                                </button>

                                                {expandedCategories.has(category) && (
                                                    <div className="border-t border-zinc-800 p-4">
                                                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                                                            {docs.map((doc) => (
                                                                <DiscoveredDocCard key={doc.url} doc={doc} />
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                </div>
                            </div>
                        </>
                    )}

                    {!discovering && !discoveryComplete && (
                        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-12 text-center">
                            <div className="text-5xl mb-4">🔍</div>
                            <h3 className="text-xl font-semibold text-zinc-200 mb-2">
                                Discover Available Documentation
                            </h3>
                            <p className="text-zinc-500 max-w-md mx-auto">
                                Click "Quick Scan" or "Full Scan" above to discover what documentation is available
                                from docs.informatica.com before downloading.
                            </p>
                        </div>
                    )}
                </div>
            )}

            {/* Downloaded Tab */}
            {activeTab === "downloaded" && (
                <div className="space-y-6">
                    {/* Stats Cards */}
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                        <Card className="bg-zinc-900/80 border-zinc-800">
                            <CardHeader className="pb-2">
                                <CardDescription className="text-zinc-500">Total Documents</CardDescription>
                                <CardTitle className="text-3xl font-bold text-orange-400">
                                    {stats?.total_documents || 0}
                                </CardTitle>
                            </CardHeader>
                        </Card>
                        <Card className="bg-zinc-900/80 border-zinc-800">
                            <CardHeader className="pb-2">
                                <CardDescription className="text-zinc-500">Total Size</CardDescription>
                                <CardTitle className="text-3xl font-bold text-amber-400">
                                    {stats?.total_size_mb || 0} MB
                                </CardTitle>
                            </CardHeader>
                        </Card>
                        <Card className="bg-zinc-900/80 border-zinc-800">
                            <CardHeader className="pb-2">
                                <CardDescription className="text-zinc-500">Categories</CardDescription>
                                <CardTitle className="text-3xl font-bold text-yellow-400">
                                    {Object.keys(documentsByCategory).length}
                                </CardTitle>
                            </CardHeader>
                        </Card>
                        <Card className="bg-zinc-900/80 border-zinc-800">
                            <CardHeader className="pb-2">
                                <CardDescription className="text-zinc-500">Recently Updated</CardDescription>
                                <CardTitle className="text-3xl font-bold text-green-400">
                                    {stats?.updated_count || 0}
                                </CardTitle>
                            </CardHeader>
                        </Card>
                    </div>

                    {/* Recently Updated */}
                    {recentlyUpdated.length > 0 && (
                        <div>
                            <div className="flex items-center gap-3 mb-3">
                                <span className="text-lg">🔄</span>
                                <h2 className="text-lg font-semibold text-green-400">Recently Updated</h2>
                                <span className="text-xs bg-green-500/20 text-green-300 px-2 py-0.5 rounded-full">
                                    {recentlyUpdated.length} docs
                                </span>
                            </div>
                            <div className="bg-green-500/5 border border-green-500/20 rounded-xl p-4">
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                                    {recentlyUpdated.map((doc) => (
                                        <DownloadedDocCard key={doc.url} doc={doc} formatSize={formatSize} formatDate={formatDate} />
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Category Browser */}
                    <div>
                        <div className="flex items-center gap-3 mb-3">
                            <span className="text-lg">📂</span>
                            <h2 className="text-lg font-semibold text-orange-400">Downloaded by Category</h2>
                        </div>

                        {Object.keys(documentsByCategory).length === 0 ? (
                            <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-8 text-center">
                                <div className="text-4xl mb-3">📄</div>
                                <p className="text-zinc-500">
                                    {loading ? "Loading documentation..." : "No documentation downloaded yet. Switch to 'Discover Available' to scan and download."}
                                </p>
                            </div>
                        ) : (
                            <div className="space-y-3">
                                {Object.entries(documentsByCategory)
                                    .sort(([a], [b]) => a.localeCompare(b))
                                    .map(([category, docs]) => (
                                        <div key={category} className="bg-zinc-900/80 border border-zinc-800 rounded-xl overflow-hidden">
                                            <button
                                                onClick={() => toggleCategory(category)}
                                                className="w-full flex items-center justify-between p-4 hover:bg-zinc-800/50 transition-colors"
                                            >
                                                <div className="flex items-center gap-3">
                                                    <span className="text-lg">
                                                        {expandedCategories.has(category) ? "📂" : "📁"}
                                                    </span>
                                                    <span className="font-medium text-zinc-100">{category}</span>
                                                    <span className="text-xs bg-orange-500/20 text-orange-300 px-2 py-0.5 rounded-full">
                                                        {docs.length} docs
                                                    </span>
                                                    <span className="text-xs text-zinc-500">
                                                        {formatSize(docs.reduce((sum, d) => sum + d.size_bytes, 0))}
                                                    </span>
                                                </div>
                                                <span className="text-zinc-500">
                                                    {expandedCategories.has(category) ? "▼" : "▶"}
                                                </span>
                                            </button>

                                            {expandedCategories.has(category) && (
                                                <div className="border-t border-zinc-800 p-4">
                                                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                                                        {docs.map((doc) => (
                                                            <DownloadedDocCard key={doc.url} doc={doc} formatSize={formatSize} formatDate={formatDate} />
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    ))}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

function DiscoveredDocCard({ doc }: { doc: DiscoveredDoc }) {
    return (
        <Card className="bg-zinc-800/50 border-zinc-700 hover:border-orange-500/30 transition-all">
            <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-2">
                    <CardTitle className="text-sm font-medium line-clamp-2 text-zinc-100">
                        {doc.doc_type === "zip" ? "📦" : "📄"} {doc.title}
                    </CardTitle>
                    <span className={`shrink-0 text-[10px] px-2 py-0.5 rounded-full ${doc.doc_type === "zip"
                        ? "bg-purple-500/20 text-purple-400"
                        : "bg-blue-500/20 text-blue-400"
                        }`}>
                        {doc.doc_type.toUpperCase()}
                    </span>
                </div>
            </CardHeader>
            <CardContent className="space-y-2">
                {/* Version and date metadata */}
                <div className="flex flex-wrap items-center gap-2 text-xs">
                    {doc.version && (
                        <span className="bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded">
                            📅 {doc.version}
                        </span>
                    )}
                    {doc.product_version && (
                        <span className="bg-blue-500/20 text-blue-300 px-2 py-0.5 rounded">
                            v{doc.product_version}
                        </span>
                    )}
                </div>
                {(doc.release_date || doc.last_updated) && (
                    <div className="text-[10px] text-zinc-500">
                        {doc.release_date && <span>Released: {doc.release_date}</span>}
                        {doc.release_date && doc.last_updated && <span> • </span>}
                        {doc.last_updated && <span>Updated: {doc.last_updated}</span>}
                    </div>
                )}
                <p className="text-xs text-zinc-500 line-clamp-1">
                    {doc.category}
                </p>
                <div className="flex gap-2 pt-2">
                    <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 text-[10px] text-orange-400 hover:text-orange-300"
                        onClick={() => window.open(doc.url, "_blank")}
                    >
                        🔗 View Source
                    </Button>
                </div>
            </CardContent>
        </Card>
    );
}

function DownloadedDocCard({
    doc,
    formatSize,
    formatDate
}: {
    doc: Document;
    formatSize: (bytes: number) => string;
    formatDate: (dateStr: string) => string;
}) {
    return (
        <Card className={`bg-zinc-800/50 border-zinc-700 hover:border-orange-500/30 transition-all ${doc.updated ? 'ring-1 ring-green-500/30' : ''}`}>
            <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-2">
                    <CardTitle className="text-sm font-medium line-clamp-2 text-zinc-100">
                        {doc.doc_type === "zip" ? "📦" : "📄"} {doc.title}
                    </CardTitle>
                    {doc.updated && (
                        <span className="shrink-0 text-[10px] bg-green-500/20 text-green-400 px-2 py-0.5 rounded-full">
                            Updated
                        </span>
                    )}
                </div>
            </CardHeader>
            <CardContent className="space-y-2">
                {/* Version and release metadata */}
                <div className="flex flex-wrap items-center gap-2 text-xs">
                    {doc.version && (
                        <span className="bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded">
                            📅 {doc.version}
                        </span>
                    )}
                    {doc.product_version && (
                        <span className="bg-blue-500/20 text-blue-300 px-2 py-0.5 rounded">
                            v{doc.product_version}
                        </span>
                    )}
                    <span className="text-zinc-500">{formatSize(doc.size_bytes)}</span>
                </div>
                {(doc.release_date || doc.last_updated) && (
                    <div className="text-[10px] text-zinc-500">
                        {doc.release_date && <span>Released: {doc.release_date}</span>}
                        {doc.release_date && doc.last_updated && <span> • </span>}
                        {doc.last_updated && <span>Updated: {doc.last_updated}</span>}
                    </div>
                )}
                <p className="text-[10px] text-zinc-600">
                    Downloaded: {formatDate(doc.downloaded_at)}
                </p>
                <div className="flex gap-2 pt-2">
                    <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 text-[10px] text-orange-400 hover:text-orange-300"
                        onClick={() => window.open(doc.url, "_blank")}
                    >
                        🔗 Source
                    </Button>
                    {doc.local_path && (
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 text-[10px] text-zinc-500"
                        >
                            📁 {doc.local_path.split('/').pop()}
                        </Button>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}
