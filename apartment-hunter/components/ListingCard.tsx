'use client';

import { useState } from 'react';

interface ListingCardProps {
    listing: {
        id: string;
        title: string;
        url: string;
        neighborhoodLabel: string;
        rentBase: number;
        rentAllInEstimate: number | null;
        sqft: number | null;
        parking: string;
        ac: string;
        wdInUnit: string;
        lanai: string;
        outdoorSpace: string;
        viewTags: string[];
        amenities: string[];
        photos: string[];
        scoreTotal: number;
        scoreBreakdown: {
            view: number;
            viewDetails: { tag: string; points: number }[];
            lanai: number;
            outdoor: number;
            amenities: number;
            amenityDetails: { name: string; points: number }[];
            bonus: number;
            penalties: number;
            penaltyDetails: { reason: string; points: number }[];
        };
        status: string;
        redFlags: string[];
    };
    onStatusChange: (id: string, status: string) => void;
    onAddNote: (id: string, note: string) => void;
    selected?: boolean;
    onSelect?: (id: string) => void;
}

const STATUS_OPTIONS = [
    { value: 'new', label: 'New', icon: '✨' },
    { value: 'shortlisted', label: 'Shortlist', icon: '⭐' },
    { value: 'contacted', label: 'Contacted', icon: '📧' },
    { value: 'touring', label: 'Touring', icon: '🏃' },
    { value: 'applied', label: 'Applied', icon: '📝' },
    { value: 'rejected', label: 'Rejected', icon: '❌' },
];

export function ListingCard({ listing, onStatusChange, onAddNote, selected, onSelect }: ListingCardProps) {
    const [showNoteInput, setShowNoteInput] = useState(false);
    const [noteText, setNoteText] = useState('');
    const [showScoreDetails, setShowScoreDetails] = useState(false);

    const handleAddNote = () => {
        if (noteText.trim()) {
            onAddNote(listing.id, noteText);
            setNoteText('');
            setShowNoteInput(false);
        }
    };

    const getNeighborhoodColor = (n: string) => {
        const colors: Record<string, string> = {
            'Waikiki': 'bg-cyan-500',
            'Ala Moana': 'bg-violet-500',
            'Diamond Head': 'bg-amber-500',
            'Downtown': 'bg-red-500',
            'Across Ala Wai': 'bg-emerald-500',
        };
        return colors[n] || 'bg-slate-500';
    };

    const getScoreColor = (score: number) => {
        if (score >= 70) return 'from-emerald-400 to-green-500';
        if (score >= 50) return 'from-cyan-400 to-blue-500';
        if (score >= 30) return 'from-amber-400 to-orange-500';
        return 'from-red-400 to-rose-500';
    };

    const rentDisplay = listing.rentAllInEstimate
        ? `$${listing.rentAllInEstimate.toLocaleString()}`
        : `$${listing.rentBase.toLocaleString()}+`;

    return (
        <div className={`listing-card bg-slate-800/50 border rounded-xl overflow-hidden ${selected ? 'border-cyan-500 ring-2 ring-cyan-500/30' : 'border-slate-700'
            }`}>
            {/* Score Badge */}
            <div className="relative">
                {listing.photos.length > 0 ? (
                    <div className="photo-strip h-40 bg-slate-900">
                        {listing.photos.slice(0, 5).map((photo, i) => (
                            <img
                                key={i}
                                src={photo}
                                alt={`Photo ${i + 1}`}
                                className="h-full w-auto object-cover"
                                onError={(e) => { e.currentTarget.style.display = 'none'; }}
                            />
                        ))}
                    </div>
                ) : (
                    <div className="h-40 bg-gradient-to-br from-slate-800 to-slate-900 flex items-center justify-center">
                        <span className="text-4xl opacity-30">🏢</span>
                    </div>
                )}

                {/* Score overlay */}
                <button
                    onClick={() => setShowScoreDetails(!showScoreDetails)}
                    className={`absolute top-3 left-3 px-3 py-1.5 rounded-lg bg-gradient-to-r ${getScoreColor(listing.scoreTotal)} text-white font-bold text-sm shadow-lg hover:scale-105 transition-transform`}
                >
                    {listing.scoreTotal}
                </button>

                {/* Select checkbox for compare */}
                {onSelect && (
                    <button
                        onClick={() => onSelect(listing.id)}
                        className={`absolute top-3 right-3 w-8 h-8 rounded-lg flex items-center justify-center transition-all ${selected
                            ? 'bg-cyan-500 text-white'
                            : 'bg-slate-900/80 text-slate-400 hover:bg-slate-800'
                            }`}
                    >
                        {selected ? '✓' : '+'}
                    </button>
                )}

                {/* Neighborhood badge */}
                <div className={`absolute bottom-3 left-3 px-2 py-1 rounded text-xs font-medium text-white ${getNeighborhoodColor(listing.neighborhoodLabel)}`}>
                    {listing.neighborhoodLabel}
                </div>
            </div>

            {/* Score breakdown (expandable) */}
            {showScoreDetails && (
                <div className="bg-slate-900/80 border-b border-slate-700 p-3">
                    <div className="text-xs font-medium text-slate-400 mb-2">Score Breakdown</div>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                        {listing.scoreBreakdown.viewDetails.map((v) => (
                            <div key={v.tag} className="flex justify-between">
                                <span className="text-slate-400">🌊 {v.tag}</span>
                                <span className="text-emerald-400">+{v.points}</span>
                            </div>
                        ))}
                        {listing.scoreBreakdown.lanai > 0 && (
                            <div className="flex justify-between">
                                <span className="text-slate-400">🌴 Lanai</span>
                                <span className="text-emerald-400">+{listing.scoreBreakdown.lanai}</span>
                            </div>
                        )}
                        {listing.scoreBreakdown.outdoor > 0 && (
                            <div className="flex justify-between">
                                <span className="text-slate-400">🌿 Outdoor</span>
                                <span className="text-emerald-400">+{listing.scoreBreakdown.outdoor}</span>
                            </div>
                        )}
                        {listing.scoreBreakdown.amenityDetails.map((a) => (
                            <div key={a.name} className="flex justify-between">
                                <span className="text-slate-400">✨ {a.name}</span>
                                <span className="text-emerald-400">+{a.points}</span>
                            </div>
                        ))}
                        {listing.scoreBreakdown.penaltyDetails.map((p) => (
                            <div key={p.reason} className="flex justify-between col-span-2">
                                <span className="text-red-400">⚠️ {p.reason}</span>
                                <span className="text-red-400">{p.points}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Content */}
            <div className="p-4">
                <a
                    href={listing.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group"
                >
                    <h3 className="font-semibold text-slate-100 mb-2 line-clamp-2 group-hover:text-cyan-400 transition-colors">
                        {listing.title} <span className="text-xs opacity-0 group-hover:opacity-100 transition-opacity">↗</span>
                    </h3>
                </a>

                {/* Key facts */}
                <div className="flex flex-wrap gap-3 mb-3 text-sm">
                    <span className="text-cyan-400 font-semibold">{rentDisplay}</span>
                    {listing.sqft && <span className="text-slate-400">{listing.sqft} sqft</span>}
                </div>

                {/* Features */}
                <div className="flex flex-wrap gap-1.5 mb-3">
                    {listing.parking === 'yes' && (
                        <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 text-xs">🅿️ Parking</span>
                    )}
                    {listing.ac === 'yes' && (
                        <span className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-400 text-xs">❄️ AC</span>
                    )}
                    {listing.wdInUnit === 'yes' && (
                        <span className="px-2 py-0.5 rounded bg-violet-500/20 text-violet-400 text-xs">🧺 W/D</span>
                    )}
                    {listing.lanai === 'yes' && (
                        <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 text-xs">🌴 Lanai</span>
                    )}
                    {listing.viewTags.map((tag) => (
                        <span key={tag} className="px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-400 text-xs">
                            {tag === 'ocean' ? '🌊' : tag === 'mountain' ? '⛰️' : '🏙️'} {tag}
                        </span>
                    ))}
                    {listing.amenities.map((a) => (
                        <span key={a} className="px-2 py-0.5 rounded bg-slate-700 text-slate-300 text-xs">
                            {a === 'pool' ? '🏊' : a === 'bbq' ? '🍖' : a === 'pickleball' ? '🏸' : '💪'} {a}
                        </span>
                    ))}
                </div>

                {/* Red flags */}
                {listing.redFlags.length > 0 && (
                    <div className="mb-3">
                        {listing.redFlags.map((flag, i) => (
                            <div key={i} className="text-xs text-red-400 flex items-center gap-1">
                                <span>⚠️</span> {flag}
                            </div>
                        ))}
                    </div>
                )}

                {/* Actions */}
                <div className="flex items-center gap-2 pt-3 border-t border-slate-700">
                    <select
                        value={listing.status}
                        onChange={(e) => onStatusChange(listing.id, e.target.value)}
                        className="flex-1 bg-slate-700 border-0 rounded-lg text-sm py-2 px-3 text-slate-200"
                    >
                        {STATUS_OPTIONS.map((opt) => (
                            <option key={opt.value} value={opt.value}>
                                {opt.icon} {opt.label}
                            </option>
                        ))}
                    </select>

                    <a
                        href={listing.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-2 bg-slate-700 rounded-lg hover:bg-slate-600 transition-colors flex items-center justify-center min-w-[36px] min-h-[36px]"
                        title="Open listing"
                    >
                        🔗
                    </a>

                    <button
                        onClick={() => setShowNoteInput(!showNoteInput)}
                        className="p-2 bg-slate-700 rounded-lg hover:bg-slate-600 transition-colors"
                        title="Add note"
                    >
                        📝
                    </button>
                </div>

                {/* Note input */}
                {showNoteInput && (
                    <div className="mt-3 flex gap-2">
                        <input
                            type="text"
                            value={noteText}
                            onChange={(e) => setNoteText(e.target.value)}
                            placeholder="Add a note..."
                            className="flex-1 bg-slate-700 border-0 rounded-lg text-sm py-2 px-3 text-slate-200 placeholder:text-slate-500"
                            onKeyDown={(e) => e.key === 'Enter' && handleAddNote()}
                        />
                        <button
                            onClick={handleAddNote}
                            className="px-3 py-2 bg-cyan-500 text-white rounded-lg text-sm font-medium hover:bg-cyan-600"
                        >
                            Save
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}
