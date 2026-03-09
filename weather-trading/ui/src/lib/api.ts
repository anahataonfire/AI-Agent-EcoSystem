import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const api = axios.create({
    baseURL: API_URL,
    timeout: 360000,  // 6 minutes - scan can take 3+ min with VPN + suffix retries
});

export interface Opportunity {
    id: string;
    city: string;
    targetDate: string;
    bucket: string;
    bucketLow: number;
    bucketHigh: number;
    forecastTemp: number;
    yesPrice: number;
    noPrice: number;
    edge: number;
    tier: 'HIGH' | 'MEDIUM' | 'LOW';
    hoursRemaining: number;
    liquidity: number;
    recommendedSide: 'YES' | 'NO';
    positionSize: number;
    marketUrl?: string;
}

export interface EdgeHarvestOpportunity {
    id: string;
    city: string;
    targetDate: string;
    bucket: string;
    bucketLow: number | null;
    bucketHigh: number | null;
    forecastTemp: number;
    bandsAway: number;
    degreesAway: number;
    thresholdType: 'CONSERVATIVE' | 'AGGRESSIVE';
    yesPrice: number;
    noPrice: number;
    potentialReturnPct: number;
    riskTier: 'LOW' | 'MEDIUM' | 'HIGH';
    riskScore: number;
    riskFactors: string[];
    modelSpread: number;
    ecmwfTemp: number | null;
    gfsTemp: number | null;
    nwsTemp: number | null;
    frontWarning: boolean;
    frontWarningReason: string | null;
    clobTokenIds: [string, string];
    marketUrl: string;
    liquidity: number;
    hoursRemaining: number;
}

export interface EdgeHarvestStats {
    total: number;
    conservative: number;
    aggressive: number;
    withWarnings: number;
    highRisk: number;
    mediumRisk: number;
    lowRisk: number;
}

export interface Order {
    id: string;
    tokenId: string;
    side: string;
    price: number;
    originalSize: number;
    sizeMatched: number;
    sizeRemaining: number;
    status: string;
    createdAt: string;
    source: 'LIVE' | 'LOCAL';
}

export interface Position {
    id: string;
    city: string;
    targetDate: string;
    bucket: string;
    side: 'YES' | 'NO';
    entryPrice: number;
    currentPrice: number;
    size: number;
    shares: number;
    unrealizedPnl: number;
    status: 'OPEN' | 'WON' | 'LOST';
    hoursRemaining: number;
    createdAt: string;
}

export interface Stats {
    bankroll: number;
    deployed: number;
    available: number;
    totalPnl: number;
    winCount: number;
    lossCount: number;
    winRate: number | null;
    openPositions: number;
    totalTrades: number;
}

export interface Status {
    bankroll: number;
    deployed: number;
    available: number;
    isLive: boolean;
    lastScan: string | null;
    opportunitiesCount: number;
    positionsCount: number;
}

export const weatherApi = {
    getStatus: async (): Promise<Status> => {
        const res = await api.get('/api/status');
        return res.data;
    },

    scan: async (cities?: string[]): Promise<{ opportunities: Opportunity[]; scanTime: string }> => {
        const res = await api.post('/api/scan', cities ? { cities } : undefined);
        return res.data;
    },

    getOpportunities: async (): Promise<{ opportunities: Opportunity[]; lastScan: string | null }> => {
        const res = await api.get('/api/opportunities');
        return res.data;
    },

    executeTrade: async (opportunityId: string, side: string, size?: number): Promise<{ success: boolean; position?: Position; orderId?: string; error?: string }> => {
        const res = await api.post('/api/trade', {
            opportunity_id: opportunityId,
            side,
            size,
        });
        return res.data;
    },

    getPositions: async (): Promise<{ positions: Position[] }> => {
        const res = await api.get('/api/positions');
        return res.data;
    },

    closePosition: async (positionId: string, outcome: 'WON' | 'LOST'): Promise<{ success: boolean; position: Position }> => {
        const res = await api.post(`/api/positions/${positionId}/close?outcome=${outcome}`);
        return res.data;
    },

    getStats: async (): Promise<Stats> => {
        const res = await api.get('/api/stats');
        return res.data;
    },

    updateSettings: async (settings: { bankroll?: number; isLive?: boolean }): Promise<{ success: boolean; bankroll: number; isLive: boolean }> => {
        const res = await api.post('/api/settings', {
            bankroll: settings.bankroll,
            is_live: settings.isLive,
        });
        return res.data;
    },

    scanEdgeHarvest: async (cities?: string[]): Promise<{
        opportunities: EdgeHarvestOpportunity[];
        scanTime: string;
        stats: EdgeHarvestStats;
    }> => {
        const res = await api.post('/api/edge-harvest', cities ? { cities } : undefined);
        return res.data;
    },

    getEdgeHarvest: async (): Promise<{
        opportunities: EdgeHarvestOpportunity[];
        lastScan: string | null
    }> => {
        const res = await api.get('/api/edge-harvest');
        return res.data;
    },

    getOrders: async (): Promise<{ orders: Order[] }> => {
        const res = await api.get('/api/orders');
        return res.data;
    },

    cancelOrder: async (orderId: string): Promise<{ success: boolean }> => {
        const res = await api.post(`/api/orders/${orderId}/cancel`);
        return res.data;
    },
};

export default weatherApi;
