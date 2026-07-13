'use client';

import { useState, useEffect } from 'react';

interface Listing {
    id: string;
    title: string;
    url: string;
    neighborhoodLabel: string;
    rentBase: number;
    rentAllInEstimate: number | null;
    scoreTotal: number;
    status: string;
}

const COLUMNS = [
    { id: 'new', label: 'New', icon: '✨', color: 'border-emerald-500/50' },
    { id: 'shortlisted', label: 'Shortlist', icon: '⭐', color: 'border-blue-500/50' },
    { id: 'contacted', label: 'Contacted', icon: '📧', color: 'border-amber-500/50' },
    { id: 'touring', label: 'Touring', icon: '🏃', color: 'border-violet-500/50' },
    { id: 'applied', label: 'Applied', icon: '📝', color: 'border-pink-500/50' },
    { id: 'rejected', label: 'Rejected', icon: '❌', color: 'border-slate-500/50' },
];

export default function PipelinePage() {
    const [listings, setListings] = useState<Listing[]>([]);
    const [loading, setLoading] = useState(true);
    const [draggedId, setDraggedId] = useState<string | null>(null);

    useEffect(() => {
        fetchListings();
    }, []);

    const fetchListings = async () => {
        try {
            const res = await fetch('/api/listings');
            const data = await res.json();
            setListings(data.listings || []);
        } catch (error) {
            console.error('Failed to fetch:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleDragStart = (id: string) => {
        setDraggedId(id);
    };

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
    };

    const handleDrop = async (status: string) => {
        if (!draggedId) return;

        // Optimistic update
        setListings((prev) =>
            prev.map((l) => (l.id === draggedId ? { ...l, status } : l))
        );
        setDraggedId(null);

        // API update
        try {
            await fetch('/api/listings', {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: draggedId, status }),
            });
        } catch (error) {
            console.error('Failed to update:', error);
            fetchListings(); // Revert on error
        }
    };

    const getListingsByStatus = (status: string) =>
        listings.filter((l) => l.status === status);

    if (loading) {
        return (
            <div className="container mx-auto px-4 py-6 flex items-center justify-center min-h-[60vh]">
                <div className="text-slate-400">Loading pipeline...</div>
            </div>
        );
    }

    return (
        <div className="container mx-auto px-4 py-6">
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-slate-100">Pipeline</h1>
                <p className="text-slate-400">Drag listings between columns to update their status</p>
            </div>

            <div className="grid grid-cols-6 gap-4 overflow-x-auto">
                {COLUMNS.map((column) => (
                    <div
                        key={column.id}
                        className={`kanban-column bg-slate-800/50 border-t-4 ${column.color} rounded-xl p-3`}
                        onDragOver={handleDragOver}
                        onDrop={() => handleDrop(column.id)}
                    >
                        <div className="flex items-center gap-2 mb-4">
                            <span>{column.icon}</span>
                            <span className="font-medium text-slate-200">{column.label}</span>
                            <span className="ml-auto text-xs bg-slate-700 px-2 py-0.5 rounded-full text-slate-400">
                                {getListingsByStatus(column.id).length}
                            </span>
                        </div>

                        <div className="space-y-2">
                            {getListingsByStatus(column.id).map((listing) => (
                                <div
                                    key={listing.id}
                                    draggable
                                    onDragStart={() => handleDragStart(listing.id)}
                                    className={`kanban-card bg-slate-700/50 border border-slate-600 rounded-lg p-3 transition-all ${draggedId === listing.id ? 'opacity-50' : 'hover:border-slate-500'
                                        }`}
                                >
                                    <div className="flex items-start justify-between gap-2 mb-2">
                                        <span className="text-lg font-bold text-cyan-400">
                                            {listing.scoreTotal}
                                        </span>
                                        <span className="text-xs text-slate-500">
                                            {listing.neighborhoodLabel}
                                        </span>
                                    </div>
                                    <a
                                        href={listing.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="group"
                                    >
                                        <h3 className="text-sm font-medium text-slate-200 line-clamp-2 mb-2 group-hover:text-cyan-400 transition-colors">
                                            {listing.title} <span className="text-xs opacity-0 group-hover:opacity-100 transition-opacity">↗</span>
                                        </h3>
                                    </a>
                                    <div className="flex items-center justify-between text-xs">
                                        <span className="text-emerald-400 font-medium">
                                            ${(listing.rentAllInEstimate || listing.rentBase).toLocaleString()}
                                        </span>
                                        <a
                                            href={listing.url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="p-1 text-slate-400 hover:text-slate-200 hover:bg-slate-600 rounded"
                                            onClick={(e) => e.stopPropagation()}
                                            title="Open listing"
                                        >
                                            🔗
                                        </a>
                                    </div>
                                </div>
                            ))}

                            {getListingsByStatus(column.id).length === 0 && (
                                <div className="text-center py-8 text-slate-500 text-sm">
                                    No listings
                                </div>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
