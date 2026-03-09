// Neighborhood classification for Honolulu

export type NeighborhoodLabel =
    | 'Waikiki'
    | 'Ala Moana'
    | 'Diamond Head'
    | 'Downtown'
    | 'Across Ala Wai'
    | 'Unknown';

// Keywords and patterns for neighborhood detection
const NEIGHBORHOOD_PATTERNS: { label: NeighborhoodLabel; patterns: RegExp[] }[] = [
    {
        label: 'Waikiki',
        patterns: [
            /waikiki/i,
            /kalakaua\s+ave/i,
            /kuhio\s+ave/i,
            /ala\s+wai\s+blvd/i,
            /royal\s+hawaiian/i,
            /waikiki\s+beach/i,
        ],
    },
    {
        label: 'Ala Moana',
        patterns: [
            /ala\s+moana/i,
            /ward\s+(?:village|center|ave)/i,
            /kakaako/i,
            /kaka'ako/i,
            /piikoi/i,
            /kapiolani\s+blvd/i,
        ],
    },
    {
        label: 'Diamond Head',
        patterns: [
            /diamond\s+head/i,
            /kahala/i,
            /kapahulu/i,
            /monsarrat/i,
            /paki\s+ave/i,
            /gold\s+coast/i,
        ],
    },
    {
        label: 'Downtown',
        patterns: [
            /downtown/i,
            /chinatown/i,
            /civic\s+center/i,
            /capitol\s+district/i,
            /alakea/i,
            /bishop\s+st/i,
            /merchant\s+st/i,
        ],
    },
    {
        label: 'Across Ala Wai',
        patterns: [
            /mccully/i,
            /moiliili/i,
            /mo'ili'ili/i,
            /date\s+st/i,
            /university\s+ave/i,
            /king\s+st.*(?:near|by).*university/i,
            /manoa/i,
        ],
    },
];

// Approximate bounding boxes for neighborhoods (lat/lng)
const NEIGHBORHOOD_BOUNDS: {
    label: NeighborhoodLabel;
    minLat: number;
    maxLat: number;
    minLng: number;
    maxLng: number;
}[] = [
        {
            label: 'Waikiki',
            minLat: 21.265,
            maxLat: 21.285,
            minLng: -157.84,
            maxLng: -157.815,
        },
        {
            label: 'Ala Moana',
            minLat: 21.285,
            maxLat: 21.305,
            minLng: -157.865,
            maxLng: -157.84,
        },
        {
            label: 'Diamond Head',
            minLat: 21.255,
            maxLat: 21.275,
            minLng: -157.815,
            maxLng: -157.79,
        },
        {
            label: 'Downtown',
            minLat: 21.305,
            maxLat: 21.32,
            minLng: -157.875,
            maxLng: -157.855,
        },
        {
            label: 'Across Ala Wai',
            minLat: 21.285,
            maxLat: 21.305,
            minLng: -157.84,
            maxLng: -157.815,
        },
    ];

export function classifyNeighborhood(
    addressRaw?: string | null,
    title?: string | null,
    description?: string | null,
    lat?: number | null,
    lng?: number | null
): NeighborhoodLabel {
    // First try lat/lng if available
    if (lat && lng) {
        for (const bounds of NEIGHBORHOOD_BOUNDS) {
            if (
                lat >= bounds.minLat &&
                lat <= bounds.maxLat &&
                lng >= bounds.minLng &&
                lng <= bounds.maxLng
            ) {
                return bounds.label;
            }
        }
    }

    // Fall back to text pattern matching
    const textToSearch = [addressRaw, title, description]
        .filter(Boolean)
        .join(' ');

    for (const { label, patterns } of NEIGHBORHOOD_PATTERNS) {
        for (const pattern of patterns) {
            if (pattern.test(textToSearch)) {
                return label;
            }
        }
    }

    return 'Unknown';
}

// Check if a neighborhood is in the primary search area
export function isPrimaryNeighborhood(label: NeighborhoodLabel): boolean {
    return ['Waikiki', 'Ala Moana', 'Diamond Head'].includes(label);
}

// Check if a neighborhood is in any target area
export function isTargetNeighborhood(
    label: NeighborhoodLabel,
    includeSecondary: boolean = true
): boolean {
    const primary = ['Waikiki', 'Ala Moana', 'Diamond Head'];
    const secondary = ['Downtown', 'Across Ala Wai'];

    if (primary.includes(label)) return true;
    if (includeSecondary && secondary.includes(label)) return true;
    return false;
}
