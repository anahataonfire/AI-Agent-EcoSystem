"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function LearningPage() {
    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold">Learning</h1>
                <p className="text-zinc-400 mt-1">How the system adapts to your preferences</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card className="bg-zinc-900 border-zinc-800">
                    <CardHeader>
                        <CardTitle>Feedback Given</CardTitle>
                        <CardDescription>Your input shapes the system</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="text-3xl font-bold">0</div>
                        <p className="text-sm text-zinc-500">total feedback signals</p>
                    </CardContent>
                </Card>

                <Card className="bg-zinc-900 border-zinc-800">
                    <CardHeader>
                        <CardTitle>Top Categories</CardTitle>
                        <CardDescription>Topics you engage with most</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <p className="text-sm text-zinc-500">No data yet</p>
                    </CardContent>
                </Card>

                <Card className="bg-zinc-900 border-zinc-800">
                    <CardHeader>
                        <CardTitle>Grounding Accuracy</CardTitle>
                        <CardDescription>How well claims are supported</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="text-3xl font-bold">—%</div>
                        <p className="text-sm text-zinc-500">average grounding score</p>
                    </CardContent>
                </Card>
            </div>

            <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader>
                    <CardTitle>Preference History</CardTitle>
                    <CardDescription>Recent feedback and how it affected the system</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="py-8 text-center">
                        <div className="text-4xl mb-4">🧠</div>
                        <h3 className="text-lg font-medium">No learning data yet</h3>
                        <p className="text-zinc-500 mt-2">
                            Use 👍 and 👎 buttons on research reports to teach the system your preferences.
                        </p>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
