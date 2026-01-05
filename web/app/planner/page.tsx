"use client";

import { useState, useEffect, useMemo } from "react";
import {
    DndContext,
    DragOverlay,
    closestCenter,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
    DragStartEvent,
    DragEndEvent,
    DragOverEvent,
    useDroppable,
} from "@dnd-kit/core";
import {
    arrayMove,
    SortableContext,
    sortableKeyboardCoordinates,
    verticalListSortingStrategy,
    useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Card, CardContent } from "@/components/ui/card";
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

type ColumnId = "todo" | "in_progress" | "done";

const COLUMNS: { id: ColumnId; title: string; icon: string; color: string }[] = [
    { id: "todo", title: "To Do", icon: "📋", color: "from-blue-500 to-cyan-500" },
    { id: "in_progress", title: "In Progress", icon: "⚡", color: "from-violet-500 to-purple-500" },
    { id: "done", title: "Done", icon: "✅", color: "from-emerald-500 to-teal-500" },
];

const PRIORITY_CONFIG = {
    1: { label: "P1", color: "bg-red-500/20 border-red-500/30 text-red-400" },
    2: { label: "P2", color: "bg-yellow-500/20 border-yellow-500/30 text-yellow-400" },
    3: { label: "P3", color: "bg-blue-500/20 border-blue-500/30 text-blue-400" },
};

export default function PlannerPage() {
    const [tasks, setTasks] = useState<Task[]>([]);
    const [loading, setLoading] = useState(true);
    const [activeTask, setActiveTask] = useState<Task | null>(null);
    const [showAddDialog, setShowAddDialog] = useState(false);
    const [newTaskTitle, setNewTaskTitle] = useState("");
    const [newTaskPriority, setNewTaskPriority] = useState(2);

    const sensors = useSensors(
        useSensor(PointerSensor, {
            activationConstraint: { distance: 5 },
        }),
        useSensor(KeyboardSensor, {
            coordinateGetter: sortableKeyboardCoordinates,
        })
    );

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
            // Demo data for development
            setTasks([
                { id: "demo-1", title: "Review earnings data integration", priority: 1, status: "in_progress", created_at: new Date().toISOString() },
                { id: "demo-2", title: "Set up Polymarket auto-scanner", priority: 1, status: "todo", created_at: new Date().toISOString() },
                { id: "demo-3", title: "Document API endpoints", priority: 2, status: "todo", created_at: new Date().toISOString() },
                { id: "demo-4", title: "Implement feedback learning loop", priority: 2, status: "in_progress", created_at: new Date().toISOString() },
                { id: "demo-5", title: "Add TanStack Table", priority: 3, status: "done", created_at: new Date().toISOString() },
            ]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchTasks();
    }, []);

    const tasksByColumn = useMemo(() => {
        return {
            todo: tasks.filter((t) => t.status === "todo"),
            in_progress: tasks.filter((t) => t.status === "in_progress"),
            done: tasks.filter((t) => t.status === "done"),
        };
    }, [tasks]);

    const findColumn = (id: string): ColumnId | null => {
        // Check if id is a column id
        if (["todo", "in_progress", "done"].includes(id)) {
            return id as ColumnId;
        }
        // Find which column the task belongs to
        const task = tasks.find((t) => t.id === id);
        return task ? (task.status as ColumnId) : null;
    };

    const handleDragStart = (event: DragStartEvent) => {
        const task = tasks.find((t) => t.id === event.active.id);
        setActiveTask(task || null);
    };

    const handleDragOver = (event: DragOverEvent) => {
        const { active, over } = event;
        if (!over) return;

        const activeId = active.id as string;
        const overId = over.id as string;

        const activeColumn = findColumn(activeId);
        const overColumn = findColumn(overId);

        if (!activeColumn || !overColumn || activeColumn === overColumn) {
            return;
        }

        // Move task to new column
        setTasks((prev) =>
            prev.map((t) =>
                t.id === activeId ? { ...t, status: overColumn } : t
            )
        );
    };

    const handleDragEnd = async (event: DragEndEvent) => {
        const { active, over } = event;
        setActiveTask(null);

        if (!over) return;

        const activeId = active.id as string;
        const overId = over.id as string;

        const activeColumn = findColumn(activeId);
        const overColumn = findColumn(overId);

        if (!activeColumn || !overColumn) return;

        // If dropped on different column, update status
        if (activeColumn !== overColumn) {
            setTasks((prev) =>
                prev.map((t) =>
                    t.id === activeId ? { ...t, status: overColumn } : t
                )
            );
        }

        // Persist the change
        const finalTask = tasks.find((t) => t.id === activeId);
        if (finalTask) {
            try {
                await fetch(
                    `http://localhost:8000/planner/task/${activeId}/status?status=${overColumn}`,
                    {
                        method: "PATCH",
                        headers: { "X-API-Key": "dev-token-change-me" },
                    }
                );
            } catch {
                // Silently fail for demo
            }
        }

        // Handle reordering within the same column
        if (activeId !== overId && activeColumn === overColumn) {
            const columnTasks = tasks.filter((t) => t.status === activeColumn);
            const oldIndex = columnTasks.findIndex((t) => t.id === activeId);
            const newIndex = columnTasks.findIndex((t) => t.id === overId);

            if (oldIndex !== -1 && newIndex !== -1) {
                const reordered = arrayMove(columnTasks, oldIndex, newIndex);
                setTasks((prev) => {
                    const otherTasks = prev.filter((t) => t.status !== activeColumn);
                    return [...otherTasks, ...reordered];
                });
            }
        }
    };

    const addTask = async () => {
        if (!newTaskTitle.trim()) return;
        try {
            const res = await fetch(
                `http://localhost:8000/planner/task?title=${encodeURIComponent(newTaskTitle)}&priority=${newTaskPriority}`,
                {
                    method: "POST",
                    headers: { "X-API-Key": "dev-token-change-me" },
                }
            );
            if (res.ok) {
                setNewTaskTitle("");
                setShowAddDialog(false);
                fetchTasks();
            }
        } catch {
            // Add locally for demo
            setTasks([
                ...tasks,
                {
                    id: `task_${Date.now()}`,
                    title: newTaskTitle,
                    priority: newTaskPriority,
                    status: "todo",
                    created_at: new Date().toISOString(),
                },
            ]);
            setNewTaskTitle("");
            setShowAddDialog(false);
        }
    };

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
                        <p className="text-zinc-400 mt-2">
                            Drag tasks between columns • {tasks.length} total tasks
                        </p>
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
                                    onKeyDown={(e) => e.key === "Enter" && addTask()}
                                    className="bg-zinc-800 border-zinc-700"
                                />
                                <div className="flex gap-2">
                                    {[1, 2, 3].map((p) => (
                                        <Button
                                            key={p}
                                            variant={newTaskPriority === p ? "default" : "outline"}
                                            size="sm"
                                            onClick={() => setNewTaskPriority(p)}
                                            className={
                                                newTaskPriority === p
                                                    ? PRIORITY_CONFIG[p as keyof typeof PRIORITY_CONFIG].color
                                                    : "border-zinc-700"
                                            }
                                        >
                                            P{p}
                                        </Button>
                                    ))}
                                </div>
                            </div>
                            <DialogFooter>
                                <DialogClose asChild>
                                    <Button variant="ghost">Cancel</Button>
                                </DialogClose>
                                <Button
                                    onClick={addTask}
                                    className="bg-gradient-to-r from-violet-500 to-purple-500"
                                >
                                    Add Task
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                </div>
            </div>

            {/* Library Queue Section */}
            <LibraryQueueSection onAddToBoard={async (item) => {
                // Create a task from the library item
                try {
                    const res = await fetch(
                        `http://localhost:8000/planner/task?title=${encodeURIComponent(item.title)}&priority=2`,
                        {
                            method: "POST",
                            headers: { "X-API-Key": "dev-token-change-me" },
                        }
                    );
                    if (res.ok) {
                        // Update library item status
                        await fetch(`http://localhost:8000/content/${item.id}/planner-status?status=in_progress`, {
                            method: "PATCH",
                            headers: { "X-API-Key": "dev-token-change-me" },
                        });
                        fetchTasks();
                    }
                } catch {
                    // Add locally for demo
                    setTasks([
                        ...tasks,
                        {
                            id: `task_${Date.now()}`,
                            title: item.title,
                            priority: 2,
                            status: "todo",
                            category: item.categories?.[0],
                            created_at: new Date().toISOString(),
                        },
                    ]);
                }
            }} />

            {/* Kanban Board */}
            <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragStart={handleDragStart}
                onDragOver={handleDragOver}
                onDragEnd={handleDragEnd}
            >
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {COLUMNS.map((column) => (
                        <DroppableColumn
                            key={column.id}
                            column={column}
                            tasks={tasksByColumn[column.id]}
                        />
                    ))}
                </div>

                <DragOverlay>
                    {activeTask ? <TaskCard task={activeTask} isDragging /> : null}
                </DragOverlay>
            </DndContext>
        </div>
    );
}

function DroppableColumn({
    column,
    tasks,
}: {
    column: { id: ColumnId; title: string; icon: string; color: string };
    tasks: Task[];
}) {
    const { setNodeRef, isOver } = useDroppable({
        id: column.id,
    });

    const taskIds = tasks.map((t) => t.id);

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h2
                    className={`text-lg font-semibold bg-gradient-to-r ${column.color} bg-clip-text text-transparent flex items-center gap-2`}
                >
                    <span>{column.icon}</span>
                    {column.title}
                </h2>
                <span className="text-sm text-zinc-500 bg-zinc-800 px-2.5 py-1 rounded-full">
                    {tasks.length}
                </span>
            </div>

            <SortableContext items={taskIds} strategy={verticalListSortingStrategy}>
                <div
                    ref={setNodeRef}
                    className={`min-h-[200px] rounded-2xl p-3 space-y-3 transition-all ${isOver
                        ? "bg-purple-500/10 border-2 border-purple-500/50"
                        : "bg-zinc-900/30 border border-zinc-800 border-dashed"
                        }`}
                >
                    {tasks.length === 0 ? (
                        <div className="flex items-center justify-center h-[180px] text-zinc-600">
                            <p className="text-sm">Drop tasks here</p>
                        </div>
                    ) : (
                        tasks.map((task) => <SortableTaskCard key={task.id} task={task} />)
                    )}
                </div>
            </SortableContext>
        </div>
    );
}

function SortableTaskCard({ task }: { task: Task }) {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging,
    } = useSortable({ id: task.id });

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
    };

    return (
        <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
            <TaskCard task={task} isDragging={isDragging} />
        </div>
    );
}

function TaskCard({ task, isDragging = false }: { task: Task; isDragging?: boolean }) {
    const config = PRIORITY_CONFIG[task.priority as keyof typeof PRIORITY_CONFIG] || PRIORITY_CONFIG[2];

    return (
        <Card
            className={`bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-xl cursor-grab active:cursor-grabbing transition-all ${isDragging
                ? "shadow-xl shadow-purple-500/20 scale-105 rotate-1 border-purple-500/50"
                : "hover:border-zinc-600"
                }`}
        >
            <CardContent className="p-4">
                <div className="flex items-start gap-3">
                    <span
                        className={`shrink-0 text-xs px-2 py-1 rounded-full border ${config.color}`}
                    >
                        {config.label}
                    </span>
                    <p className="text-sm font-medium text-zinc-200 leading-relaxed">
                        {task.title}
                    </p>
                </div>
            </CardContent>
        </Card>
    );
}

interface LibraryItem {
    id: string;
    title: string;
    summary: string;
    categories: string[];
    planner_status: string | null;
}

function LibraryQueueSection({ onAddToBoard }: { onAddToBoard: (item: LibraryItem) => void }) {
    const [items, setItems] = useState<LibraryItem[]>([]);
    const [collapsed, setCollapsed] = useState(false);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchQueuedItems = async () => {
            try {
                const res = await fetch("http://localhost:8000/content/browse?planner_status=queued", {
                    headers: { "X-API-Key": "dev-token-change-me" },
                });
                if (res.ok) {
                    const data = await res.json();
                    setItems(data);
                }
            } catch {
                // Silently fail
            } finally {
                setLoading(false);
            }
        };
        fetchQueuedItems();
    }, []);

    const handleAddToBoard = (item: LibraryItem) => {
        onAddToBoard(item);
        // Remove from local list
        setItems(prev => prev.filter(i => i.id !== item.id));
    };

    if (loading) return null;
    if (items.length === 0) return null;

    return (
        <div className="bg-zinc-900/60 border border-violet-500/20 rounded-xl overflow-hidden">
            <button
                onClick={() => setCollapsed(!collapsed)}
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-zinc-800/50 transition-colors"
            >
                <div className="flex items-center gap-2">
                    <span className="text-lg">📚</span>
                    <span className="font-medium text-violet-300">From Library</span>
                    <span className="text-xs bg-violet-500/20 text-violet-300 px-2 py-0.5 rounded-full">
                        {items.length} queued
                    </span>
                </div>
                <span className="text-zinc-500">{collapsed ? "▶" : "▼"}</span>
            </button>

            {!collapsed && (
                <div className="px-4 pb-4 space-y-2">
                    {items.map(item => (
                        <div
                            key={item.id}
                            className="flex items-center gap-3 bg-zinc-800/50 rounded-lg p-3 hover:bg-zinc-800 transition-colors"
                        >
                            {/* Category badges */}
                            <div className="flex gap-1 shrink-0">
                                {item.categories.slice(0, 2).map(cat => (
                                    <span
                                        key={cat}
                                        className="text-[10px] bg-purple-500/30 text-purple-200 px-2 py-0.5 rounded-full"
                                    >
                                        {cat}
                                    </span>
                                ))}
                            </div>

                            {/* Title */}
                            <p className="flex-1 text-sm text-zinc-300 truncate">{item.title}</p>

                            {/* Add to Board button */}
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleAddToBoard(item)}
                                className="shrink-0 h-7 text-xs text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/10"
                            >
                                + Add to Board
                            </Button>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
