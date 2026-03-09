// Manual connector for user-provided listings and URLs

import { BaseConnector, SearchOptions, ConnectorResult } from './types';
import { RawListing } from '../normalizer';

export interface ManualListingInput {
    url: string;
    title: string;
    description?: string;
    addressRaw?: string;
    buildingName?: string;
    rent: number;
    beds: number;
    baths: number;
    sqft?: number;
    photos?: string[];
    features?: string[];
}

export class ManualConnector extends BaseConnector {
    name = 'manual';
    displayName = 'Manual Entry';

    async isAvailable(): Promise<boolean> {
        return true; // Always available
    }

    async search(_options: SearchOptions): Promise<ConnectorResult> {
        // Manual connector doesn't support broad search
        return {
            listings: [],
            errors: [],
            scanned: 0,
        };
    }

    async parseUrl(_url: string): Promise<RawListing | null> {
        // Manual connector doesn't parse URLs automatically
        // Use createFromInput instead
        return null;
    }

    // Create a listing from manual input
    createFromInput(input: ManualListingInput): RawListing {
        return {
            source: 'manual',
            sourceId: `manual-${Date.now()}`,
            url: input.url,
            title: input.title,
            description: input.description,
            addressRaw: input.addressRaw,
            buildingName: input.buildingName,
            rent: input.rent,
            beds: input.beds,
            baths: input.baths,
            sqft: input.sqft,
            photos: input.photos,
            rawFeatures: input.features,
            postedDate: new Date(),
        };
    }
}

export const manualConnector = new ManualConnector();
