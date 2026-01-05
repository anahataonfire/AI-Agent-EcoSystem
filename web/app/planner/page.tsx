"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface Task {
    id: string;
    title: string;
    priority: 1 | 2 | 3;
    status: "todo" | "in_progress" | "done";
    category?: string;
}

const priorityColors = {
    1: "bg-red-500/20 text-red-400 border-red-500/50",
    2: "bg-yellow-500/20 text-yellow-400 border-yellow-500/50",
    3: "bg-blue-500/20 text-blue-400 border-blue-500/50",
};

export default function PlannerPage() {
    const [newTask, setNewTask] = useState("");
    const [tasks, setTasks] = useState<Task[]>([]);

    const addTask = () => {
        if (!newTask) return;
        setTasks([
            ...tasks,
            {
                id: Date.now().toString(),
                title: newTask,
                priority: 2,
                status: "todo",
            },
        ]);
        setNewTask("");
    };

    const todoTasks = tasks.filter((t) => t.status === "todo");
    const inProgressTasks = tasks.filter((t) => t.status === "in_progress");
    const doneTasks = tasks.filter((t) => t.status === "done");

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold">Planner</h1>
                <p className="text-zinc-400 mt-1">Organize tasks and projects across any domain</p>
            </div>

            <div className="flex gap-2">
                <Input
                    placeholder="Add a new task..."
                    value={newTask}
                    onChange={(e) => setNewTask(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && addTask()}
                    className="bg-zinc-800 border-zinc-700 max-w-md"
                />
                <Button onClick={addTask}>Add</Button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <Card className="bg-zinc-900 border-zinc-800">
                    <CardHeader>
                        <CardTitle className="text-sm flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-zinc-500"></span>
                            To Do ({todoTasks.length})
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                        {todoTasks.length === 0 ? (
                            <p className="text-zinc-500 text-sm">No tasks</p>
                        ) : (
                            todoTasks.map((task) => (
                                <TaskCard key={task.id} task={task} />
                            ))
                        )}
                    </CardContent>
                </Card>

                <Card className="bg-zinc-900 border-zinc-800">
                    <CardHeader>
                        <CardTitle className="text-sm flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-yellow-500"></span>
                            In Progress ({inProgressTasks.length})
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                        {inProgressTasks.length === 0 ? (
                            <p className="text-zinc-500 text-sm">No tasks</p>
                        ) : (
                            inProgressTasks.map((task) => (
                                <TaskCard key={task.id} task={task} />
                            ))
                        )}
                    </CardContent>
                </Card>

                <Card className="bg-zinc-900 border-zinc-800">
                    <CardHeader>
                        <CardTitle className="text-sm flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-green-500"></span>
                            Done ({doneTasks.length})
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                        {doneTasks.length === 0 ? (
                            <p className="text-zinc-500 text-sm">No tasks</p>
                        ) : (
                            doneTasks.map((task) => (
                                <TaskCard key={task.id} task={task} />
                            ))
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}

function TaskCard({ task }: { task: Task }) {
    return (
        <div className="p-3 bg-zinc-800 rounded-lg border border-zinc-700">
            <div className="flex items-start gap-2">
                <span
                    className={`text-xs px-2 py-0.5 rounded border ${priorityColors[task.priority]}`}
                >
                    P{task.priority}
                </span>
                <span className="flex-1 text-sm">{task.title}</span>
            </div>
        </div>
    );
}
