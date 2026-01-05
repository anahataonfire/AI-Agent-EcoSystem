"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const navItems = [
    { href: "/", label: "Dashboard", icon: "🏠" },
    { href: "/inbox", label: "Inbox", icon: "📥" },
    { href: "/library", label: "Library", icon: "📚" },
    { href: "/planner", label: "Planner", icon: "📋" },
    { href: "/research", label: "Research", icon: "🔬" },
    { href: "/learning", label: "Learning", icon: "🧠" },
];

export function Navigation() {
    const pathname = usePathname();

    return (
        <nav className="w-56 border-r border-zinc-800 bg-zinc-900/50 p-4 flex flex-col gap-1">
            <div className="mb-6">
                <h1 className="text-xl font-bold text-zinc-50">DTL</h1>
                <p className="text-xs text-zinc-500">Personal Intelligence</p>
            </div>

            {navItems.map((item) => (
                <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                        "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                        pathname === item.href
                            ? "bg-zinc-800 text-zinc-50"
                            : "text-zinc-400 hover:text-zinc-50 hover:bg-zinc-800/50"
                    )}
                >
                    <span>{item.icon}</span>
                    <span>{item.label}</span>
                </Link>
            ))}

            <div className="mt-auto pt-4 border-t border-zinc-800">
                <div className="px-3 py-2 text-xs text-zinc-500">
                    v3.0 • Grounded AI
                </div>
            </div>
        </nav>
    );
}
