# Honolulu Apartment Hunter 🏝️

AI-assisted apartment search dashboard for finding, normalizing, ranking, and tracking 1BR/1BA rentals in Honolulu.

## Features

- **Multi-source ingestion** - Craigslist, manual URL import, generic website scraping
- **Smart normalization** - Auto-extracts parking, AC, W/D, views, amenities from descriptions
- **Transparent scoring** - See exactly why each listing got its score
- **Deduplication** - Detects same listing across multiple sources
- **Pipeline tracking** - Kanban board: New → Shortlist → Contacted → Touring → Applied
- **All-in cost estimation** - Parses fees and estimates total monthly cost
- **Compliance mode** - URL-only (safe) or broad search

## Quick Start

```bash
cd apartment-hunter

# Install dependencies
npm install

# Run database migrations
npx prisma migrate dev

# Start development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## Tech Stack

- **Framework**: Next.js 15 (App Router)
- **Database**: SQLite + Prisma ORM
- **Styling**: Tailwind CSS
- **Language**: TypeScript

## Project Structure

```
apartment-hunter/
├── app/                 # Next.js pages
│   ├── page.tsx         # Dashboard (ranked list)
│   ├── compare/         # Side-by-side comparison
│   ├── pipeline/        # Kanban board
│   ├── settings/        # Scoring weights config
│   └── api/             # API routes
├── components/          # React components
├── lib/
│   ├── connectors/      # Source connectors
│   ├── scoring.ts       # Scoring engine
│   ├── normalizer.ts    # Listing normalizer
│   ├── dedupe.ts        # Deduplication
│   ├── cost-parser.ts   # All-in cost estimation
│   └── neighborhoods.ts # Neighborhood classifier
├── prisma/
│   └── schema.prisma    # Database schema
└── config/
    └── scoring-weights.json
```

## Adding Connectors

Create a new file in `lib/connectors/`:

```typescript
import { BaseConnector, SearchOptions, ConnectorResult } from './types';
import { RawListing } from '../normalizer';

export class MyConnector extends BaseConnector {
  name = 'myconnector';
  displayName = 'My Connector';

  async search(options: SearchOptions): Promise<ConnectorResult> {
    // Implement search logic
  }

  async parseUrl(url: string): Promise<RawListing | null> {
    // Implement URL parsing
  }
}
```

Register in `lib/connectors/index.ts`:

```typescript
import { myConnector } from './myconnector';
connectorRegistry.register(myConnector);
```

## Scoring Weights

Default scoring (0-100 scale):

| Category | Points |
|----------|--------|
| Ocean view | +20 |
| Diamond Head view | +15 |
| Mountain view | +10 |
| City view | +8 |
| Lanai | +20 |
| Private outdoor | +15 |
| Shared outdoor | +8 |
| Pool | +8 |
| BBQ | +6 |
| Pickleball | +10 |
| Gym | +4 |
| Portable AC | -10 |

Edit in Settings page or `config/scoring-weights.json`.

## Hard Filters (Auto-exclude)

- Not 1BR/1BA
- Over budget ($3,400 all-in)
- No parking
- No AC
- No in-unit W/D

## Compliance Modes

### URL-Only (Default)
Only parse listings from URLs you provide manually. Safest for ToS compliance.

### Broad Search
Allow connectors to search automatically (Craigslist RSS, etc). Toggle in Settings.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/listings` | GET | List/filter listings |
| `/api/listings` | PATCH | Update status/notes |
| `/api/listings/add` | POST | Add from URL or manual |
| `/api/scan` | POST | Run connector scan |
| `/api/scan` | GET | Get scan history |

## Budget

- Min: $2,700/month
- Max: $3,400/month (all-in)

## Target Neighborhoods

**Primary**: Waikiki, Ala Moana, Diamond Head
**Secondary**: Downtown, Across Ala Wai

---

Built with ❤️ for apartment hunting in paradise
