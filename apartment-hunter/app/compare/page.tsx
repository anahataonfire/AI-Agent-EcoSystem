'use client';

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';

interface Listing {
    id: string;
    title: string;
    url: string;
    neighborhoodLabel: string;
    rentBase: number;
    rentAllInEstimate: number | null;
    sqft: number | null;
    parking: string;
    ac: string;
    acType: string | null;
    wdInUnit: string;
    lanai: string;
    outdoorSpace: string;
    viewTags: string[];
    amenities: string[];
    photos: string[];
    scoreTotal: number;
    scoreBreakdown: {
        view: number;
        lanai: number;
        outdoor: number;
        amenities: number;
        bonus: number;
        penalties: number;
    };
}

function CompareContent() {
    const searchParams = useSearchParams();
    const ids = searchParams.get('ids')?.split(',') || [];

    const [listings, setListings] = useState<Listing[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (ids.length > 0) {
            fetchListings();
        } else {
            setLoading(false);
        }
    }, []);

    const fetchListings = async () => {
        try {
            const res = await fetch('/api/listings');
            const data = await res.json();
            const selected = (data.listings || []).filter((l: Listing) =>
                ids.includes(l.id)
            );
            setListings(selected);
        } catch (error) {
            console.error('Failed to fetch:', error);
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="container mx-auto px-4 py-6 flex items-center justify-center min-h-[60vh]">
                <div className="text-slate-400">Loading comparison...</div>
            </div>
        );
    }

    if (listings.length === 0) {
        return (
            <div className="container mx-auto px-4 py-6">
                <div className="text-center py-20">
                    <div className="text-6xl mb-4">⚖️</div>
                    <h2 className="text-xl font-semibold text-slate-300 mb-2">No listings to compare</h2>
                    <p className="text-slate-500 mb-4">
                        Select 2-4 listings from the dashboard to compare side by side
                    </p>
                    <Link
                        href="/"
                        className="inline-block px-4 py-2 bg-cyan-500 text-white rounded-lg hover:bg-cyan-600"
                    >
                        Go to Dashboard
                    </Link>
                </div>
            </div>
        );
    }

    const CompareRow = ({ label, getValue }: { label: string; getValue: (l: Listing) => React.ReactNode }) => (
        <tr className="border-b border-slate-700">
            <td className="py-3 px-4 text-sm font-medium text-slate-400 bg-slate-800/50">
                {label}
            </td>
            {listings.map((l) => (
                <td key={l.id} className="py-3 px-4 text-sm text-slate-200">
                    {getValue(l)}
                </td>
            ))}
        </tr>
    );

    const getBestValue = (getValue: (l: Listing) => number) => {
        const values = listings.map(getValue);
        return Math.max(...values);
    };

    const getWorstValue = (getValue: (l: Listing) => number) => {
        const values = listings.map(getValue);
        return Math.min(...values);
    };

    return (
        <div className="container mx-auto px-4 py-6">
            <div className="mb-6 flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-100">Compare Listings</h1>
                    <p className="text-slate-400">Side-by-side comparison of {listings.length} listings</p>
                </div>
                <Link
                    href="/"
                    className="px-4 py-2 bg-slate-700 text-slate-200 rounded-lg hover:bg-slate-600"
                >
                    ← Back to Dashboard
                </Link>
            </div>

            <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden overflow-x-auto">
                <table className="w-full">
                    <thead>
                        <tr className="border-b border-slate-700">
                            <th className="py-4 px-4 text-left text-sm font-semibold text-slate-300 bg-slate-800/80 w-40">
                                Property
                            </th>
                            {listings.map((l) => (
                                <th key={l.id} className="py-4 px-4 text-left min-w-64">
                                    <div className="space-y-2">
                                        {l.photos[0] ? (
                                            <img
                                                src={l.photos[0]}
                                                alt={l.title}
                                                className="w-full h-32 object-cover rounded-lg"
                                            />
                                        ) : (
                                            <div className="w-full h-32 bg-slate-700 rounded-lg flex items-center justify-center text-2xl">
                                                🏢
                                            </div>
                                        )}
                                        <h3 className="font-medium text-slate-200 line-clamp-2">{l.title}</h3>
                                        <span className="inline-block px-2 py-1 rounded text-xs bg-slate-700 text-slate-300">
                                            {l.neighborhoodLabel}
                                        </span>
                                    </div>
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        <CompareRow
                            label="Score"
                            getValue={(l) => {
                                const isBest = l.scoreTotal === getBestValue((x) => x.scoreTotal);
                                return (
                                    <span className={`text-lg font-bold ${isBest ? 'text-emerald-400' : 'text-slate-300'}`}>
                                        {l.scoreTotal} {isBest && '🏆'}
                                    </span>
                                );
                            }}
                        />
                        <CompareRow
                            label="Rent"
                            getValue={(l) => {
                                const rent = l.rentAllInEstimate || l.rentBase;
                                const isLowest = rent === getWorstValue((x) => x.rentAllInEstimate || x.rentBase);
                                return (
                                    <span className={isLowest ? 'text-emerald-400' : ''}>
                                        ${rent.toLocaleString()}
                                        {l.rentAllInEstimate ? '/mo all-in' : '/mo base'}
                                    </span>
                                );
                            }}
                        />
                        <CompareRow label="Sqft" getValue={(l) => l.sqft ? `${l.sqft} sqft` : '-'} />
                        <CompareRow
                            label="Parking"
                            getValue={(l) => (
                                <span className={l.parking === 'yes' ? 'text-emerald-400' : 'text-red-400'}>
                                    {l.parking === 'yes' ? '✓ Yes' : '✗ No'}
                                </span>
                            )}
                        />
                        <CompareRow
                            label="AC"
                            getValue={(l) => (
                                <span className={l.ac === 'yes' ? 'text-emerald-400' : 'text-red-400'}>
                                    {l.ac === 'yes' ? `✓ ${l.acType || 'Yes'}` : '✗ No'}
                                </span>
                            )}
                        />
                        <CompareRow
                            label="W/D In-Unit"
                            getValue={(l) => (
                                <span className={l.wdInUnit === 'yes' ? 'text-emerald-400' : 'text-red-400'}>
                                    {l.wdInUnit === 'yes' ? '✓ Yes' : '✗ No'}
                                </span>
                            )}
                        />
                        <CompareRow
                            label="Lanai"
                            getValue={(l) => (
                                <span className={l.lanai === 'yes' ? 'text-emerald-400' : 'text-slate-500'}>
                                    {l.lanai === 'yes' ? '✓ Yes' : '-'}
                                </span>
                            )}
                        />
                        <CompareRow label="Outdoor Space" getValue={(l) => l.outdoorSpace || '-'} />
                        <CompareRow
                            label="Views"
                            getValue={(l) =>
                                l.viewTags.length > 0 ? (
                                    <div className="flex flex-wrap gap-1">
                                        {l.viewTags.map((v) => (
                                            <span key={v} className="px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-400 text-xs">
                                                {v}
                                            </span>
                                        ))}
                                    </div>
                                ) : (
                                    '-'
                                )
                            }
                        />
                        <CompareRow
                            label="Amenities"
                            getValue={(l) =>
                                l.amenities.length > 0 ? (
                                    <div className="flex flex-wrap gap-1">
                                        {l.amenities.map((a) => (
                                            <span key={a} className="px-2 py-0.5 rounded bg-slate-700 text-slate-300 text-xs">
                                                {a}
                                            </span>
                                        ))}
                                    </div>
                                ) : (
                                    '-'
                                )
                            }
                        />
                        <CompareRow
                            label="Score Breakdown"
                            getValue={(l) => (
                                <div className="text-xs space-y-1">
                                    <div>View: +{l.scoreBreakdown.view}</div>
                                    <div>Lanai: +{l.scoreBreakdown.lanai}</div>
                                    <div>Outdoor: +{l.scoreBreakdown.outdoor}</div>
                                    <div>Amenities: +{l.scoreBreakdown.amenities}</div>
                                    {l.scoreBreakdown.penalties < 0 && (
                                        <div className="text-red-400">Penalties: {l.scoreBreakdown.penalties}</div>
                                    )}
                                </div>
                            )}
                        />
                        <CompareRow
                            label="Link"
                            getValue={(l) => (
                                <a
                                    href={l.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-cyan-400 hover:text-cyan-300"
                                >
                                    View Listing →
                                </a>
                            )}
                        />
                    </tbody>
                </table>
            </div>
        </div>
    );
}

export default function ComparePage() {
    return (
        <Suspense fallback={<div className="container mx-auto px-4 py-6 flex items-center justify-center min-h-[60vh]"><div className="text-slate-400">Loading...</div></div>}>
            <CompareContent />
        </Suspense>
    );
}
