"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

interface InboxEntry {
    id: string;
    type: "link" | "text" | "note";
    content: string;
    status: "pending" | "processed";
    created_at: string;
}

export default function InboxPage() {
    const [activeTab, setActiveTab] = useState<"link" | "text">("link");
    const [linkUrl, setLinkUrl] = useState("");
    const [textContent, setTextContent] = useState("");
    const [notes, setNotes] = useState("");
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
    const [recentItems, setRecentItems] = useState<InboxEntry[]>([]);

    const submitToInbox = async () => {
        setLoading(true);
        setMessage(null);

        try {
            const body = activeTab === "link"
                ? { url: linkUrl, notes }
                : { text: textContent, notes };

            const res = await fetch("http://localhost:8000/inbox/add", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-API-Key": "dev-token-change-me",
                },
                body: JSON.stringify(body),
            });

            if (!res.ok) throw new Error(`API error: ${res.status}`);

            const data = await res.json();
            setMessage({ type: "success", text: `Added to inbox: ${data.id}` });
            setLinkUrl("");
            setTextContent("");
            setNotes("");

            // Add to recent items
            setRecentItems([
                {
                    id: data.id,
                    type: activeTab,
                    content: activeTab === "link" ? linkUrl : textContent.slice(0, 100),
                    status: "pending",
                    created_at: new Date().toISOString(),
                },
                ...recentItems.slice(0, 4),
            ]);
        } catch (e: any) {
            setMessage({ type: "error", text: e.message });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-8">
            {/* Header */}
            <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-r from-sky-500/10 via-blue-500/10 to-indigo-500/10 rounded-2xl blur-xl" />
                <div className="relative bg-zinc-900/80 backdrop-blur-sm border border-zinc-800 rounded-2xl p-6">
                    <h1 className="text-4xl font-bold bg-gradient-to-r from-sky-400 via-blue-400 to-indigo-400 bg-clip-text text-transparent">
                        Inbox
                    </h1>
                    <p className="text-zinc-400 mt-2">Add links and notes to your knowledge base</p>
                </div>
            </div>

            {/* Add Content Form */}
            <Card className="bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl">
                <CardHeader className="border-b border-zinc-800">
                    <div className="flex items-center gap-3">
                        <Button
                            variant={activeTab === "link" ? "default" : "outline"}
                            onClick={() => setActiveTab("link")}
                            className={`rounded-xl ${activeTab === "link"
                                    ? "bg-gradient-to-r from-sky-500 to-blue-500"
                                    : "border-zinc-700"
                                }`}
                        >
                            🔗 Add Link
                        </Button>
                        <Button
                            variant={activeTab === "text" ? "default" : "outline"}
                            onClick={() => setActiveTab("text")}
                            className={`rounded-xl ${activeTab === "text"
                                    ? "bg-gradient-to-r from-sky-500 to-blue-500"
                                    : "border-zinc-700"
                                }`}
                        >
                            📝 Add Text
                        </Button>
                    </div>
                </CardHeader>
                <CardContent className="p-6 space-y-4">
                    {activeTab === "link" ? (
                        <div className="space-y-4">
                            <div>
                                <label className="text-sm text-zinc-400 mb-2 block">URL</label>
                                <Input
                                    placeholder="https://example.com/article"
                                    value={linkUrl}
                                    onChange={(e) => setLinkUrl(e.target.value)}
                                    className="bg-zinc-800/50 border-zinc-700 rounded-xl h-12"
                                />
                            </div>
                            <div>
                                <label className="text-sm text-zinc-400 mb-2 block">Notes (optional)</label>
                                <Textarea
                                    placeholder="Why is this interesting? What should I do with it?"
                                    value={notes}
                                    onChange={(e) => setNotes(e.target.value)}
                                    className="bg-zinc-800/50 border-zinc-700 rounded-xl min-h-[80px]"
                                />
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-4">
                            <div>
                                <label className="text-sm text-zinc-400 mb-2 block">Content</label>
                                <Textarea
                                    placeholder="Paste or type content to save..."
                                    value={textContent}
                                    onChange={(e) => setTextContent(e.target.value)}
                                    className="bg-zinc-800/50 border-zinc-700 rounded-xl min-h-[120px]"
                                />
                            </div>
                            <div>
                                <label className="text-sm text-zinc-400 mb-2 block">Notes (optional)</label>
                                <Input
                                    placeholder="Quick note about this content"
                                    value={notes}
                                    onChange={(e) => setNotes(e.target.value)}
                                    className="bg-zinc-800/50 border-zinc-700 rounded-xl"
                                />
                            </div>
                        </div>
                    )}

                    <Button
                        onClick={submitToInbox}
                        disabled={loading || (activeTab === "link" ? !linkUrl : !textContent)}
                        className="w-full h-14 text-lg rounded-xl bg-gradient-to-r from-sky-500 to-blue-500 hover:from-sky-600 hover:to-blue-600"
                    >
                        {loading ? "⟳ Adding..." : "📥 Add to Inbox"}
                    </Button>

                    {message && (
                        <div className={`p-4 rounded-xl ${message.type === "success"
                                ? "bg-green-950/30 border border-green-800/50 text-green-400"
                                : "bg-red-950/30 border border-red-800/50 text-red-400"
                            }`}>
                            {message.type === "success" ? "✓" : "✗"} {message.text}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Recent Additions */}
            <Card className="bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <span>📬</span> Recent Additions
                    </CardTitle>
                    <CardDescription>Items added in this session</CardDescription>
                </CardHeader>
                <CardContent>
                    {recentItems.length === 0 ? (
                        <div className="py-8 text-center">
                            <div className="text-4xl mb-3">📭</div>
                            <p className="text-zinc-500">No items added yet this session</p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {recentItems.map((item) => (
                                <div
                                    key={item.id}
                                    className="flex items-center gap-4 p-4 bg-zinc-800/50 rounded-xl"
                                >
                                    <span className="text-2xl">
                                        {item.type === "link" ? "🔗" : "📝"}
                                    </span>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium text-zinc-200 truncate">
                                            {item.content}
                                        </p>
                                        <p className="text-xs text-zinc-500">{item.id}</p>
                                    </div>
                                    <span className={`text-xs px-2 py-1 rounded-full ${item.status === "pending"
                                            ? "bg-yellow-500/20 text-yellow-400"
                                            : "bg-green-500/20 text-green-400"
                                        }`}>
                                        {item.status}
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
