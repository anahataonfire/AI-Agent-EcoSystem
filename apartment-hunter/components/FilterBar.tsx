'use client';

import { useState } from 'react';
import type { NeighborhoodLabel } from '@/lib/neighborhoods';

interface FilterBarProps {
    onFilterChange: (filters: FilterState) => void;
}

export interface FilterState {
    neighborhoods: NeighborhoodLabel[];
    minRent: number;
    maxRent: number;
    requireParking: boolean;
    requireAC: boolean;
    requireWD: boolean;
    highConfidenceOnly: boolean;
}

const NEIGHBORHOODS: { label: NeighborhoodLabel; color: string }[] = [
    { label: 'Waikiki', color: 'bg-cyan-500' },
    { label: 'Ala Moana', color: 'bg-violet-500' },
    { label: 'Diamond Head', color: 'bg-amber-500' },
    { label: 'Downtown', color: 'bg-red-500' },
    { label: 'Across Ala Wai', color: 'bg-emerald-500' },
];

export function FilterBar({ onFilterChange }: FilterBarProps) {
    const [filters, setFilters] = useState<FilterState>({
        neighborhoods: ['Waikiki', 'Ala Moana', 'Diamond Head'],
        minRent: 2700,
        maxRent: 3400,
        requireParking: true,
        requireAC: true,
        requireWD: true,
        highConfidenceOnly: true,
    });

    const updateFilters = (updates: Partial<FilterState>) => {
        const newFilters = { ...filters, ...updates };
        setFilters(newFilters);
        onFilterChange(newFilters);
    };

    const toggleNeighborhood = (label: NeighborhoodLabel) => {
        const current = filters.neighborhoods;
        const newNeighborhoods = current.includes(label)
            ? current.filter((n) => n !== label)
            : [...current, label];
        updateFilters({ neighborhoods: newNeighborhoods });
    };

    return (
        <div className="bg-slate-900/80 backdrop-blur-sm border border-slate-700 rounded-xl p-4 mb-6">
            <div className="flex flex-wrap items-center gap-6">
                {/* Neighborhoods */}
                <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-400">Areas:</span>
                    <div className="flex gap-1">
                        {NEIGHBORHOODS.map(({ label, color }) => (
                            <button
                                key={label}
                                onClick={() => toggleNeighborhood(label)}
                                className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${filters.neighborhoods.includes(label)
                                        ? `${color} text-white shadow-lg`
                                        : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                                    }`}
                            >
                                {label}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Price Range */}
                <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-400">Rent:</span>
                    <div className="flex items-center gap-2 bg-slate-800 rounded-lg px-3 py-1.5">
                        <span className="text-sm text-slate-300">${filters.minRent.toLocaleString()}</span>
                        <input
                            type="range"
                            min="2000"
                            max="4000"
                            step="100"
                            value={filters.maxRent}
                            onChange={(e) => updateFilters({ maxRent: parseInt(e.target.value) })}
                            className="w-24 accent-cyan-500"
                        />
                        <span className="text-sm text-slate-300">${filters.maxRent.toLocaleString()}</span>
                    </div>
                </div>

                {/* Hard Filters */}
                <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-400">Requires:</span>
                    <div className="flex gap-1">
                        <button
                            onClick={() => updateFilters({ requireParking: !filters.requireParking })}
                            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${filters.requireParking
                                    ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/50'
                                    : 'bg-slate-700 text-slate-500'
                                }`}
                        >
                            🅿️ Parking
                        </button>
                        <button
                            onClick={() => updateFilters({ requireAC: !filters.requireAC })}
                            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${filters.requireAC
                                    ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/50'
                                    : 'bg-slate-700 text-slate-500'
                                }`}
                        >
                            ❄️ AC
                        </button>
                        <button
                            onClick={() => updateFilters({ requireWD: !filters.requireWD })}
                            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${filters.requireWD
                                    ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/50'
                                    : 'bg-slate-700 text-slate-500'
                                }`}
                        >
                            🧺 W/D
                        </button>
                    </div>
                </div>

                {/* High Confidence Toggle */}
                <div className="flex items-center gap-2 ml-auto">
                    <label className="flex items-center gap-2 cursor-pointer">
                        <input
                            type="checkbox"
                            checked={filters.highConfidenceOnly}
                            onChange={(e) => updateFilters({ highConfidenceOnly: e.target.checked })}
                            className="w-4 h-4 rounded bg-slate-700 border-slate-600 text-cyan-500 focus:ring-cyan-500"
                        />
                        <span className="text-sm text-slate-300">High confidence only</span>
                    </label>
                </div>
            </div>
        </div>
    );
}
