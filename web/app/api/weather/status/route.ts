import { NextRequest, NextResponse } from "next/server";
import { readFileSync, statSync, existsSync } from "fs";
import path from "path";

/**
 * Weather Auto-Trader Status API
 * 
 * Returns current status of the weather trading bot:
 * - Running state
 * - Recent log entries
 * - Trade history
 * - Position summary
 */

const PROJECT_ROOT = "/Users/adamc/Documents/001 AI Agents/AI Agent EcoSystem 2.0";

interface Trade {
    trade_id: string;
    order_id: string;
    token_id: string;
    market_slug: string;
    side: string;
    price: number;
    size: number;
    executed_at: string;
    paper_mode: boolean;
}

export async function GET(request: NextRequest) {
    try {
        const logPath = path.join(PROJECT_ROOT, "logs", "weather_auto_trader_live.log");
        const tradeLogPath = path.join(PROJECT_ROOT, "src", "weather_trading", "trade_log.json");

        // Check if bot is running
        let isRunning = false;
        let lastActivity = null;
        let recentLogs: string[] = [];

        if (existsSync(logPath)) {
            const stats = statSync(logPath);
            const mtime = stats.mtime;
            const ageMinutes = (Date.now() - mtime.getTime()) / (1000 * 60);

            // Consider running if log was updated in last 20 minutes
            isRunning = ageMinutes < 20;
            lastActivity = mtime.toISOString();

            // Read last 30 lines of log
            const logContent = readFileSync(logPath, "utf-8");
            const lines = logContent.split("\n").filter(Boolean);
            recentLogs = lines.slice(-30);
        }

        // Load trade history
        let trades: Trade[] = [];
        let totalPnL = 0;
        let liveTrades = 0;
        let paperTrades = 0;

        if (existsSync(tradeLogPath)) {
            const tradeData = readFileSync(tradeLogPath, "utf-8");
            trades = JSON.parse(tradeData);

            // Calculate stats
            for (const trade of trades) {
                if (trade.paper_mode) {
                    paperTrades++;
                } else {
                    liveTrades++;
                }
            }

            // Keep only last 20 trades for display
            trades = trades.slice(-20).reverse();
        }

        // Extract current scan info from logs - check ALL log lines for mode
        const allLogContent = existsSync(logPath) ? readFileSync(logPath, "utf-8") : "";
        const allLines = allLogContent.split("\n").filter(Boolean);

        let currentScan = {
            mode: "UNKNOWN",
            marketsFound: 0,
            tradeableMarkets: 0,
            lastScanTime: null as string | null,
            opportunities: 0,
        };

        // Check for mode in entire log (it appears at startup)
        if (allLogContent.includes("LIVE TRADING MODE") || allLogContent.includes("Mode: LIVE")) {
            currentScan.mode = "LIVE";
        } else if (allLogContent.includes("Mode: PAPER")) {
            currentScan.mode = "PAPER";
        }

        // Get recent metrics from last 50 lines
        for (const line of allLines.slice(-50).reverse()) {

            const marketsMatch = line.match(/Found (\d+) temperature markets/);
            if (marketsMatch) {
                currentScan.marketsFound = parseInt(marketsMatch[1]);
            }

            const tradeableMatch = line.match(/Tradeable markets.*: (\d+)/);
            if (tradeableMatch) {
                currentScan.tradeableMarkets = parseInt(tradeableMatch[1]);
            }

            const oppMatch = line.match(/Found (\d+) opportunities/);
            if (oppMatch) {
                currentScan.opportunities = parseInt(oppMatch[1]);
            }

            const timeMatch = line.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})/);
            if (timeMatch && !currentScan.lastScanTime) {
                currentScan.lastScanTime = timeMatch[1];
            }
        }

        return NextResponse.json({
            status: isRunning ? "running" : "stopped",
            lastActivity,
            scanInfo: currentScan,
            stats: {
                liveTrades,
                paperTrades,
                totalTrades: trades.length,
            },
            recentTrades: trades,
            recentLogs: recentLogs.slice(-15),
        });

    } catch (error: any) {
        return NextResponse.json(
            { error: error.message },
            { status: 500 }
        );
    }
}
