// API route to add a listing from URL or manual input

import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';
import { normalizeListing, passesHardFilters } from '@/lib/normalizer';
import { checkDuplicate } from '@/lib/dedupe';
import { getConnectorForUrl, manualConnector } from '@/lib/connectors';

export async function POST(request: NextRequest) {
    try {
        const body = await request.json();

        // Check if it's a URL import or manual entry
        if (body.url && !body.title) {
            // URL import
            const { url } = body;

            // Find appropriate connector
            const connector = getConnectorForUrl(url);
            if (!connector) {
                return NextResponse.json(
                    { error: 'No connector available for this URL' },
                    { status: 400 }
                );
            }

            // Parse the URL
            const rawListing = await connector.parseUrl(url);
            if (!rawListing) {
                return NextResponse.json(
                    { error: 'Failed to parse listing from URL' },
                    { status: 400 }
                );
            }

            // Normalize
            const normalized = normalizeListing(rawListing);

            // Check for duplicates
            const dupeResult = await checkDuplicate(url, {
                addressRaw: normalized.addressRaw,
                buildingName: normalized.buildingName,
                beds: normalized.beds,
                baths: normalized.baths,
                sqft: normalized.sqft,
                rentBase: normalized.rentBase,
            });

            if (dupeResult.isDuplicate && dupeResult.confidence === 'exact') {
                return NextResponse.json(
                    { error: 'This listing already exists', existingId: dupeResult.canonicalId },
                    { status: 409 }
                );
            }

            // Create listing
            const listing = await prisma.listing.create({
                data: {
                    ...normalized,
                    canonicalListingId: dupeResult.isDuplicate ? dupeResult.canonicalId : null,
                },
            });

            // Check hard filters
            const filterResult = passesHardFilters(normalized);

            return NextResponse.json({
                listing,
                passesFilters: filterResult.passed,
                filterFailReasons: filterResult.reasons,
                duplicateInfo: dupeResult.isDuplicate ? dupeResult : null,
            });
        } else {
            // Manual entry
            const {
                url,
                title,
                description,
                addressRaw,
                buildingName,
                rent,
                beds,
                baths,
                sqft,
                photos,
                features,
            } = body;

            if (!url || !title || !rent) {
                return NextResponse.json(
                    { error: 'Missing required fields: url, title, rent' },
                    { status: 400 }
                );
            }

            // Create raw listing from manual input
            const rawListing = manualConnector.createFromInput({
                url,
                title,
                description,
                addressRaw,
                buildingName,
                rent,
                beds: beds || 1,
                baths: baths || 1,
                sqft,
                photos,
                features,
            });

            // Normalize
            const normalized = normalizeListing(rawListing);

            // Check for duplicates
            const dupeResult = await checkDuplicate(url, {
                addressRaw: normalized.addressRaw,
                buildingName: normalized.buildingName,
                beds: normalized.beds,
                baths: normalized.baths,
                sqft: normalized.sqft,
                rentBase: normalized.rentBase,
            });

            if (dupeResult.isDuplicate && dupeResult.confidence === 'exact') {
                return NextResponse.json(
                    { error: 'This listing already exists', existingId: dupeResult.canonicalId },
                    { status: 409 }
                );
            }

            // Create listing
            const listing = await prisma.listing.create({
                data: {
                    ...normalized,
                    canonicalListingId: dupeResult.isDuplicate ? dupeResult.canonicalId : null,
                },
            });

            // Check hard filters
            const filterResult = passesHardFilters(normalized);

            return NextResponse.json({
                listing,
                passesFilters: filterResult.passed,
                filterFailReasons: filterResult.reasons,
            });
        }
    } catch (error) {
        console.error('Error adding listing:', error);
        return NextResponse.json({ error: 'Failed to add listing' }, { status: 500 });
    }
}
