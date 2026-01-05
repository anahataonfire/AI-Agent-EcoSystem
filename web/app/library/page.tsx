"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

interface LibraryItem {
    id: string;
    title: string;
    summary: string;
    categories: string[];
    source_url?: string;
    created_at: string;
}

export default function LibraryPage() {
    const [search, setSearch] = useState("");
    const [items, setItems] = useState<LibraryItem[]>([]);

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold">Library</h1>
                <p className="text-zinc-400 mt-1">All your curated knowledge, searchable</p>
            </div>

            <div className="flex gap-4">
                <Input
                    placeholder="Search your library..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="bg-zinc-800 border-zinc-700 max-w-md"
                />
            </div>

            {items.length === 0 ? (
                <Card className="bg-zinc-900 border-zinc-800">
                    <CardContent className="py-12 text-center">
                        <div className="text-4xl mb-4">📚</div>
                        <h3 className="text-lg font-medium">Your library is empty</h3>
                        <p className="text-zinc-500 mt-2">
                            Add links or notes in the Inbox to start building your knowledge base.
                        </p>
                    </CardContent>
                </Card>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {items.map((item) => (
                        <Card key={item.id} className="bg-zinc-900 border-zinc-800 hover:border-zinc-700 transition-colors cursor-pointer">
                            <CardHeader>
                                <CardTitle className="text-base">{item.title}</CardTitle>
                                <CardDescription className="line-clamp-2">{item.summary}</CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div className="flex flex-wrap gap-1">
                                    {item.categories.map((cat) => (
                                        <span key={cat} className="text-xs bg-zinc-800 px-2 py-1 rounded">
                                            {cat}
                                        </span>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}
