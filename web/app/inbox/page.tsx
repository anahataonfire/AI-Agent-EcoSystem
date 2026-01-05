"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";

export default function InboxPage() {
    const [url, setUrl] = useState("");
    const [text, setText] = useState("");
    const [pending, setPending] = useState<any[]>([]);

    const addLink = async () => {
        if (!url) return;
        // TODO: Call API
        setPending([...pending, { type: "link", content: url, id: Date.now() }]);
        setUrl("");
    };

    const addNote = async () => {
        if (!text) return;
        // TODO: Call API
        setPending([...pending, { type: "note", content: text, id: Date.now() }]);
        setText("");
    };

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold">Inbox</h1>
                <p className="text-zinc-400 mt-1">Drop links, paste text, or add quick notes</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <Card className="bg-zinc-900 border-zinc-800">
                    <CardHeader>
                        <CardTitle>Add Link</CardTitle>
                        <CardDescription>Paste a URL to summarize and curate</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <Input
                            placeholder="https://..."
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                            className="bg-zinc-800 border-zinc-700"
                        />
                        <Button onClick={addLink} className="w-full">
                            Add to Inbox
                        </Button>
                    </CardContent>
                </Card>

                <Card className="bg-zinc-900 border-zinc-800">
                    <CardHeader>
                        <CardTitle>Quick Note</CardTitle>
                        <CardDescription>Capture ideas, text, or thoughts</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <Textarea
                            placeholder="Type or paste anything..."
                            value={text}
                            onChange={(e) => setText(e.target.value)}
                            className="bg-zinc-800 border-zinc-700 min-h-[100px]"
                        />
                        <Button onClick={addNote} className="w-full">
                            Add Note
                        </Button>
                    </CardContent>
                </Card>
            </div>

            <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader>
                    <CardTitle>Pending Items ({pending.length})</CardTitle>
                    <CardDescription>Items waiting to be processed</CardDescription>
                </CardHeader>
                <CardContent>
                    {pending.length === 0 ? (
                        <p className="text-zinc-500 text-sm">No pending items. Add something above!</p>
                    ) : (
                        <div className="space-y-2">
                            {pending.map((item) => (
                                <div
                                    key={item.id}
                                    className="flex items-center gap-3 p-3 bg-zinc-800 rounded-lg"
                                >
                                    <span>{item.type === "link" ? "🔗" : "📝"}</span>
                                    <span className="flex-1 text-sm truncate">{item.content}</span>
                                    <span className="text-xs text-zinc-500">Processing...</span>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
