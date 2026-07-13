// API route for listing operations

import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';

export async function GET(request: NextRequest) {
    const searchParams = request.nextUrl.searchParams;

    // Parse filter params
    const neighborhoods = searchParams.get('neighborhoods')?.split(',') || [];
    const minRent = parseInt(searchParams.get('minRent') || '0');
    const maxRent = parseInt(searchParams.get('maxRent') || '10000');
    const requireParking = searchParams.get('requireParking') === 'true';
    const requireAC = searchParams.get('requireAC') === 'true';
    const requireWD = searchParams.get('requireWD') === 'true';
    const status = searchParams.get('status');

    try {
        // Build where clause
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const where: any = {
            // Only show canonical listings (not duplicates)
            canonicalListingId: null,
        };

        if (neighborhoods.length > 0) {
            where.neighborhoodLabel = { in: neighborhoods };
        }

        // Use rentAllInEstimate if available, else rentBase
        where.OR = [
            { rentAllInEstimate: { gte: minRent, lte: maxRent } },
            { rentAllInEstimate: null, rentBase: { gte: minRent, lte: maxRent } },
        ];

        if (requireParking) {
            where.parking = 'yes';
        }

        if (requireAC) {
            where.ac = 'yes';
        }

        if (requireWD) {
            where.wdInUnit = 'yes';
        }

        if (status) {
            where.status = status;
        }

        const listings = await prisma.listing.findMany({
            where,
            orderBy: { scoreTotal: 'desc' },
            take: 100,
        });

        // Transform for frontend
        const transformed = listings.map((listing: typeof listings[number]) => ({
            id: listing.id,
            title: listing.title,
            url: listing.url,
            source: listing.source,
            neighborhoodLabel: listing.neighborhoodLabel,
            rentBase: listing.rentBase,
            rentAllInEstimate: listing.rentAllInEstimate,
            sqft: listing.sqft,
            parking: listing.parking,
            ac: listing.ac,
            wdInUnit: listing.wdInUnit,
            lanai: listing.lanai,
            outdoorSpace: listing.outdoorSpace,
            viewTags: JSON.parse(listing.viewTags),
            amenities: JSON.parse(listing.amenities),
            photos: JSON.parse(listing.photos),
            scoreTotal: listing.scoreTotal,
            scoreBreakdown: JSON.parse(listing.scoreBreakdown),
            status: listing.status,
            redFlags: JSON.parse(listing.redFlags),
            notes: listing.notes,
            postedDate: listing.postedDate,
            lastSeenDate: listing.lastSeenDate,
        }));

        return NextResponse.json({ listings: transformed });
    } catch (error) {
        console.error('Error fetching listings:', error);
        return NextResponse.json({ error: 'Failed to fetch listings' }, { status: 500 });
    }
}

export async function PATCH(request: NextRequest) {
    try {
        const body = await request.json();
        const { id, status, notes } = body;

        if (!id) {
            return NextResponse.json({ error: 'Missing listing ID' }, { status: 400 });
        }

        const updateData: Record<string, unknown> = {};
        if (status) updateData.status = status;
        if (notes !== undefined) updateData.notes = notes;

        const updated = await prisma.listing.update({
            where: { id },
            data: updateData,
        });

        return NextResponse.json({ listing: updated });
    } catch (error) {
        console.error('Error updating listing:', error);
        return NextResponse.json({ error: 'Failed to update listing' }, { status: 500 });
    }
}
