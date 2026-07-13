// Generic website scraper for property manager sites

import { BaseConnector, SearchOptions, ConnectorResult } from './types';
import { RawListing } from '../normalizer';

export class GenericConnector extends BaseConnector {
    name = 'generic';
    displayName = 'Generic Website';

    async isAvailable(): Promise<boolean> {
        return true;
    }

    async search(_options: SearchOptions): Promise<ConnectorResult> {
        // Generic connector only supports URL parsing
        return {
            listings: [],
            errors: ['Generic connector only supports URL-based parsing'],
            scanned: 0,
        };
    }

    async parseUrl(url: string): Promise<RawListing | null> {
        try {
            await this.rateLimit();

            const response = await fetch(url, {
                headers: {
                    'User-Agent': 'ApartmentHunter/1.0 (Educational Project)',
                    'Accept': 'text/html,application/xhtml+xml',
                },
            });

            if (!response.ok) {
                console.error(`Failed to fetch URL: ${response.status}`);
                return null;
            }

            const html = await response.text();
            return this.parseGenericHtml(html, url);
        } catch (error) {
            console.error(`Error parsing URL: ${error}`);
            return null;
        }
    }

    private parseGenericHtml(html: string, url: string): RawListing | null {
        // Try to extract common patterns

        // Title from og:title, title tag, or h1
        let title = this.extractMeta(html, 'og:title') ||
            this.extractTag(html, 'title') ||
            this.extractFirstH1(html) ||
            'Unknown Listing';

        // Description from og:description or meta description
        const description = this.extractMeta(html, 'og:description') ||
            this.extractMetaName(html, 'description') ||
            '';

        // Price patterns
        const pricePatterns = [
            /\$\s*([\d,]+)\s*(?:\/\s*(?:mo|month))?/i,
            /rent[:\s]+\$?\s*([\d,]+)/i,
            /price[:\s]+\$?\s*([\d,]+)/i,
        ];
        let rent = 0;
        for (const pattern of pricePatterns) {
            const match = html.match(pattern);
            if (match) {
                rent = parseInt(match[1].replace(',', ''), 10);
                if (rent > 500 && rent < 10000) break; // Reasonable rent range
            }
        }

        // Beds/baths patterns
        const bedsMatch = html.match(/(\d+)\s*(?:bed(?:room)?s?|br)/i);
        const bathsMatch = html.match(/(\d+(?:\.\d+)?)\s*(?:bath(?:room)?s?|ba)/i);
        const sqftMatch = html.match(/([\d,]+)\s*(?:sq\.?\s*ft|sqft|square\s*feet)/i);

        const beds = bedsMatch ? parseInt(bedsMatch[1], 10) : 1;
        const baths = bathsMatch ? parseFloat(bathsMatch[1]) : 1;
        const sqft = sqftMatch ? parseInt(sqftMatch[1].replace(',', ''), 10) : undefined;

        // Photos from og:image or img tags
        const photos: string[] = [];
        const ogImage = this.extractMeta(html, 'og:image');
        if (ogImage) photos.push(ogImage);

        // Try to find property/apartment images
        const imgRegex = /<img[^>]+src="([^"]+)"[^>]*>/gi;
        let imgMatch;
        while ((imgMatch = imgRegex.exec(html)) !== null && photos.length < 10) {
            const src = imgMatch[1];
            // Filter for likely property photos
            if (
                src.includes('property') ||
                src.includes('unit') ||
                src.includes('apartment') ||
                src.includes('photo') ||
                src.includes('image')
            ) {
                if (!photos.includes(src)) {
                    photos.push(src);
                }
            }
        }

        // Address
        const addressPatterns = [
            /<address[^>]*>([^<]+)<\/address>/i,
            /address[:\s]+([^<\n]+)/i,
            /location[:\s]+([^<\n]+)/i,
        ];
        let addressRaw: string | undefined;
        for (const pattern of addressPatterns) {
            const match = html.match(pattern);
            if (match) {
                addressRaw = match[1].trim();
                break;
            }
        }

        // Extract features from common list patterns
        const rawFeatures: string[] = [];
        const featurePatterns = [
            /<li[^>]*class="[^"]*(?:feature|amenity)[^"]*"[^>]*>([^<]+)<\/li>/gi,
            /<span[^>]*class="[^"]*(?:feature|amenity)[^"]*"[^>]*>([^<]+)<\/span>/gi,
        ];
        for (const pattern of featurePatterns) {
            let featureMatch;
            while ((featureMatch = pattern.exec(html)) !== null) {
                rawFeatures.push(featureMatch[1].trim());
            }
        }

        // Only return if we have minimum required data
        if (!rent || rent < 500) {
            console.warn('Could not extract valid rent from generic page');
            return null;
        }

        return {
            source: 'pm_site',
            sourceId: this.generateId(url),
            url,
            title,
            description,
            addressRaw,
            rent,
            beds,
            baths,
            sqft,
            photos,
            rawFeatures,
        };
    }

    private extractMeta(html: string, property: string): string | null {
        const regex = new RegExp(
            `<meta[^>]+(?:property|name)="${property}"[^>]+content="([^"]+)"`,
            'i'
        );
        const match = html.match(regex);
        return match ? match[1] : null;
    }

    private extractMetaName(html: string, name: string): string | null {
        const regex = new RegExp(
            `<meta[^>]+name="${name}"[^>]+content="([^"]+)"`,
            'i'
        );
        const match = html.match(regex);
        return match ? match[1] : null;
    }

    private extractTag(html: string, tag: string): string | null {
        const regex = new RegExp(`<${tag}[^>]*>([^<]+)</${tag}>`, 'i');
        const match = html.match(regex);
        return match ? match[1].trim() : null;
    }

    private extractFirstH1(html: string): string | null {
        const match = html.match(/<h1[^>]*>([^<]+)<\/h1>/i);
        return match ? match[1].trim() : null;
    }

    private generateId(url: string): string {
        // Simple hash of URL
        let hash = 0;
        for (let i = 0; i < url.length; i++) {
            const char = url.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash;
        }
        return `generic-${Math.abs(hash)}`;
    }
}

export const genericConnector = new GenericConnector();
