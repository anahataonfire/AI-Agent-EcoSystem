// Craigslist connector for Honolulu housing listings

import { BaseConnector, SearchOptions, ConnectorResult } from './types';
import { RawListing } from '../normalizer';

// Craigslist RSS feed URLs for Honolulu
const HONOLULU_CL_BASE = 'https://honolulu.craigslist.org';
const HONOLULU_HOUSING_RSS = `${HONOLULU_CL_BASE}/search/apa?format=rss`;

export class CraigslistConnector extends BaseConnector {
    name = 'craigslist';
    displayName = 'Craigslist Honolulu';

    async isAvailable(): Promise<boolean> {
        return true; // Craigslist is generally accessible
    }

    async search(options: SearchOptions): Promise<ConnectorResult> {
        const result: ConnectorResult = {
            listings: [],
            errors: [],
            scanned: 0,
        };

        // In URL-only mode, don't do broad search
        if (this.complianceMode === 'url-only') {
            result.errors.push('Broad search disabled in URL-only compliance mode');
            return result;
        }

        try {
            // Build search URL with filters
            const params = new URLSearchParams();
            params.set('format', 'rss');

            // 1BR filter
            if (options.beds) {
                params.set('min_bedrooms', options.beds.toString());
                params.set('max_bedrooms', options.beds.toString());
            }

            // Price range
            if (options.minRent) {
                params.set('min_price', options.minRent.toString());
            }
            if (options.maxRent) {
                params.set('max_price', options.maxRent.toString());
            }

            // Housing type: apartment
            params.set('housing_type', '1'); // 1 = apartment

            const searchUrl = `${HONOLULU_CL_BASE}/search/apa?${params.toString()}`;

            await this.rateLimit();

            const response = await fetch(searchUrl, {
                headers: {
                    'User-Agent': 'ApartmentHunter/1.0 (Educational Project)',
                },
            });

            if (!response.ok) {
                result.errors.push(`Failed to fetch Craigslist: ${response.status}`);
                return result;
            }

            const xml = await response.text();
            const listings = this.parseRssFeed(xml);

            result.listings = listings;
            result.scanned = listings.length;

        } catch (error) {
            result.errors.push(`Craigslist search error: ${error}`);
        }

        return result;
    }

    async parseUrl(url: string): Promise<RawListing | null> {
        if (!url.includes('craigslist.org')) {
            return null;
        }

        try {
            await this.rateLimit();

            const response = await fetch(url, {
                headers: {
                    'User-Agent': 'ApartmentHunter/1.0 (Educational Project)',
                },
            });

            if (!response.ok) {
                console.error(`Failed to fetch Craigslist listing: ${response.status}`);
                return null;
            }

            const html = await response.text();
            return this.parseListingHtml(html, url);
        } catch (error) {
            console.error(`Error parsing Craigslist URL: ${error}`);
            return null;
        }
    }

    private parseRssFeed(xml: string): RawListing[] {
        const listings: RawListing[] = [];

        // Simple RSS parsing (in production, use a proper XML parser)
        const itemRegex = /<item>([\s\S]*?)<\/item>/g;
        let match;

        while ((match = itemRegex.exec(xml)) !== null) {
            const item = match[1];

            const title = this.extractTag(item, 'title');
            const link = this.extractTag(item, 'link');
            const description = this.extractTag(item, 'description');
            const pubDate = this.extractTag(item, 'dc:date') || this.extractTag(item, 'pubDate');

            if (title && link) {
                // Extract price from title (e.g., "$2500 / 1br - Nice apartment")
                const priceMatch = title.match(/\$(\d{1,2},?\d{3})/);
                const rent = priceMatch ? parseInt(priceMatch[1].replace(',', ''), 10) : 0;

                // Extract beds from title
                const bedsMatch = title.match(/(\d+)\s*br/i);
                const beds = bedsMatch ? parseInt(bedsMatch[1], 10) : 1;

                // Extract sqft if present
                const sqftMatch = title.match(/(\d{3,4})\s*(?:sf|sqft|sq\s*ft)/i);
                const sqft = sqftMatch ? parseInt(sqftMatch[1], 10) : undefined;

                listings.push({
                    source: 'craigslist',
                    sourceId: this.extractListingId(link),
                    url: link,
                    title: this.cleanTitle(title),
                    description: this.decodeHtml(description || ''),
                    rent,
                    beds,
                    baths: 1, // CL usually doesn't specify, assume 1 for 1br
                    sqft,
                    postedDate: pubDate ? new Date(pubDate) : undefined,
                });
            }
        }

        return listings;
    }

    private parseListingHtml(html: string, url: string): RawListing | null {
        try {
            // Extract title
            const titleMatch = html.match(/<span id="titletextonly"[^>]*>([^<]+)<\/span>/);
            const title = titleMatch ? titleMatch[1].trim() : '';

            // Extract price
            const priceMatch = html.match(/<span class="price">\$([^<]+)<\/span>/);
            const rent = priceMatch ? parseInt(priceMatch[1].replace(',', ''), 10) : 0;

            // Extract description
            const descMatch = html.match(/<section id="postingbody"[^>]*>([\s\S]*?)<\/section>/);
            let description = '';
            if (descMatch) {
                description = descMatch[1]
                    .replace(/<[^>]+>/g, ' ')
                    .replace(/\s+/g, ' ')
                    .trim();
            }

            // Extract housing info (beds/baths/sqft)
            const housingMatch = html.match(/<span class="housing">([^<]+)<\/span>/);
            let beds = 1, baths = 1, sqft: number | undefined;
            if (housingMatch) {
                const housing = housingMatch[1];
                const bedsMatch = housing.match(/(\d+)br/i);
                const bathsMatch = housing.match(/(\d+(?:\.\d+)?)ba/i);
                const sqftMatch = housing.match(/(\d+)ft/i);

                if (bedsMatch) beds = parseInt(bedsMatch[1], 10);
                if (bathsMatch) baths = parseFloat(bathsMatch[1]);
                if (sqftMatch) sqft = parseInt(sqftMatch[1], 10);
            }

            // Extract photos
            const photos: string[] = [];
            const photoRegex = /<img[^>]+src="([^"]*images\.craigslist\.org[^"]*)"/g;
            let photoMatch;
            while ((photoMatch = photoRegex.exec(html)) !== null) {
                photos.push(photoMatch[1]);
            }

            // Extract address if present
            const addressMatch = html.match(/<div class="mapaddress">([^<]+)<\/div>/);
            const addressRaw = addressMatch ? addressMatch[1].trim() : undefined;

            // Extract lat/lng if present
            const latMatch = html.match(/data-latitude="([^"]+)"/);
            const lngMatch = html.match(/data-longitude="([^"]+)"/);
            const lat = latMatch ? parseFloat(latMatch[1]) : undefined;
            const lng = lngMatch ? parseFloat(lngMatch[1]) : undefined;

            // Extract attributes
            const attrRegex = /<span class="(?:shared-line-bubble|housing_movein_now|otherpostings)"[^>]*>([^<]+)<\/span>/g;
            const rawFeatures: string[] = [];
            let attrMatch;
            while ((attrMatch = attrRegex.exec(html)) !== null) {
                rawFeatures.push(attrMatch[1].trim());
            }

            // Also extract from attrgroup spans
            const attrGroupRegex = /<span>([^<]+)<\/span>/g;
            const attrSection = html.match(/<p class="attrgroup">([\s\S]*?)<\/p>/g);
            if (attrSection) {
                for (const section of attrSection) {
                    let m;
                    while ((m = attrGroupRegex.exec(section)) !== null) {
                        rawFeatures.push(m[1].trim());
                    }
                }
            }

            return {
                source: 'craigslist',
                sourceId: this.extractListingId(url),
                url,
                title,
                description,
                addressRaw,
                lat,
                lng,
                rent,
                beds,
                baths,
                sqft,
                photos,
                rawFeatures,
            };
        } catch (error) {
            console.error(`Error parsing Craigslist HTML: ${error}`);
            return null;
        }
    }

    private extractTag(xml: string, tag: string): string | null {
        const regex = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`);
        const match = xml.match(regex);
        return match ? match[1].trim() : null;
    }

    private extractListingId(url: string): string {
        const match = url.match(/\/(\d+)\.html/);
        return match ? match[1] : url;
    }

    private cleanTitle(title: string): string {
        // Remove price and br info from title
        return title
            .replace(/\$[\d,]+\s*\/?\s*/g, '')
            .replace(/\d+br\s*-?\s*/gi, '')
            .replace(/\s+/g, ' ')
            .trim();
    }

    private decodeHtml(html: string): string {
        return html
            .replace(/&lt;/g, '<')
            .replace(/&gt;/g, '>')
            .replace(/&amp;/g, '&')
            .replace(/&quot;/g, '"')
            .replace(/&#39;/g, "'")
            .replace(/<[^>]+>/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
    }
}

// Export singleton instance
export const craigslistConnector = new CraigslistConnector();
