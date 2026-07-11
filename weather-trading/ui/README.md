# Weather Trading dashboard

Next.js operator UI for the local weather-trading backend.

```bash
npm install
npm run dev
```

The client defaults to `http://localhost:8000`; override with `NEXT_PUBLIC_API_URL`.

The dashboard distinguishes reserved orders from confirmed positions, displays gross and conditional fee-net winning payoff separately, exposes runtime risk/order settings, and polls authenticated lifecycle reconciliation while live mode is enabled.

Validate types with:

```bash
PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin npm exec tsc -- --noEmit --incremental false
```
