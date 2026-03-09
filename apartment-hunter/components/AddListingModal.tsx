'use client';

import { useState } from 'react';

interface AddListingModalProps {
    onClose: () => void;
    onSuccess: () => void;
}

export function AddListingModal({ onClose, onSuccess }: AddListingModalProps) {
    const [mode, setMode] = useState<'url' | 'manual'>('url');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // URL mode
    const [url, setUrl] = useState('');

    // Manual mode
    const [title, setTitle] = useState('');
    const [description, setDescription] = useState('');
    const [addressRaw, setAddressRaw] = useState('');
    const [buildingName, setBuildingName] = useState('');
    const [rent, setRent] = useState('');
    const [sqft, setSqft] = useState('');
    const [features, setFeatures] = useState('');

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);

        try {
            const body = mode === 'url'
                ? { url }
                : {
                    url: url || `manual://listing-${Date.now()}`,
                    title,
                    description,
                    addressRaw,
                    buildingName,
                    rent: parseInt(rent),
                    beds: 1,
                    baths: 1,
                    sqft: sqft ? parseInt(sqft) : undefined,
                    features: features.split(',').map((f) => f.trim()).filter(Boolean),
                };

            const res = await fetch('/api/listings/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });

            const data = await res.json();

            if (!res.ok) {
                throw new Error(data.error || 'Failed to add listing');
            }

            onSuccess();
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Something went wrong');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-lg overflow-hidden">
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-slate-700">
                    <h2 className="text-lg font-semibold text-slate-100">Add Listing</h2>
                    <button
                        onClick={onClose}
                        className="text-slate-400 hover:text-slate-200"
                    >
                        ✕
                    </button>
                </div>

                {/* Mode Tabs */}
                <div className="flex border-b border-slate-700">
                    <button
                        onClick={() => setMode('url')}
                        className={`flex-1 py-3 text-sm font-medium transition-colors ${mode === 'url'
                                ? 'text-cyan-400 border-b-2 border-cyan-400'
                                : 'text-slate-400 hover:text-slate-200'
                            }`}
                    >
                        🔗 Import from URL
                    </button>
                    <button
                        onClick={() => setMode('manual')}
                        className={`flex-1 py-3 text-sm font-medium transition-colors ${mode === 'manual'
                                ? 'text-cyan-400 border-b-2 border-cyan-400'
                                : 'text-slate-400 hover:text-slate-200'
                            }`}
                    >
                        ✏️ Manual Entry
                    </button>
                </div>

                {/* Form */}
                <form onSubmit={handleSubmit} className="p-4 space-y-4">
                    {mode === 'url' ? (
                        <div>
                            <label className="block text-sm font-medium text-slate-300 mb-1">
                                Listing URL
                            </label>
                            <input
                                type="url"
                                value={url}
                                onChange={(e) => setUrl(e.target.value)}
                                placeholder="https://honolulu.craigslist.org/apa/..."
                                className="w-full bg-slate-700 border border-slate-600 rounded-lg py-2 px-3 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                                required
                            />
                            <p className="mt-1 text-xs text-slate-500">
                                Supports Craigslist, Zillow, Apartments.com, and generic property sites
                            </p>
                        </div>
                    ) : (
                        <>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="col-span-2">
                                    <label className="block text-sm font-medium text-slate-300 mb-1">
                                        Title *
                                    </label>
                                    <input
                                        type="text"
                                        value={title}
                                        onChange={(e) => setTitle(e.target.value)}
                                        placeholder="Beautiful 1BR in Waikiki"
                                        className="w-full bg-slate-700 border border-slate-600 rounded-lg py-2 px-3 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                                        required
                                    />
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-slate-300 mb-1">
                                        Rent *
                                    </label>
                                    <input
                                        type="number"
                                        value={rent}
                                        onChange={(e) => setRent(e.target.value)}
                                        placeholder="2800"
                                        className="w-full bg-slate-700 border border-slate-600 rounded-lg py-2 px-3 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                                        required
                                    />
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-slate-300 mb-1">
                                        Sqft
                                    </label>
                                    <input
                                        type="number"
                                        value={sqft}
                                        onChange={(e) => setSqft(e.target.value)}
                                        placeholder="650"
                                        className="w-full bg-slate-700 border border-slate-600 rounded-lg py-2 px-3 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                                    />
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-slate-300 mb-1">
                                        Building Name
                                    </label>
                                    <input
                                        type="text"
                                        value={buildingName}
                                        onChange={(e) => setBuildingName(e.target.value)}
                                        placeholder="Pacific Ocean Tower"
                                        className="w-full bg-slate-700 border border-slate-600 rounded-lg py-2 px-3 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                                    />
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-slate-300 mb-1">
                                        Address
                                    </label>
                                    <input
                                        type="text"
                                        value={addressRaw}
                                        onChange={(e) => setAddressRaw(e.target.value)}
                                        placeholder="123 Kalakaua Ave"
                                        className="w-full bg-slate-700 border border-slate-600 rounded-lg py-2 px-3 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                                    />
                                </div>

                                <div className="col-span-2">
                                    <label className="block text-sm font-medium text-slate-300 mb-1">
                                        URL
                                    </label>
                                    <input
                                        type="url"
                                        value={url}
                                        onChange={(e) => setUrl(e.target.value)}
                                        placeholder="https://..."
                                        className="w-full bg-slate-700 border border-slate-600 rounded-lg py-2 px-3 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                                    />
                                </div>

                                <div className="col-span-2">
                                    <label className="block text-sm font-medium text-slate-300 mb-1">
                                        Features (comma-separated)
                                    </label>
                                    <input
                                        type="text"
                                        value={features}
                                        onChange={(e) => setFeatures(e.target.value)}
                                        placeholder="ocean view, lanai, pool, parking included"
                                        className="w-full bg-slate-700 border border-slate-600 rounded-lg py-2 px-3 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                                    />
                                </div>

                                <div className="col-span-2">
                                    <label className="block text-sm font-medium text-slate-300 mb-1">
                                        Description
                                    </label>
                                    <textarea
                                        value={description}
                                        onChange={(e) => setDescription(e.target.value)}
                                        placeholder="Describe the listing..."
                                        rows={3}
                                        className="w-full bg-slate-700 border border-slate-600 rounded-lg py-2 px-3 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500 resize-none"
                                    />
                                </div>
                            </div>
                        </>
                    )}

                    {error && (
                        <div className="p-3 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400 text-sm">
                            {error}
                        </div>
                    )}

                    <div className="flex gap-3 pt-2">
                        <button
                            type="button"
                            onClick={onClose}
                            className="flex-1 py-2 bg-slate-700 text-slate-300 rounded-lg hover:bg-slate-600 transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={loading}
                            className="flex-1 py-2 bg-gradient-to-r from-cyan-500 to-blue-500 text-white font-medium rounded-lg hover:from-cyan-600 hover:to-blue-600 disabled:opacity-50 transition-all"
                        >
                            {loading ? 'Adding...' : 'Add Listing'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
