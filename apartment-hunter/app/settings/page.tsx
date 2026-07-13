'use client';

import { useState, useEffect } from 'react';

interface ScoringWeights {
    view_ocean: number;
    view_diamond_head: number;
    view_mountain: number;
    view_city: number;
    view_marina: number;
    view_canal: number;
    view_uncertain_penalty: number;
    lanai: number;
    outdoor_private: number;
    outdoor_shared: number;
    amenity_pool: number;
    amenity_bbq: number;
    amenity_pickleball: number;
    amenity_gym: number;
    renovation_bonus: number;
    penalty_portable_ac: number;
    penalty_high_app_fee: number;
}

const DEFAULT_WEIGHTS: ScoringWeights = {
    view_ocean: 20,
    view_diamond_head: 15,
    view_mountain: 10,
    view_city: 8,
    view_marina: 6,
    view_canal: 6,
    view_uncertain_penalty: 0.5,
    lanai: 20,
    outdoor_private: 15,
    outdoor_shared: 8,
    amenity_pool: 8,
    amenity_bbq: 6,
    amenity_pickleball: 10,
    amenity_gym: 4,
    renovation_bonus: 5,
    penalty_portable_ac: -10,
    penalty_high_app_fee: -5,
};

const WEIGHT_LABELS: Record<keyof ScoringWeights, string> = {
    view_ocean: '🌊 Ocean View',
    view_diamond_head: '💎 Diamond Head View',
    view_mountain: '⛰️ Mountain View',
    view_city: '🏙️ City View',
    view_marina: '⚓ Marina View',
    view_canal: '🚣 Canal View',
    view_uncertain_penalty: '❓ Uncertain View Penalty',
    lanai: '🌴 Lanai',
    outdoor_private: '🏡 Private Outdoor Space',
    outdoor_shared: '🏢 Shared Outdoor Space',
    amenity_pool: '🏊 Pool',
    amenity_bbq: '🍖 BBQ',
    amenity_pickleball: '🏸 Pickleball',
    amenity_gym: '💪 Gym',
    renovation_bonus: '✨ Renovation Bonus',
    penalty_portable_ac: '⚠️ Portable AC Penalty',
    penalty_high_app_fee: '⚠️ High App Fee Penalty',
};

export default function SettingsPage() {
    const [weights, setWeights] = useState<ScoringWeights>(DEFAULT_WEIGHTS);
    const [complianceMode, setComplianceMode] = useState<'url-only' | 'broad-search'>('url-only');
    const [saved, setSaved] = useState(false);

    const handleWeightChange = (key: keyof ScoringWeights, value: number) => {
        setWeights((prev) => ({ ...prev, [key]: value }));
        setSaved(false);
    };

    const handleSave = () => {
        // Save to localStorage for now (in production, save to API/database)
        localStorage.setItem('scoringWeights', JSON.stringify(weights));
        localStorage.setItem('complianceMode', complianceMode);
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
    };

    const handleReset = () => {
        setWeights(DEFAULT_WEIGHTS);
        setComplianceMode('url-only');
        setSaved(false);
    };

    useEffect(() => {
        // Load saved settings
        const savedWeights = localStorage.getItem('scoringWeights');
        const savedMode = localStorage.getItem('complianceMode');
        if (savedWeights) {
            setWeights(JSON.parse(savedWeights));
        }
        if (savedMode) {
            setComplianceMode(savedMode as 'url-only' | 'broad-search');
        }
    }, []);

    return (
        <div className="container mx-auto px-4 py-6 max-w-4xl">
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-slate-100">Settings</h1>
                <p className="text-slate-400">Configure scoring weights and compliance mode</p>
            </div>

            {/* Compliance Mode */}
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 mb-6">
                <h2 className="text-lg font-semibold text-slate-200 mb-4">🔒 Compliance Mode</h2>
                <div className="space-y-3">
                    <label className="flex items-start gap-3 cursor-pointer p-3 rounded-lg hover:bg-slate-700/50 transition-colors">
                        <input
                            type="radio"
                            name="compliance"
                            checked={complianceMode === 'url-only'}
                            onChange={() => setComplianceMode('url-only')}
                            className="mt-1 accent-cyan-500"
                        />
                        <div>
                            <div className="font-medium text-slate-200">URL-Only Mode</div>
                            <div className="text-sm text-slate-400">
                                Only parse listings from URLs you provide. No automated searching.
                                This is the safest option for website ToS compliance.
                            </div>
                        </div>
                    </label>
                    <label className="flex items-start gap-3 cursor-pointer p-3 rounded-lg hover:bg-slate-700/50 transition-colors">
                        <input
                            type="radio"
                            name="compliance"
                            checked={complianceMode === 'broad-search'}
                            onChange={() => setComplianceMode('broad-search')}
                            className="mt-1 accent-cyan-500"
                        />
                        <div>
                            <div className="font-medium text-slate-200">Broad Search Mode</div>
                            <div className="text-sm text-slate-400">
                                Allow connectors to search listings automatically (Craigslist RSS, etc).
                                May violate some website terms of service.
                            </div>
                        </div>
                    </label>
                </div>
            </div>

            {/* Scoring Weights */}
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 mb-6">
                <h2 className="text-lg font-semibold text-slate-200 mb-4">⚖️ Scoring Weights</h2>
                <p className="text-sm text-slate-400 mb-4">
                    Adjust the point values for each scoring factor. Higher values = more importance.
                </p>

                <div className="space-y-6">
                    {/* Views */}
                    <div>
                        <h3 className="text-sm font-medium text-cyan-400 mb-3">View Quality (max 35 pts)</h3>
                        <div className="grid grid-cols-2 gap-4">
                            {(['view_ocean', 'view_diamond_head', 'view_mountain', 'view_city', 'view_marina', 'view_canal'] as const).map((key) => (
                                <div key={key} className="flex items-center gap-3">
                                    <label className="flex-1 text-sm text-slate-300">{WEIGHT_LABELS[key]}</label>
                                    <input
                                        type="number"
                                        value={weights[key]}
                                        onChange={(e) => handleWeightChange(key, parseInt(e.target.value) || 0)}
                                        className="w-16 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-sm text-slate-200 text-center"
                                    />
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Lanai & Outdoor */}
                    <div>
                        <h3 className="text-sm font-medium text-cyan-400 mb-3">Outdoor Features</h3>
                        <div className="grid grid-cols-2 gap-4">
                            {(['lanai', 'outdoor_private', 'outdoor_shared'] as const).map((key) => (
                                <div key={key} className="flex items-center gap-3">
                                    <label className="flex-1 text-sm text-slate-300">{WEIGHT_LABELS[key]}</label>
                                    <input
                                        type="number"
                                        value={weights[key]}
                                        onChange={(e) => handleWeightChange(key, parseInt(e.target.value) || 0)}
                                        className="w-16 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-sm text-slate-200 text-center"
                                    />
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Amenities */}
                    <div>
                        <h3 className="text-sm font-medium text-cyan-400 mb-3">Amenities</h3>
                        <div className="grid grid-cols-2 gap-4">
                            {(['amenity_pool', 'amenity_bbq', 'amenity_pickleball', 'amenity_gym'] as const).map((key) => (
                                <div key={key} className="flex items-center gap-3">
                                    <label className="flex-1 text-sm text-slate-300">{WEIGHT_LABELS[key]}</label>
                                    <input
                                        type="number"
                                        value={weights[key]}
                                        onChange={(e) => handleWeightChange(key, parseInt(e.target.value) || 0)}
                                        className="w-16 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-sm text-slate-200 text-center"
                                    />
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Penalties */}
                    <div>
                        <h3 className="text-sm font-medium text-red-400 mb-3">Penalties & Bonuses</h3>
                        <div className="grid grid-cols-2 gap-4">
                            {(['renovation_bonus', 'penalty_portable_ac', 'penalty_high_app_fee'] as const).map((key) => (
                                <div key={key} className="flex items-center gap-3">
                                    <label className="flex-1 text-sm text-slate-300">{WEIGHT_LABELS[key]}</label>
                                    <input
                                        type="number"
                                        value={weights[key]}
                                        onChange={(e) => handleWeightChange(key, parseInt(e.target.value) || 0)}
                                        className="w-16 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-sm text-slate-200 text-center"
                                    />
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-4">
                <button
                    onClick={handleSave}
                    className="px-6 py-2 bg-gradient-to-r from-cyan-500 to-blue-500 text-white font-medium rounded-lg hover:from-cyan-600 hover:to-blue-600 transition-all"
                >
                    {saved ? '✓ Saved!' : 'Save Settings'}
                </button>
                <button
                    onClick={handleReset}
                    className="px-6 py-2 bg-slate-700 text-slate-300 rounded-lg hover:bg-slate-600 transition-colors"
                >
                    Reset to Defaults
                </button>
            </div>
        </div>
    );
}
