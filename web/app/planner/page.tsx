"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
    DialogFooter,
    DialogClose,
} from "@/components/ui/dialog";

interface Task {
    id: string;
    title: string;
    priority: number;
    status: string;
    category?: string;
    created_at: string;
}

const PRIORITY_CONFIG = {
    1: { label: "P1 - Urgent", color: "from-red-500 to-orange-500", bg: "bg-red-500/20 border-red-500/30" },
    2: { label: "P2 - High", color: "from-yellow-500 to-amber-500", bg: "bg-yellow-500/20 border-yellow-500/30" },
    3: { label: "P3 - Normal", color: "from-blue-500 to-cyan-500", bg: "bg-blue-500/20 border-blue-500/30" },
};

export default function PlannerPage() {
    const [tasks, setTasks] = useState<Task[]>([]);
    const [loading, setLoading] = useState(false);
    const [newTaskTitle, setNewTaskTitle] = useState("");
    const [newTaskPriority, setNewTaskPriority] = useState(2);
    const [showAddDialog, setShowAddDialog] = useState(false);

    const fetchTasks = async () => {
        setLoading(true);
        try {
            const res = await fetch("http://localhost:8000/planner/projects", {
                headers: { "X-API-Key": "dev-token-change-me" },
            });
            if (!res.ok) throw new Error("Failed to fetch");
            const data = await res.json();
            setTasks(data);
        } catch {
            // Use demo data
            setTasks([
                { id: "1", title: "Review earnings data integration", priority: 1, status: "in_progress", created_at: new Date().toISOString() },
                { id: "2", title: "Set up Polymarket auto-scanner", priority: 1, status: "todo", created_at: new Date().toISOString() },
                { id: "3", title: "Document API endpoints", priority: 2, status: "todo", created_at: new Date().toISOString() },
                { id: "4", title: "Implement feedback learning loop", priority: 2, status: "in_progress", created_at: new Date().toISOString() },
                { id: "5", title: "Add TanStack Table", priority: 3, status: "done", created_at: new Date().toISOString() },
            ]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchTasks();
    }, []);

    const addTask = async () => {
        if (!newTaskTitle.trim()) return;
        try {
            await fetch(`http://localhost:8000/planner/task?title=${encodeURIComponent(newTaskTitle)}&priority=${newTaskPriority}`, {
                method: "POST",
                headers: { "X-API-Key": "dev-token-change-me" },
            });
            setNewTaskTitle("");
            setShowAddDialog(false);
            fetchTasks();
        } catch {
            // Add locally for demo
            setTasks([...tasks, {
                id: Date.now().toString(),
                title: newTaskTitle,
                priority: newTaskPriority,
                status: "todo",
                created_at: new Date().toISOString(),
            }]);
            setNewTaskTitle("");
            setShowAddDialog(false);
        }
    };

    const todoTasks = tasks.filter((t) => t.status === "todo");
    const inProgressTasks = tasks.filter((t) => t.status === "in_progress");
    const doneTasks = tasks.filter((t) => t.status === "done");

    return (
        <div className="space-y-8">
            {/* Header */}
            <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-r from-violet-500/10 via-purple-500/10 to-fuchsia-500/10 rounded-2xl blur-xl" />
                <div className="relative bg-zinc-900/80 backdrop-blur-sm border border-zinc-800 rounded-2xl p-6 flex items-center justify-between">
                    <div>
                        <h1 className="text-4xl font-bold bg-gradient-to-r from-violet-400 via-purple-400 to-fuchsia-400 bg-clip-text text-transparent">
                            Planner
                        </h1>
                        <p className="text-zinc-400 mt-2">Organize your projects and track progress</p>
                    </div>
                    <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
                        <DialogTrigger asChild>
                            <Button className="bg-gradient-to-r from-violet-500 to-purple-500 hover:from-violet-600 hover:to-purple-600 rounded-xl px-6">
                                + Add Task
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="bg-zinc-900 border-zinc-800">
                            <DialogHeader>
                                <DialogTitle>Add New Task</DialogTitle>
                                <DialogDescription>Create a new task to track</DialogDescription>
                            </DialogHeader>
                            <div className="space-y-4 py-4">
                                <Input
                                    placeholder="Task title..."
                                    value={newTaskTitle}
                                    onChange={(e) => setNewTaskTitle(e.target.value)}
                                    className="bg-zinc-800 border-zinc-700"
                                />
                                <div className="flex gap-2">
                                    {[1, 2, 3].map((p) => (
                                        <Button
                                            key={p}
                                            variant={newTaskPriority === p ? "default" : "outline"}
                                            size="sm"
                                            onClick={() => setNewTaskPriority(p)}
                                            className={newTaskPriority === p ? `bg-gradient-to-r ${PRIORITY_CONFIG[p as keyof typeof PRIORITY_CONFIG].color}` : "border-zinc-700"}
                                        >
                                            {PRIORITY_CONFIG[p as keyof typeof PRIORITY_CONFIG].label}
                                        </Button>
                                    ))}
                                </div>
                            </div>
                            <DialogFooter>
                                <DialogClose asChild>
                                    <Button variant="ghost">Cancel</Button>
                                </DialogClose>
                                <Button onClick={addTask} className="bg-gradient-to-r from-violet-500 to-purple-500">
                                    Add Task
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                </div>
            </div>

            {/* Kanban Board */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <KanbanColumn title="📋 To Do" tasks={todoTasks} color="from-blue-500 to-cyan-500" />
                <KanbanColumn title="⚡ In Progress" tasks={inProgressTasks} color="from-violet-500 to-purple-500" />
                <KanbanColumn title="✅ Done" tasks={doneTasks} color="from-emerald-500 to-teal-500" />
            </div>
        </div>
    );
}

function KanbanColumn({ title, tasks, color }: { title: string; tasks: Task[]; color: string }) {
    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h2 className={`text-lg font-semibold bg-gradient-to-r ${color} bg-clip-text text-transparent`}>
                    {title}
                </h2>
                <span className="text-sm text-zinc-500">{tasks.length}</span>
            </div>
            <div className="space-y-3">
                {tasks.length === 0 ? (
                    <div className="bg-zinc-900/50 border border-zinc-800 border-dashed rounded-xl p-8 text-center">
                        <p className="text-sm text-zinc-600">No tasks</p>
                    </div>
                ) : (
                    tasks.map((task) => <TaskCard key={task.id} task={task} />)
                )}
            </div>
        </div>
    );
}

function TaskCard({ task }: { task: Task }) {
    const config = PRIORITY_CONFIG[task.priority as keyof typeof PRIORITY_CONFIG];

    return (
        <Card className="bg-zinc-900/80 backdrop-blur-sm border-zinc-800 hover:border-zinc-700 transition-all rounded-xl cursor-pointer group">
            <CardContent className="p-4">
                <div className="flex items-start gap-3">
                    <span className={`shrink-0 text-xs px-2 py-1 rounded-full border ${config.bg}`}>
                        P{task.priority}
                    </span>
                    <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-zinc-200 group-hover:text-white transition-colors">
                            {task.title}
                        </p>
                        {task.category && (
                            <span className="text-xs text-zinc-500">{task.category}</span>
                        )}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
