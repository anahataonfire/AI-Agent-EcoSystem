// Deduplication logic for listings
import { prisma } from './db';

export interface DedupeResult {
    isDuplicate: boolean;
    confidence: 'exact' | 'high' | 'medium' | 'low';
    canonicalId: string | null;
    reason: string | null;
}

// Generate a dedupe key for fuzzy matching
export function generateDedupeKey(listing: {
    addressRaw?: string | null;
    buildingName?: string | null;
    beds: number;
    baths: number;
    sqft?: number | null;
}): string {
    const parts: string[] = [];

    // Normalize address
    if (listing.addressRaw) {
        const normalizedAddr = listing.addressRaw
            .toLowerCase()
            .replace(/\s+/g, ' ')
            .replace(/,/g, '')
            .replace(/\./g, '')
            .replace(/apt\.?\s*#?\d+/i, '')
            .replace(/unit\.?\s*#?\d+/i, '')
            .replace(/\#\d+/i, '')
            .trim();
        parts.push(normalizedAddr);
    }

    // Add building name if available
    if (listing.buildingName) {
        parts.push(listing.buildingName.toLowerCase().trim());
    }

    // Add unit details
    parts.push(`${listing.beds}br`);
    parts.push(`${listing.baths}ba`);

    if (listing.sqft && listing.sqft > 0) {
        // Round to nearest 50 sqft for fuzzy matching
        const roundedSqft = Math.round(listing.sqft / 50) * 50;
        parts.push(`${roundedSqft}sqft`);
    }

    return parts.join('|');
}

// Check for duplicates
export async function checkDuplicate(
    url: string,
    listing: {
        addressRaw?: string | null;
        buildingName?: string | null;
        beds: number;
        baths: number;
        sqft?: number | null;
        rentBase: number;
    }
): Promise<DedupeResult> {
    // 1. Exact URL match
    const exactMatch = await prisma.listing.findUnique({
        where: { url },
        select: { id: true },
    });

    if (exactMatch) {
        return {
            isDuplicate: true,
            confidence: 'exact',
            canonicalId: exactMatch.id,
            reason: 'Exact URL match',
        };
    }

    // 2. Building + rent match
    if (listing.buildingName) {
        // SQLite is case-sensitive, so we normalize both sides
        const normalizedBuilding = listing.buildingName.toLowerCase().trim();
        const buildingMatches = await prisma.listing.findMany({
            where: {
                beds: listing.beds,
                baths: listing.baths,
                // Rent within $100
                rentBase: {
                    gte: listing.rentBase - 100,
                    lte: listing.rentBase + 100,
                },
            },
            select: { id: true, url: true, sqft: true, buildingName: true },
        });

        // Filter for matching building names (case-insensitive)
        const filteredMatches = buildingMatches.filter(
            (m) => m.buildingName && m.buildingName.toLowerCase().trim() === normalizedBuilding
        );

        if (filteredMatches.length > 0) {
            // Check sqft similarity if available
            for (const match of filteredMatches) {
                if (listing.sqft && match.sqft) {
                    const sqftDiff = Math.abs(listing.sqft - match.sqft);
                    if (sqftDiff <= 50) {
                        return {
                            isDuplicate: true,
                            confidence: 'high',
                            canonicalId: match.id,
                            reason: `Same building (${listing.buildingName}), similar rent and size`,
                        };
                    }
                } else {
                    // No sqft to compare, still likely same unit
                    return {
                        isDuplicate: true,
                        confidence: 'medium',
                        canonicalId: match.id,
                        reason: `Same building (${listing.buildingName}), similar rent`,
                    };
                }
            }
        }
    }

    // 3. Address similarity
    if (listing.addressRaw) {
        const dedupeKey = generateDedupeKey(listing);

        // Look for similar dedupe keys
        const potentialMatches = await prisma.listing.findMany({
            where: {
                dedupeKey: {
                    not: null,
                },
                beds: listing.beds,
                baths: listing.baths,
                rentBase: {
                    gte: listing.rentBase - 150,
                    lte: listing.rentBase + 150,
                },
            },
            select: { id: true, dedupeKey: true },
        });

        for (const match of potentialMatches) {
            if (match.dedupeKey) {
                const similarity = calculateSimilarity(dedupeKey, match.dedupeKey);
                if (similarity > 0.85) {
                    return {
                        isDuplicate: true,
                        confidence: 'medium',
                        canonicalId: match.id,
                        reason: `Address similarity: ${Math.round(similarity * 100)}%`,
                    };
                }
            }
        }
    }

    return {
        isDuplicate: false,
        confidence: 'low',
        canonicalId: null,
        reason: null,
    };
}

// Simple string similarity (Jaccard)
function calculateSimilarity(str1: string, str2: string): number {
    const set1 = new Set(str1.toLowerCase().split(/[\s|]+/));
    const set2 = new Set(str2.toLowerCase().split(/[\s|]+/));

    const intersection = new Set([...set1].filter((x) => set2.has(x)));
    const union = new Set([...set1, ...set2]);

    return intersection.size / union.size;
}

// Get all sources for a listing (canonical + duplicates)
export async function getListingSources(canonicalId: string): Promise<string[]> {
    const listing = await prisma.listing.findUnique({
        where: { id: canonicalId },
        select: {
            source: true,
            duplicates: {
                select: { source: true },
            },
        },
    });

    if (!listing) return [];

    const sources = [listing.source];
    for (const dupe of listing.duplicates) {
        if (!sources.includes(dupe.source)) {
            sources.push(dupe.source);
        }
    }

    return sources;
}
