// Listing normalizer - converts raw data from connectors to canonical schema

import { parseFees, computeAllInEstimate } from './cost-parser';
import { classifyNeighborhood } from './neighborhoods';
import { generateDedupeKey } from './dedupe';
import { scoreListing, checkHardFilters, type ScoreBreakdown } from './scoring';

// Raw listing from any connector
export interface RawListing {
    source: string;
    sourceId?: string;
    url: string;
    title: string;
    description?: string;
    addressRaw?: string;
    buildingName?: string;
    lat?: number;
    lng?: number;
    rent: number; // Base rent
    beds: number;
    baths: number;
    sqft?: number;
    photos?: string[];
    availableDate?: Date;
    postedDate?: Date;

    // Raw feature flags from source
    rawFeatures?: string[];
}

// Normalized listing ready for database
export interface NormalizedListing {
    source: string;
    sourceId: string | null;
    url: string;
    title: string;
    description: string | null;
    addressRaw: string | null;
    buildingName: string | null;
    lat: number | null;
    lng: number | null;
    neighborhoodLabel: string;
    rentBase: number;
    feesParsed: string; // JSON
    rentAllInEstimate: number | null;
    beds: number;
    baths: number;
    sqft: number | null;
    parking: string;
    parkingType: string | null;
    ac: string;
    acType: string | null;
    wdInUnit: string;
    lanai: string;
    outdoorSpace: string;
    amenities: string; // JSON array
    viewTags: string; // JSON array
    photos: string; // JSON array
    availableDate: Date | null;
    postedDate: Date | null;
    dedupeKey: string | null;
    scoreTotal: number;
    scoreBreakdown: string; // JSON
    redFlags: string; // JSON array
}

// Feature detection patterns
const FEATURE_PATTERNS = {
    parking: {
        yes: [/parking\s+(?:included|available|spot|space|stall)/i, /covered\s+parking/i, /garage\s+parking/i, /assigned\s+parking/i],
        no: [/no\s+parking/i, /street\s+parking\s+only/i],
        types: {
            covered: [/covered\s+parking/i, /covered\s+stall/i],
            garage: [/garage\s+parking/i, /parking\s+garage/i],
            tandem: [/tandem\s+parking/i],
            street: [/street\s+parking/i],
        },
    },
    ac: {
        yes: [/air\s+condition/i, /\bac\b/i, /a\/c/i, /central\s+air/i, /split\s+(?:ac|a\/c)/i],
        no: [/no\s+(?:ac|a\/c|air\s+condition)/i],
        types: {
            central: [/central\s+(?:ac|a\/c|air)/i],
            split: [/split\s+(?:ac|a\/c)/i, /mini[\s-]split/i],
            window: [/window\s+(?:ac|a\/c|unit)/i],
            portable: [/portable\s+(?:ac|a\/c)/i],
        },
    },
    wdInUnit: {
        yes: [/washer\s*(?:\/|and|&)\s*dryer\s+in[\s-]?unit/i, /in[\s-]?unit\s+(?:w\/d|washer|laundry)/i, /private\s+laundry/i, /\bw\/d\s+in[\s-]?unit/i],
        no: [/shared\s+laundry/i, /coin\s+laundry/i, /laundry\s+(?:room|facility)/i, /no\s+washer/i],
    },
    lanai: {
        yes: [/lanai/i, /balcony/i, /private\s+(?:patio|terrace|deck)/i],
        no: [/no\s+(?:lanai|balcony)/i],
    },
    outdoorSpace: {
        private: [/private\s+(?:lanai|balcony|patio|terrace|yard|deck)/i, /\blanai\b/i, /\bbalcony\b/i],
        shared: [/roof(?:top)?\s+(?:deck|terrace|lounge)/i, /shared\s+(?:patio|terrace|courtyard)/i, /common\s+(?:area|space)/i],
        none: [/no\s+outdoor/i, /no\s+balcony/i],
    },
    views: {
        ocean: [/ocean\s+view/i, /oceanfront/i, /beachfront/i, /sea\s+view/i],
        diamond_head: [/diamond\s+head\s+view/i, /views?\s+of\s+diamond\s+head/i],
        mountain: [/mountain\s+view/i, /ko'olau/i, /koolau/i],
        city: [/city\s+view/i, /skyline/i, /downtown\s+view/i],
        marina: [/marina\s+view/i, /harbor\s+view/i, /yacht/i],
        canal: [/canal\s+view/i, /ala\s+wai\s+view/i],
    },
    amenities: {
        pool: [/\bpool\b/i, /swimming/i],
        bbq: [/\bbbq\b/i, /barbecue/i, /grill\s+area/i],
        pickleball: [/pickleball/i],
        gym: [/\bgym\b/i, /fitness/i, /workout/i, /exercise\s+room/i],
        tennis: [/tennis/i],
        sauna: [/sauna/i, /steam\s+room/i],
    },
};

function detectFeature(
    text: string,
    patterns: { yes?: RegExp[]; no?: RegExp[] }
): 'yes' | 'no' | 'unknown' {
    if (patterns.yes) {
        for (const p of patterns.yes) {
            if (p.test(text)) return 'yes';
        }
    }
    if (patterns.no) {
        for (const p of patterns.no) {
            if (p.test(text)) return 'no';
        }
    }
    return 'unknown';
}

function detectType(
    text: string,
    types: Record<string, RegExp[]>
): string | null {
    for (const [type, patterns] of Object.entries(types)) {
        for (const p of patterns) {
            if (p.test(text)) return type;
        }
    }
    return null;
}

function detectMultiple(
    text: string,
    patterns: Record<string, RegExp[]>
): string[] {
    const found: string[] = [];
    for (const [name, regexes] of Object.entries(patterns)) {
        for (const p of regexes) {
            if (p.test(text)) {
                found.push(name);
                break;
            }
        }
    }
    return found;
}

function detectRedFlags(text: string, listing: Partial<NormalizedListing>): string[] {
    const flags: string[] = [];

    // High application fee
    const appFeeMatch = text.match(/application\s+fee[:\s]+\$?(\d+)/i);
    if (appFeeMatch && parseInt(appFeeMatch[1]) > 100) {
        flags.push(`High application fee: $${appFeeMatch[1]}`);
    }

    // Security deposit issues
    if (/no\s+refund/i.test(text) || /non[\s-]?refundable/i.test(text)) {
        flags.push('Non-refundable fees mentioned');
    }

    // Scam indicators
    if (/wire\s+transfer/i.test(text) || /western\s+union/i.test(text)) {
        flags.push('⚠️ Potential scam: Wire transfer mentioned');
    }

    // AC issues
    if (listing.acType === 'portable') {
        flags.push('Only portable AC');
    }

    return flags;
}

export function normalizeListing(raw: RawListing): NormalizedListing {
    const text = [raw.title, raw.description, ...(raw.rawFeatures || [])].join(' ');

    // Parse fees
    const fees = parseFees(text);
    const { estimate: allInEstimate } = computeAllInEstimate(raw.rent, fees);

    // Detect features
    const parking = detectFeature(text, FEATURE_PATTERNS.parking);
    const parkingType = detectType(text, FEATURE_PATTERNS.parking.types);
    const ac = detectFeature(text, FEATURE_PATTERNS.ac);
    const acType = detectType(text, FEATURE_PATTERNS.ac.types);
    const wdInUnit = detectFeature(text, FEATURE_PATTERNS.wdInUnit);
    const lanai = detectFeature(text, FEATURE_PATTERNS.lanai);

    // Outdoor space
    let outdoorSpace: 'private' | 'shared' | 'none' | 'unknown' = 'unknown';
    for (const p of FEATURE_PATTERNS.outdoorSpace.private) {
        if (p.test(text)) { outdoorSpace = 'private'; break; }
    }
    if (outdoorSpace === 'unknown') {
        for (const p of FEATURE_PATTERNS.outdoorSpace.shared) {
            if (p.test(text)) { outdoorSpace = 'shared'; break; }
        }
    }
    if (outdoorSpace === 'unknown') {
        for (const p of FEATURE_PATTERNS.outdoorSpace.none) {
            if (p.test(text)) { outdoorSpace = 'none'; break; }
        }
    }

    // Views and amenities
    const viewTags = detectMultiple(text, FEATURE_PATTERNS.views);
    const amenities = detectMultiple(text, FEATURE_PATTERNS.amenities);

    // Classify neighborhood
    const neighborhoodLabel = classifyNeighborhood(
        raw.addressRaw,
        raw.title,
        raw.description,
        raw.lat,
        raw.lng
    );

    // Generate dedupe key
    const dedupeKey = generateDedupeKey({
        addressRaw: raw.addressRaw,
        buildingName: raw.buildingName,
        beds: raw.beds,
        baths: raw.baths,
        sqft: raw.sqft,
    });

    // Build normalized listing
    const normalized: NormalizedListing = {
        source: raw.source,
        sourceId: raw.sourceId || null,
        url: raw.url,
        title: raw.title,
        description: raw.description || null,
        addressRaw: raw.addressRaw || null,
        buildingName: raw.buildingName || null,
        lat: raw.lat || null,
        lng: raw.lng || null,
        neighborhoodLabel,
        rentBase: raw.rent,
        feesParsed: JSON.stringify(fees),
        rentAllInEstimate: allInEstimate,
        beds: raw.beds,
        baths: raw.baths,
        sqft: raw.sqft || null,
        parking,
        parkingType,
        ac,
        acType,
        wdInUnit,
        lanai,
        outdoorSpace,
        amenities: JSON.stringify(amenities),
        viewTags: JSON.stringify(viewTags),
        photos: JSON.stringify(raw.photos || []),
        availableDate: raw.availableDate || null,
        postedDate: raw.postedDate || null,
        dedupeKey,
        scoreTotal: 0,
        scoreBreakdown: '{}',
        redFlags: '[]',
    };

    // Detect red flags
    const redFlags = detectRedFlags(text, normalized);
    normalized.redFlags = JSON.stringify(redFlags);

    // Score the listing
    const breakdown = scoreListing({
        viewTags,
        lanai,
        outdoorSpace,
        amenities,
        acType,
        description: raw.description,
    });

    normalized.scoreTotal = breakdown.total;
    normalized.scoreBreakdown = JSON.stringify(breakdown);

    return normalized;
}

// Check if listing passes hard filters
export function passesHardFilters(
    normalized: NormalizedListing,
    maxBudget: number = 3400
): { passed: boolean; reasons: string[] } {
    const result = checkHardFilters(
        {
            beds: normalized.beds,
            baths: normalized.baths,
            rentBase: normalized.rentBase,
            rentAllInEstimate: normalized.rentAllInEstimate,
            parking: normalized.parking,
            ac: normalized.ac,
            acType: normalized.acType,
            wdInUnit: normalized.wdInUnit,
        },
        maxBudget
    );

    return { passed: result.passed, reasons: result.failReasons };
}
