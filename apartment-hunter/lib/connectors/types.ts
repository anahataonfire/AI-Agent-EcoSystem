// Pluggable connector interface for listing sources

import { RawListing } from '../normalizer';

export type ComplianceMode = 'url-only' | 'broad-search';

export interface SearchOptions {
    neighborhoods?: string[];
    minRent?: number;
    maxRent?: number;
    beds?: number;
    baths?: number;
}

export interface ConnectorConfig {
    enabled: boolean;
    complianceMode: ComplianceMode;
    rateLimit?: number; // requests per minute
    userAgent?: string;
}

export interface ConnectorResult {
    listings: RawListing[];
    errors: string[];
    scanned: number;
}

export interface ListingConnector {
    name: string;
    displayName: string;

    // Check if connector is available/configured
    isAvailable(): Promise<boolean>;

    // Broad search (if compliance mode allows)
    search(options: SearchOptions): Promise<ConnectorResult>;

    // Parse a specific URL (always available)
    parseUrl(url: string): Promise<RawListing | null>;

    // Current compliance mode
    getComplianceMode(): ComplianceMode;
    setComplianceMode(mode: ComplianceMode): void;
}

// Base connector with common functionality
export abstract class BaseConnector implements ListingConnector {
    abstract name: string;
    abstract displayName: string;

    protected complianceMode: ComplianceMode = 'url-only';
    protected config: ConnectorConfig = {
        enabled: true,
        complianceMode: 'url-only',
    };

    async isAvailable(): Promise<boolean> {
        return this.config.enabled;
    }

    getComplianceMode(): ComplianceMode {
        return this.complianceMode;
    }

    setComplianceMode(mode: ComplianceMode): void {
        this.complianceMode = mode;
    }

    abstract search(options: SearchOptions): Promise<ConnectorResult>;
    abstract parseUrl(url: string): Promise<RawListing | null>;

    // Rate limiting helper
    protected async rateLimit(): Promise<void> {
        if (this.config.rateLimit) {
            const delayMs = (60 * 1000) / this.config.rateLimit;
            await new Promise((resolve) => setTimeout(resolve, delayMs));
        }
    }
}

// Registry for all connectors
class ConnectorRegistry {
    private connectors: Map<string, ListingConnector> = new Map();

    register(connector: ListingConnector): void {
        this.connectors.set(connector.name, connector);
    }

    get(name: string): ListingConnector | undefined {
        return this.connectors.get(name);
    }

    getAll(): ListingConnector[] {
        return Array.from(this.connectors.values());
    }

    getEnabled(): ListingConnector[] {
        return this.getAll().filter(async (c) => await c.isAvailable());
    }
}

export const connectorRegistry = new ConnectorRegistry();

// Helper to determine which connector to use for a URL
export function getConnectorForUrl(url: string): ListingConnector | null {
    const urlLower = url.toLowerCase();

    if (urlLower.includes('craigslist.org')) {
        return connectorRegistry.get('craigslist') || null;
    }
    if (urlLower.includes('zillow.com')) {
        return connectorRegistry.get('zillow') || null;
    }
    if (urlLower.includes('apartments.com')) {
        return connectorRegistry.get('apartments') || null;
    }

    // Fall back to generic connector
    return connectorRegistry.get('generic') || null;
}
