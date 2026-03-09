// All-in cost estimation parser

export interface ParsedFees {
    parking: number | null;
    utilities: number | null;
    other: number | null;
    parkingIncluded: boolean | null;
    utilitiesIncluded: string[]; // ['water', 'electric', 'internet']
    uncertainties: string[];
}

// Common fee patterns
const PARKING_FEE_PATTERNS = [
    /parking[:\s]+\$?(\d+)(?:\/mo|\/month)?/i,
    /\$(\d+)(?:\/mo|\/month)?\s*(?:for\s+)?parking/i,
    /parking\s+(?:is\s+)?(?:an?\s+)?additional\s+\$?(\d+)/i,
    /add(?:itional)?\s+\$?(\d+)\s+(?:for\s+)?parking/i,
];

const PARKING_INCLUDED_PATTERNS = [
    /parking\s+included/i,
    /includes?\s+(?:one|1|a)\s+parking/i,
    /free\s+parking/i,
    /(?:one|1)\s+(?:assigned\s+)?parking\s+(?:spot|space|stall)\s+included/i,
    /parking\s+(?:spot|space|stall)\s+(?:is\s+)?included/i,
];

const NO_PARKING_PATTERNS = [
    /no\s+parking/i,
    /street\s+parking\s+only/i,
    /parking\s+not\s+(?:included|available)/i,
];

const UTILITIES_INCLUDED_PATTERNS: { pattern: RegExp; utility: string }[] = [
    { pattern: /water\s+(?:is\s+)?included/i, utility: 'water' },
    { pattern: /includes?\s+water/i, utility: 'water' },
    { pattern: /electric(?:ity)?\s+(?:is\s+)?included/i, utility: 'electric' },
    { pattern: /includes?\s+electric/i, utility: 'electric' },
    { pattern: /internet\s+(?:is\s+)?included/i, utility: 'internet' },
    { pattern: /includes?\s+internet/i, utility: 'internet' },
    { pattern: /wifi\s+(?:is\s+)?included/i, utility: 'internet' },
    { pattern: /cable\s+(?:is\s+)?included/i, utility: 'cable' },
    { pattern: /all\s+utilities?\s+(?:are\s+)?included/i, utility: 'all' },
    { pattern: /utilities?\s+included/i, utility: 'all' },
];

const TENANT_PAYS_PATTERNS = [
    /tenant\s+pays?\s+(?:for\s+)?(?:all\s+)?utilities/i,
    /utilities?\s+not\s+included/i,
    /(?:electric|water)\s+(?:is\s+)?additional/i,
];

export function parseFees(text: string): ParsedFees {
    const result: ParsedFees = {
        parking: null,
        utilities: null,
        other: null,
        parkingIncluded: null,
        utilitiesIncluded: [],
        uncertainties: [],
    };

    if (!text) {
        result.uncertainties.push('No description to parse');
        return result;
    }

    // Check parking
    for (const pattern of PARKING_INCLUDED_PATTERNS) {
        if (pattern.test(text)) {
            result.parkingIncluded = true;
            result.parking = 0;
            break;
        }
    }

    if (result.parkingIncluded === null) {
        for (const pattern of NO_PARKING_PATTERNS) {
            if (pattern.test(text)) {
                result.parkingIncluded = false;
                result.uncertainties.push('No parking available');
                break;
            }
        }
    }

    if (result.parkingIncluded === null) {
        for (const pattern of PARKING_FEE_PATTERNS) {
            const match = text.match(pattern);
            if (match) {
                result.parking = parseInt(match[1], 10);
                result.parkingIncluded = false;
                break;
            }
        }
    }

    if (result.parkingIncluded === null) {
        result.uncertainties.push('Parking cost unknown');
    }

    // Check utilities
    for (const { pattern, utility } of UTILITIES_INCLUDED_PATTERNS) {
        if (pattern.test(text)) {
            if (utility === 'all') {
                result.utilitiesIncluded = ['water', 'electric', 'internet'];
                result.utilities = 0;
                break;
            } else if (!result.utilitiesIncluded.includes(utility)) {
                result.utilitiesIncluded.push(utility);
            }
        }
    }

    // Check if tenant pays utilities
    for (const pattern of TENANT_PAYS_PATTERNS) {
        if (pattern.test(text)) {
            if (result.utilitiesIncluded.length === 0) {
                result.uncertainties.push('Tenant pays utilities (amount TBD)');
            }
            break;
        }
    }

    if (result.utilities === null && result.utilitiesIncluded.length === 0) {
        result.uncertainties.push('Utility costs unknown');
    }

    return result;
}

export function computeAllInEstimate(
    rentBase: number,
    fees: ParsedFees
): { estimate: number | null; confidence: 'high' | 'medium' | 'low' } {
    // If we have high uncertainty, return null
    if (fees.uncertainties.length > 1) {
        return { estimate: null, confidence: 'low' };
    }

    let estimate = rentBase;
    let confidence: 'high' | 'medium' | 'low' = 'high';

    // Add parking if known
    if (fees.parking !== null) {
        estimate += fees.parking;
    } else if (fees.parkingIncluded === false) {
        // Unknown parking fee, estimate $150
        estimate += 150;
        confidence = 'medium';
    } else if (fees.parkingIncluded === null) {
        confidence = 'medium';
    }

    // Add utilities if not included
    if (fees.utilities !== null) {
        estimate += fees.utilities;
    } else if (fees.utilitiesIncluded.length === 0) {
        // Unknown utilities, might add $100-200 estimate
        // For now, don't add to keep estimate conservative
        if (confidence === 'high') confidence = 'medium';
    }

    // Add other fees if known
    if (fees.other !== null) {
        estimate += fees.other;
    }

    if (fees.uncertainties.length > 0) {
        if (confidence === 'high') confidence = 'medium';
    }

    return { estimate, confidence };
}

// Generate questions for uncertain fields
export function generateVerificationQuestions(fees: ParsedFees): string[] {
    const questions: string[] = [];

    if (fees.parkingIncluded === null) {
        questions.push('Is parking included in the rent? If not, what is the monthly parking fee?');
    } else if (fees.parkingIncluded === false && fees.parking === null) {
        questions.push('What is the monthly parking fee?');
    }

    if (fees.utilitiesIncluded.length === 0) {
        questions.push('Are any utilities included? (water, electric, internet)');
    } else if (!fees.utilitiesIncluded.includes('electric')) {
        questions.push('Is electricity included or tenant-paid?');
    }

    return questions;
}
