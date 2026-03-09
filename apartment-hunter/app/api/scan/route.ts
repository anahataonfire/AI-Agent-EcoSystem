// API route for scanning listings from connectors

import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';
import { normalizeListing, passesHardFilters } from '@/lib/normalizer';
import { checkDuplicate } from '@/lib/dedupe';
import { connectorRegistry } from '@/lib/connectors';

export async function POST(request: NextRequest) {
    try {
        const body = await request.json();
        const { connectorName, options } = body;

        // Get the connector
        const connector = connectorName
            ? connectorRegistry.get(connectorName)
            : null;

        // Create scan run record
        const scanRun = await prisma.scanRun.create({
            data: {
                connector: connectorName || 'all',
            },
        });

        const results = {
            scanned: 0,
            newListings: 0,
            duplicates: 0,
            filtered: 0,
            errors: [] as string[],
        };

        // Get connectors to run
        const connectorsToRun = connector
            ? [connector]
            : connectorRegistry.getAll();

        for (const conn of connectorsToRun) {
            // Check if available and broad search is allowed
            const available = await conn.isAvailable();
            if (!available) continue;

            if (conn.getComplianceMode() === 'url-only') {
                results.errors.push(`${conn.displayName}: Skipping broad search (URL-only mode)`);
                continue;
            }

            try {
                const searchResult = await conn.search(options || {
                    beds: 1,
                    minRent: 2700,
                    maxRent: 3400,
                });

                results.scanned += searchResult.scanned;
                results.errors.push(...searchResult.errors);

                // Process each listing
                for (const rawListing of searchResult.listings) {
                    try {
                        // Normalize
                        const normalized = normalizeListing(rawListing);

                        // Check hard filters
                        const filterResult = passesHardFilters(normalized);
                        if (!filterResult.passed) {
                            results.filtered++;
                            continue;
                        }

                        // Check for duplicates
                        const dupeResult = await checkDuplicate(rawListing.url, {
                            addressRaw: normalized.addressRaw,
                            buildingName: normalized.buildingName,
                            beds: normalized.beds,
                            baths: normalized.baths,
                            sqft: normalized.sqft,
                            rentBase: normalized.rentBase,
                        });

                        if (dupeResult.isDuplicate && dupeResult.confidence === 'exact') {
                            // Update lastSeenDate
                            await prisma.listing.update({
                                where: { url: rawListing.url },
                                data: { lastSeenDate: new Date() },
                            });
                            results.duplicates++;
                            continue;
                        }

                        // Create new listing
                        await prisma.listing.create({
                            data: {
                                ...normalized,
                                canonicalListingId: dupeResult.isDuplicate ? dupeResult.canonicalId : null,
                            },
                        });

                        results.newListings++;
                    } catch (listingError) {
                        results.errors.push(`Failed to process listing: ${listingError}`);
                    }
                }
            } catch (connError) {
                results.errors.push(`${conn.displayName}: ${connError}`);
            }
        }

        // Update scan run
        await prisma.scanRun.update({
            where: { id: scanRun.id },
            data: {
                completedAt: new Date(),
                listingsFound: results.scanned,
                newListings: results.newListings,
                errors: JSON.stringify(results.errors),
            },
        });

        return NextResponse.json({
            scanId: scanRun.id,
            ...results,
        });
    } catch (error) {
        console.error('Scan error:', error);
        return NextResponse.json({ error: 'Scan failed' }, { status: 500 });
    }
}

export async function GET() {
    // Get recent scan runs
    try {
        const runs = await prisma.scanRun.findMany({
            orderBy: { startedAt: 'desc' },
            take: 10,
        });

        return NextResponse.json({ runs });
    } catch (error) {
        console.error('Error fetching scan runs:', error);
        return NextResponse.json({ error: 'Failed to fetch scan runs' }, { status: 500 });
    }
}
