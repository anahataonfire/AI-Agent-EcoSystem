"use client";

import { useState, useRef, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
            content: "Hello! I'm your Advisor. I can help you categorize content, suggest priorities, and learn your preferences. What would you like to discuss?",
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

        // Simulate advisor response (would call API in real implementation)
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
        <div className="flex flex-col h-[calc(100vh-8rem)]">
            <div className="mb-4">
                <h1 className="text-3xl font-bold">🧠 Advisor Chat</h1>
                <p className="text-zinc-400 mt-1">Your personal learning assistant</p>
            </div>

            <Card className="flex-1 bg-zinc-900 border-zinc-800 flex flex-col overflow-hidden">
                <CardContent className="flex-1 overflow-y-auto p-4 space-y-4">
                    {messages.map((msg, i) => (
                        <MessageBubble key={i} message={msg} />
                    ))}
                    {loading && (
                        <div className="flex items-center gap-2 text-zinc-500">
                            <span className="animate-pulse">🧠 Thinking...</span>
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </CardContent>

                <div className="p-4 border-t border-zinc-800">
                    <div className="flex gap-2">
                        <Input
                            placeholder="Ask about content, priorities, or preferences..."
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => e.key === "Enter" && !loading && sendMessage()}
                            className="bg-zinc-800 border-zinc-700"
                        />
                        <Button onClick={sendMessage} disabled={loading || !input.trim()}>
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
            <div
                className={`max-w-[80%] p-3 rounded-lg ${isUser
                        ? "bg-blue-600 text-white"
                        : "bg-zinc-800 text-zinc-100"
                    }`}
            >
                <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                <p className="text-xs opacity-50 mt-1">
                    {new Date(message.timestamp).toLocaleTimeString()}
                </p>
            </div>
        </div>
    );
}

function getAdvisorResponse(input: string): string {
    const lower = input.toLowerCase();

    if (lower.includes("priority") || lower.includes("prioritize")) {
        return "Based on your recent activity, I'd suggest prioritizing:\n\n1. **Trading research** - You've been engaging heavily with market analysis\n2. **System maintenance** - Some regression tests need attention\n3. **Content curation** - Your inbox has pending items\n\nWould you like me to create tasks for any of these?";
    }

    if (lower.includes("learn") || lower.includes("preference")) {
        return "I've learned a few things about your preferences:\n\n• You prefer grounded, evidence-based reports\n• You're interested in crypto and prediction markets\n• You value concise summaries over lengthy analysis\n\nI use these to personalize my suggestions. Want to refine any of these?";
    }

    if (lower.includes("help") || lower.includes("what can you")) {
        return "I can help you with:\n\n• **Content categorization** - Organize incoming articles/links\n• **Priority suggestions** - Based on your patterns\n• **Preference tracking** - Learning what you find useful\n• **Research assistance** - Grounded answers to questions\n\nJust ask!";
    }

    return "I understand you're asking about: \"" + input + "\"\n\nTo give you a grounded answer, I'd need to search through your library and evidence store. Would you like me to run a research query on this topic?";
}
