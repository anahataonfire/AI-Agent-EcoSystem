"use client";

import { useState, useRef, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface Message {
    role: "user" | "advisor";
    content: string;
    timestamp: string;
}

export default function AdvisorPage() {
    const [messages, setMessages] = useState<Message[]>([
        {
            role: "advisor",
            content: "Hello! I'm your personal AI advisor. I can help you categorize content, suggest priorities, and learn your preferences over time. What would you like to discuss?",
            timestamp: new Date().toISOString(),
        },
    ]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const sendMessage = async () => {
        if (!input.trim()) return;

        const userMessage: Message = {
            role: "user",
            content: input,
            timestamp: new Date().toISOString(),
        };

        setMessages((prev) => [...prev, userMessage]);
        setInput("");
        setLoading(true);

        // Simulate advisor response
        await new Promise((resolve) => setTimeout(resolve, 1000));

        const advisorResponse: Message = {
            role: "advisor",
            content: getAdvisorResponse(input),
            timestamp: new Date().toISOString(),
        };

        setMessages((prev) => [...prev, advisorResponse]);
        setLoading(false);
    };

    return (
        <div className="flex flex-col h-[calc(100vh-6rem)]">
            {/* Header */}
            <div className="relative mb-6 shrink-0">
                <div className="absolute inset-0 bg-gradient-to-r from-pink-500/10 via-rose-500/10 to-orange-500/10 rounded-2xl blur-xl" />
                <div className="relative bg-zinc-900/80 backdrop-blur-sm border border-zinc-800 rounded-2xl p-6">
                    <h1 className="text-4xl font-bold bg-gradient-to-r from-pink-400 via-rose-400 to-orange-400 bg-clip-text text-transparent">
                        Advisor Chat
                    </h1>
                    <p className="text-zinc-400 mt-2">Your personal learning assistant that adapts to you</p>
                </div>
            </div>

            {/* Chat Container */}
            <Card className="flex-1 bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl overflow-hidden flex flex-col">
                {/* Messages */}
                <div className="flex-1 overflow-y-auto p-6 space-y-4">
                    {messages.map((msg, i) => (
                        <MessageBubble key={i} message={msg} />
                    ))}
                    {loading && (
                        <div className="flex items-center gap-3 text-zinc-500">
                            <div className="relative">
                                <div className="w-10 h-10 rounded-full bg-gradient-to-r from-pink-500 to-rose-500 flex items-center justify-center">
                                    <span className="text-lg">🧠</span>
                                </div>
                                <div className="absolute inset-0 rounded-full bg-gradient-to-r from-pink-500 to-rose-500 animate-ping opacity-30" />
                            </div>
                            <span className="text-sm">Thinking...</span>
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>

                {/* Input */}
                <div className="p-4 border-t border-zinc-800 bg-zinc-900/50">
                    <div className="flex gap-3">
                        <Input
                            placeholder="Ask about content, priorities, or preferences..."
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => e.key === "Enter" && !loading && sendMessage()}
                            className="bg-zinc-800/50 border-zinc-700 rounded-xl h-12"
                        />
                        <Button
                            onClick={sendMessage}
                            disabled={loading || !input.trim()}
                            className="h-12 px-6 rounded-xl bg-gradient-to-r from-pink-500 to-rose-500 hover:from-pink-600 hover:to-rose-600"
                        >
                            Send
                        </Button>
                    </div>
                </div>
            </Card>
        </div>
    );
}

function MessageBubble({ message }: { message: Message }) {
    const isUser = message.role === "user";

    return (
        <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
            <div className="flex items-start gap-3 max-w-[80%]">
                {!isUser && (
                    <div className="shrink-0 w-10 h-10 rounded-full bg-gradient-to-r from-pink-500 to-rose-500 flex items-center justify-center">
                        <span className="text-lg">🧠</span>
                    </div>
                )}
                <div
                    className={`p-4 rounded-2xl ${isUser
                            ? "bg-gradient-to-r from-blue-500 to-indigo-500 text-white"
                            : "bg-zinc-800 text-zinc-100"
                        }`}
                >
                    <p className="text-sm whitespace-pre-wrap leading-relaxed">{message.content}</p>
                    <p className="text-xs opacity-50 mt-2">
                        {new Date(message.timestamp).toLocaleTimeString()}
                    </p>
                </div>
                {isUser && (
                    <div className="shrink-0 w-10 h-10 rounded-full bg-gradient-to-r from-blue-500 to-indigo-500 flex items-center justify-center">
                        <span className="text-lg">👤</span>
                    </div>
                )}
            </div>
        </div>
    );
}

function getAdvisorResponse(input: string): string {
    const lower = input.toLowerCase();

    if (lower.includes("priority") || lower.includes("prioritize")) {
        return "Based on your recent activity, I'd suggest prioritizing:\n\n1. **Trading research** — You've been engaging heavily with market analysis\n2. **System maintenance** — Some regression tests need attention\n3. **Content curation** — Your inbox has pending items\n\nWould you like me to create tasks for any of these?";
    }

    if (lower.includes("learn") || lower.includes("preference")) {
        return "I've learned a few things about your preferences:\n\n• You prefer grounded, evidence-based reports\n• You're interested in crypto and prediction markets\n• You value concise summaries over lengthy analysis\n• You enjoy baking content (Paul Hollywood recipes!)\n\nI use these patterns to personalize suggestions. Would you like to refine any of these?";
    }

    if (lower.includes("help") || lower.includes("what can you")) {
        return "I can help you with:\n\n🏷️ **Content categorization** — Organize incoming articles\n⚡ **Priority suggestions** — Based on your patterns\n📈 **Learning patterns** — Track what you find useful\n🔬 **Research assistance** — Grounded answers\n\nJust ask!";
    }

    return `I understand you're asking about: "${input}"\n\nTo give you a grounded answer, I can search through your library (32 curated links + 242 evidence items). Would you like me to run a research query on this topic?`;
}
