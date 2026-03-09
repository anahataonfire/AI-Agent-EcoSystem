// Default scoring weights - editable from UI
export interface ScoringWeights {
    // View quality (max 35)
    view_ocean: number;
    view_diamond_head: number;
    view_mountain: number;
    view_city: number;
    view_marina: number;
    view_canal: number;
    view_uncertain_penalty: number; // Multiplier for uncertain views (0.5 = half points)

    // Lanai (max 20)
    lanai: number;

    // Outdoor space (max 15)
    outdoor_private: number;
    outdoor_shared: number;

    // Amenities (max 24)
    amenity_pool: number;
    amenity_bbq: number;
    amenity_pickleball: number;
    amenity_gym: number;

    // Bonus (max 5)
    renovation_bonus: number;

    // Penalties
    penalty_portable_ac: number;
    penalty_high_app_fee: number;
}

export const DEFAULT_WEIGHTS: ScoringWeights = {
    // View quality
    view_ocean: 20,
    view_diamond_head: 15,
    view_mountain: 10,
    view_city: 8,
    view_marina: 6,
    view_canal: 6,
    view_uncertain_penalty: 0.5,

    // Lanai
    lanai: 20,

    // Outdoor space
    outdoor_private: 15,
    outdoor_shared: 8,

    // Amenities
    amenity_pool: 8,
    amenity_bbq: 6,
    amenity_pickleball: 10,
    amenity_gym: 4,

    // Bonus
    renovation_bonus: 5,

    // Penalties
    penalty_portable_ac: -10,
    penalty_high_app_fee: -5,
};

export interface ScoreBreakdown {
    view: number;
    viewDetails: { tag: string; points: number; uncertain: boolean }[];
    lanai: number;
    outdoor: number;
    amenities: number;
    amenityDetails: { name: string; points: number }[];
    bonus: number;
    penalties: number;
    penaltyDetails: { reason: string; points: number }[];
    total: number;
}

export interface HardFilterResult {
    passed: boolean;
    failReasons: string[];
}

// Hard filter check
export function checkHardFilters(
    listing: {
        beds: number;
        baths: number;
        rentBase: number;
        rentAllInEstimate: number | null;
        parking: string;
        ac: string;
        acType?: string | null;
        wdInUnit: string;
    },
    maxBudget: number = 3400
): HardFilterResult {
    const failReasons: string[] = [];

    // 1BR/1BA only
    if (listing.beds !== 1) {
        failReasons.push(`Not 1BR (has ${listing.beds} beds)`);
    }
    if (listing.baths !== 1) {
        failReasons.push(`Not 1BA (has ${listing.baths} baths)`);
    }

    // Budget check
    const effectiveRent = listing.rentAllInEstimate ?? listing.rentBase;
    if (effectiveRent > maxBudget) {
        failReasons.push(`Over budget: $${effectiveRent} > $${maxBudget}`);
    }

    // Parking
    if (listing.parking === 'no' || listing.parking === 'street') {
        failReasons.push('No adequate parking');
    }

    // AC
    if (listing.ac === 'no') {
        failReasons.push('No AC');
    }
    if (listing.acType === 'portable') {
        // Not a hard fail, but will be penalized in scoring
    }

    // W/D in-unit
    if (listing.wdInUnit === 'no') {
        failReasons.push('No in-unit W/D');
    }

    return {
        passed: failReasons.length === 0,
        failReasons,
    };
}

// Score a listing
export function scoreListing(
    listing: {
        viewTags: string[];
        lanai: string;
        outdoorSpace: string;
        amenities: string[];
        acType?: string | null;
        description?: string | null;
    },
    weights: ScoringWeights = DEFAULT_WEIGHTS
): ScoreBreakdown {
    const breakdown: ScoreBreakdown = {
        view: 0,
        viewDetails: [],
        lanai: 0,
        outdoor: 0,
        amenities: 0,
        amenityDetails: [],
        bonus: 0,
        penalties: 0,
        penaltyDetails: [],
        total: 0,
    };

    // View scoring (take best view, don't stack all)
    const viewScores: { tag: string; points: number; uncertain: boolean }[] = [];
    const viewTagSet = new Set(listing.viewTags.map((t) => t.toLowerCase()));

    const viewMap: Record<string, number> = {
        ocean: weights.view_ocean,
        diamond_head: weights.view_diamond_head,
        mountain: weights.view_mountain,
        city: weights.view_city,
        marina: weights.view_marina,
        canal: weights.view_canal,
    };

    for (const [tag, points] of Object.entries(viewMap)) {
        if (viewTagSet.has(tag)) {
            // Check if uncertain (would need more sophisticated detection)
            const uncertain = false; // TODO: detect from description
            const finalPoints = uncertain
                ? Math.round(points * weights.view_uncertain_penalty)
                : points;
            viewScores.push({ tag, points: finalPoints, uncertain });
        }
    }

    // Take highest scoring view
    if (viewScores.length > 0) {
        viewScores.sort((a, b) => b.points - a.points);
        breakdown.view = viewScores[0].points;
        breakdown.viewDetails = [viewScores[0]];
        // Add secondary views at reduced rate
        for (let i = 1; i < Math.min(viewScores.length, 2); i++) {
            const secondary = viewScores[i];
            const reducedPoints = Math.round(secondary.points * 0.3);
            breakdown.view += reducedPoints;
            breakdown.viewDetails.push({ ...secondary, points: reducedPoints });
        }
    }

    // Lanai
    if (listing.lanai === 'yes') {
        breakdown.lanai = weights.lanai;
    }

    // Outdoor space
    if (listing.outdoorSpace === 'private') {
        breakdown.outdoor = weights.outdoor_private;
    } else if (listing.outdoorSpace === 'shared') {
        breakdown.outdoor = weights.outdoor_shared;
    }

    // Amenities
    const amenitySet = new Set(listing.amenities.map((a) => a.toLowerCase()));
    const amenityMap: Record<string, number> = {
        pool: weights.amenity_pool,
        bbq: weights.amenity_bbq,
        pickleball: weights.amenity_pickleball,
        gym: weights.amenity_gym,
    };

    for (const [name, points] of Object.entries(amenityMap)) {
        if (amenitySet.has(name)) {
            breakdown.amenities += points;
            breakdown.amenityDetails.push({ name, points });
        }
    }

    // Bonus for renovation cues
    if (listing.description) {
        const renovationCues = [
            'renovated',
            'remodeled',
            'updated',
            'modern',
            'new appliances',
            'newly',
        ];
        const descLower = listing.description.toLowerCase();
        if (renovationCues.some((cue) => descLower.includes(cue))) {
            breakdown.bonus = weights.renovation_bonus;
        }
    }

    // Penalties
    if (listing.acType === 'portable') {
        breakdown.penalties += weights.penalty_portable_ac;
        breakdown.penaltyDetails.push({
            reason: 'Portable AC only',
            points: weights.penalty_portable_ac,
        });
    }

    // Calculate total
    breakdown.total =
        breakdown.view +
        breakdown.lanai +
        breakdown.outdoor +
        breakdown.amenities +
        breakdown.bonus +
        breakdown.penalties;

    // Clamp to 0-100
    breakdown.total = Math.max(0, Math.min(100, breakdown.total));

    return breakdown;
}
