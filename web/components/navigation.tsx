"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import Image from "next/image";

const navItems = [
    { href: "/", label: "Dashboard", icon: "🏠" },
    { href: "/inbox", label: "Inbox", icon: "📥" },
    { href: "/library", label: "Library", icon: "📚" },
    { href: "/planner", label: "Planner", icon: "📋" },
    { href: "/research", label: "Research", icon: "🔬" },
    { href: "/learning", label: "Learning", icon: "📈" },
    { href: "/mission", label: "Mission Control", icon: "🚀" },
    { href: "/polymarket", label: "Polymarket", icon: "🎯" },
    { href: "/hangar", label: "The Hangar", icon: "🛫" },
    { href: "/architecture", label: "Architecture", icon: "🏗️" },
    { href: "/advisor", label: "Advisor", icon: "🧠" },
];

export function Navigation() {
    const pathname = usePathname();

    return (
        <aside className="w-64 bg-zinc-900/80 backdrop-blur-xl border-r border-zinc-800 flex flex-col fixed inset-y-0 left-0 z-50">
            {/* Brand Header */}
            <div className="p-6 border-b border-zinc-800">
                <Link href="/" className="flex items-center gap-3 group">
                    <div className="relative">
                        <div className="absolute inset-0 bg-gradient-to-r from-purple-500 to-cyan-500 rounded-xl blur-md opacity-50 group-hover:opacity-75 transition-opacity" />
                        <div className="relative w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500/20 to-cyan-500/20 border border-zinc-700 flex items-center justify-center overflow-hidden">
                            <Image
                                src="/logo.png"
                                alt="DTL"
                                width={32}
                                height={32}
                                className="object-contain"
                            />
                        </div>
                    </div>
                    <div>
                        <h1 className="font-bold text-lg bg-gradient-to-r from-purple-400 to-cyan-400 bg-clip-text text-transparent">
                            DTL
                        </h1>
                        <p className="text-[10px] text-zinc-500 uppercase tracking-wider">
                            Personal Intelligence
                        </p>
                    </div>
                </Link>
            </div>

            {/* Navigation Links */}
            <nav className="flex-1 overflow-y-auto py-4 px-3">
                <div className="space-y-1">
                    {navItems.map((item) => {
                        const isActive = pathname === item.href;
                        return (
                            <Link
                                key={item.href}
                                href={item.href}
                                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all group ${isActive
                                        ? "bg-gradient-to-r from-purple-500/20 to-blue-500/20 border border-purple-500/30 text-white"
                                        : "text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/50"
                                    }`}
                            >
                                <span className="text-lg group-hover:scale-110 transition-transform">{item.icon}</span>
                                <span className="text-sm font-medium">{item.label}</span>
                                {isActive && (
                                    <div className="ml-auto w-1.5 h-1.5 rounded-full bg-gradient-to-r from-purple-400 to-cyan-400" />
                                )}
                            </Link>
                        );
                    })}
                </div>
            </nav>

            {/* Footer */}
            <div className="p-4 border-t border-zinc-800">
                <div className="flex items-center gap-2 text-xs text-zinc-600">
                    <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                    <span>System Online</span>
                </div>
                <p className="text-[10px] text-zinc-700 mt-1">v3.0.0 • DTL Platform</p>
            </div>
        </aside>
    );
}
