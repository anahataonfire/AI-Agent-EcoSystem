'use client';

import { useState, useEffect, useCallback } from 'react';
import { FilterBar, FilterState } from '@/components/FilterBar';
import { ListingCard } from '@/components/ListingCard';
import { AddListingModal } from '@/components/AddListingModal';
import Link from 'next/link';

interface Listing {
  id: string;
  title: string;
  url: string;
  source: string;
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
  notes: string | null;
}

export default function DashboardPage() {
  const [listings, setListings] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<FilterState>({
    neighborhoods: ['Waikiki', 'Ala Moana', 'Diamond Head'],
    minRent: 2700,
    maxRent: 3400,
    requireParking: true,
    requireAC: true,
    requireWD: true,
    highConfidenceOnly: true,
  });
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [showAddModal, setShowAddModal] = useState(false);
  const [scanning, setScanning] = useState(false);

  const fetchListings = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.neighborhoods.length > 0) {
        params.set('neighborhoods', filters.neighborhoods.join(','));
      }
      params.set('minRent', filters.minRent.toString());
      params.set('maxRent', filters.maxRent.toString());
      if (filters.requireParking) params.set('requireParking', 'true');
      if (filters.requireAC) params.set('requireAC', 'true');
      if (filters.requireWD) params.set('requireWD', 'true');

      const res = await fetch(`/api/listings?${params.toString()}`);
      const data = await res.json();
      setListings(data.listings || []);
    } catch (error) {
      console.error('Failed to fetch listings:', error);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    fetchListings();
  }, [fetchListings]);

  const handleStatusChange = async (id: string, status: string) => {
    try {
      await fetch('/api/listings', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, status }),
      });
      setListings((prev) =>
        prev.map((l) => (l.id === id ? { ...l, status } : l))
      );
    } catch (error) {
      console.error('Failed to update status:', error);
    }
  };

  const handleAddNote = async (id: string, note: string) => {
    try {
      await fetch('/api/listings', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, notes: note }),
      });
      setListings((prev) =>
        prev.map((l) => (l.id === id ? { ...l, notes: note } : l))
      );
    } catch (error) {
      console.error('Failed to add note:', error);
    }
  };

  const handleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(id)) {
        newSet.delete(id);
      } else if (newSet.size < 4) {
        newSet.add(id);
      }
      return newSet;
    });
  };

  const handleScan = async () => {
    setScanning(true);
    try {
      const res = await fetch('/api/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      const data = await res.json();
      console.log('Scan results:', data);
      // Refresh listings
      await fetchListings();
    } catch (error) {
      console.error('Scan failed:', error);
    } finally {
      setScanning(false);
    }
  };

  const stats = {
    total: listings.length,
    shortlisted: listings.filter((l) => l.status === 'shortlisted').length,
    avgScore: listings.length
      ? Math.round(listings.reduce((sum, l) => sum + l.scoreTotal, 0) / listings.length)
      : 0,
  };

  return (
    <div className="container mx-auto px-4 py-6">
      {/* Stats Bar */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-gradient-to-br from-cyan-500/20 to-blue-500/20 border border-cyan-500/30 rounded-xl p-4">
          <div className="text-3xl font-bold text-cyan-400">{stats.total}</div>
          <div className="text-sm text-slate-400">Total Listings</div>
        </div>
        <div className="bg-gradient-to-br from-amber-500/20 to-orange-500/20 border border-amber-500/30 rounded-xl p-4">
          <div className="text-3xl font-bold text-amber-400">{stats.shortlisted}</div>
          <div className="text-sm text-slate-400">Shortlisted</div>
        </div>
        <div className="bg-gradient-to-br from-emerald-500/20 to-green-500/20 border border-emerald-500/30 rounded-xl p-4">
          <div className="text-3xl font-bold text-emerald-400">{stats.avgScore}</div>
          <div className="text-sm text-slate-400">Avg Score</div>
        </div>
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4 flex items-center gap-3">
          <button
            onClick={handleScan}
            disabled={scanning}
            className="flex-1 py-2 px-4 bg-gradient-to-r from-cyan-500 to-blue-500 text-white font-medium rounded-lg hover:from-cyan-600 hover:to-blue-600 disabled:opacity-50 transition-all"
          >
            {scanning ? '🔄 Scanning...' : '🔍 Run Scan'}
          </button>
          <button
            onClick={() => setShowAddModal(true)}
            className="py-2 px-4 bg-slate-700 text-slate-200 font-medium rounded-lg hover:bg-slate-600 transition-colors"
          >
            ➕ Add
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <FilterBar onFilterChange={setFilters} />

      {/* Selected for Compare */}
      {selectedIds.size > 0 && (
        <div className="bg-cyan-500/10 border border-cyan-500/30 rounded-xl p-4 mb-6 flex items-center justify-between">
          <span className="text-cyan-400">
            {selectedIds.size} listing{selectedIds.size > 1 ? 's' : ''} selected for comparison
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setSelectedIds(new Set())}
              className="px-3 py-1.5 text-sm bg-slate-700 text-slate-300 rounded-lg hover:bg-slate-600"
            >
              Clear
            </button>
            <Link
              href={`/compare?ids=${Array.from(selectedIds).join(',')}`}
              className="px-3 py-1.5 text-sm bg-cyan-500 text-white rounded-lg hover:bg-cyan-600"
            >
              Compare →
            </Link>
          </div>
        </div>
      )}

      {/* Listings Grid */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="text-slate-400">Loading listings...</div>
        </div>
      ) : listings.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="text-6xl mb-4">🏠</div>
          <h2 className="text-xl font-semibold text-slate-300 mb-2">No listings yet</h2>
          <p className="text-slate-500 mb-4">
            Add your first listing or run a scan to get started
          </p>
          <button
            onClick={() => setShowAddModal(true)}
            className="px-4 py-2 bg-cyan-500 text-white rounded-lg hover:bg-cyan-600"
          >
            Add a Listing
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {listings.map((listing) => (
            <ListingCard
              key={listing.id}
              listing={listing}
              onStatusChange={handleStatusChange}
              onAddNote={handleAddNote}
              selected={selectedIds.has(listing.id)}
              onSelect={handleSelect}
            />
          ))}
        </div>
      )}

      {/* Add Listing Modal */}
      {showAddModal && (
        <AddListingModal
          onClose={() => setShowAddModal(false)}
          onSuccess={() => {
            setShowAddModal(false);
            fetchListings();
          }}
        />
      )}
    </div>
  );
}
