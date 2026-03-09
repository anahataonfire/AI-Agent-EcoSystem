/**
 * Antigravity Cockpit Quota Source
 * 
 * Reads quota snapshots from the Antigravity Cockpit VS Code extension's cache.
 * 
 * Data sources (in order of priority):
 * 1. Local cache files at ~/.antigravity_cockpit/cache/quota/{local|authorized}/{hashed_email}.json
 * 2. (Future) HTTP endpoint if Cockpit exposes one
 * 
 * This module is optional - if data is unavailable, returns null and router
 * falls back to API error detection.
 * 
 * Environment:
 *   AG_COCKPIT_EMAIL - Email to look up in cache (hashed with SHA256)
 *   AG_COCKPIT_SOURCE - 'local' or 'authorized' (default: 'local')
 *   AG_COCKPIT_CACHE_PATH - Override cache directory path
 */

import { promises as fsPromises, constants as fsConstants } from 'fs';
import path from 'path';
import os from 'os';
import { createHash } from 'crypto';

// Default cache location (matches Cockpit's quota_cache.ts)
const DEFAULT_CACHE_ROOT = path.join(os.homedir(), '.antigravity_cockpit', 'cache', 'quota');

// Claude model identifiers in Cockpit
const CLAUDE_MODEL_PATTERNS = [
    'claude-3',
    'claude-sonnet',
    'claude-opus',
    'claude-haiku',
    'sonnet',
    'opus',
];

/**
 * @typedef {Object} QuotaSnapshot
 * @property {'antigravity-cockpit'} provider
 * @property {number} ts - Epoch milliseconds when snapshot was taken
 * @property {number} [claudeRemainingSeconds] - Seconds until quota resets
 * @property {number} [claudeRemainingPct] - Remaining quota percentage (0-100)
 * @property {any} [raw] - Raw cache record for debugging
 * @property {boolean} stale - Whether this snapshot is considered stale
 */

/**
 * @typedef {Object} QuotaCacheModel
 * @property {string} id
 * @property {string} [displayName]
 * @property {number} [remainingPercentage]
 * @property {number} [remainingFraction]
 * @property {string} [resetTime]
 */

/**
 * @typedef {Object} QuotaCacheRecord
 * @property {1} version
 * @property {'authorized'|'local'} source
 * @property {string} [email]
 * @property {number} updatedAt - Epoch ms
 * @property {string} [subscriptionTier]
 * @property {boolean} [isForbidden]
 * @property {QuotaCacheModel[]} models
 */

/**
 * Hash email to match Cockpit's cache filename scheme
 * @param {string} email 
 * @returns {string}
 */
export function hashEmail(email) {
    return createHash('sha256').update(email.trim().toLowerCase()).digest('hex');
}

/**
 * Find Claude model in cache record
 * @param {QuotaCacheRecord} record 
 * @returns {QuotaCacheModel|null}
 */
export function findClaudeModel(record) {
    if (!record.models || !Array.isArray(record.models)) {
        return null;
    }

    // Find any Claude-related model (prefer Sonnet/Opus)
    for (const model of record.models) {
        const id = (model.id || '').toLowerCase();
        const name = (model.displayName || '').toLowerCase();

        if (CLAUDE_MODEL_PATTERNS.some(p => id.includes(p) || name.includes(p))) {
            return model;
        }
    }

    return null;
}

/**
 * Parse reset time string to seconds remaining
 * @param {string} resetTime - Time string like "15:16" or ISO date
 * @returns {number|null}
 */
export function parseResetTimeToSeconds(resetTime) {
    if (!resetTime) return null;

    try {
        // Try ISO date format first
        const resetDate = new Date(resetTime);
        if (!isNaN(resetDate.getTime())) {
            const now = Date.now();
            const remaining = Math.max(0, Math.floor((resetDate.getTime() - now) / 1000));
            return remaining;
        }

        // Try HH:MM format (assume same day or next day)
        const match = resetTime.match(/^(\d{1,2}):(\d{2})$/);
        if (match) {
            const now = new Date();
            const resetHour = parseInt(match[1], 10);
            const resetMin = parseInt(match[2], 10);

            const reset = new Date(now);
            reset.setHours(resetHour, resetMin, 0, 0);

            // If reset time is in the past, assume next day
            if (reset <= now) {
                reset.setDate(reset.getDate() + 1);
            }

            return Math.max(0, Math.floor((reset.getTime() - now.getTime()) / 1000));
        }

        return null;
    } catch {
        return null;
    }
}

/**
 * List all cache files and find the most recent one
 * @param {string} cacheDir 
 * @returns {Promise<string|null>}
 */
async function findLatestCacheFile(cacheDir) {
    try {
        const files = await fsPromises.readdir(cacheDir);
        const jsonFiles = files.filter(f => f.endsWith('.json'));

        if (jsonFiles.length === 0) return null;

        // Find most recently modified
        let latestFile = null;
        let latestMtime = 0;

        for (const file of jsonFiles) {
            const filePath = path.join(cacheDir, file);
            const stat = await fsPromises.stat(filePath);
            if (stat.mtimeMs > latestMtime) {
                latestMtime = stat.mtimeMs;
                latestFile = filePath;
            }
        }

        return latestFile;
    } catch {
        return null;
    }
}

/**
 * Read quota snapshot from Antigravity Cockpit cache
 * @param {Object} [options]
 * @param {string} [options.email] - Email to look up (uses AG_COCKPIT_EMAIL env var if not provided)
 * @param {'local'|'authorized'} [options.source] - Cache source (uses AG_COCKPIT_SOURCE or 'local')
 * @param {string} [options.cachePath] - Override cache directory
 * @param {number} [options.staleMs] - Milliseconds after which snapshot is considered stale
 * @returns {Promise<QuotaSnapshot|null>}
 */
export async function readQuotaSnapshot(options = {}) {
    const email = options.email || process.env.AG_COCKPIT_EMAIL;
    const source = options.source || process.env.AG_COCKPIT_SOURCE || 'local';
    const cachePath = options.cachePath || process.env.AG_COCKPIT_CACHE_PATH || DEFAULT_CACHE_ROOT;
    const staleMs = options.staleMs || parseInt(process.env.AG_COCKPIT_STALE_MS || '180000', 10);

    const sourceDir = path.join(cachePath, source);

    let cacheFilePath = null;

    // If email provided, look for specific cache file
    if (email) {
        const hashedEmail = hashEmail(email);
        cacheFilePath = path.join(sourceDir, `${hashedEmail}.json`);

        // Check if file exists
        try {
            await fsPromises.access(cacheFilePath, fsConstants.R_OK);
        } catch {
            console.log('[QuotaSource] Cache file not found for email, searching for latest...');
            cacheFilePath = await findLatestCacheFile(sourceDir);
        }
    } else {
        // No email provided, find latest cache file
        cacheFilePath = await findLatestCacheFile(sourceDir);
    }

    if (!cacheFilePath) {
        console.log('[QuotaSource] No Cockpit cache files found');
        return null;
    }

    // Read and parse cache file
    let record;
    try {
        const content = await fsPromises.readFile(cacheFilePath, 'utf-8');
        record = JSON.parse(content);
    } catch (err) {
        console.log(`[QuotaSource] Failed to read cache: ${err.message}`);
        return null;
    }

    // Validate record
    if (!record || record.version !== 1) {
        console.log('[QuotaSource] Invalid cache format');
        return null;
    }

    // Check staleness
    const now = Date.now();
    const age = now - (record.updatedAt || 0);
    const stale = age > staleMs;

    // Find Claude model
    const claudeModel = findClaudeModel(record);

    if (!claudeModel) {
        console.log('[QuotaSource] No Claude model found in cache');
        return {
            provider: 'antigravity-cockpit',
            ts: record.updatedAt || now,
            stale,
            raw: record,
        };
    }

    // Extract quota info
    const claudeRemainingPct = claudeModel.remainingPercentage ??
        (claudeModel.remainingFraction != null ? claudeModel.remainingFraction * 100 : undefined);

    const claudeRemainingSeconds = parseResetTimeToSeconds(claudeModel.resetTime);

    const snapshot = {
        provider: 'antigravity-cockpit',
        ts: record.updatedAt || now,
        claudeRemainingSeconds,
        claudeRemainingPct,
        stale,
        raw: record,
    };

    console.log(`[QuotaSource] Cockpit snapshot: pct=${claudeRemainingPct?.toFixed(1)}%, seconds=${claudeRemainingSeconds}, stale=${stale}`);

    return snapshot;
}

/**
 * Configuration for quota hinting
 */
export const QuotaConfig = {
    /** Minimum seconds remaining to prefer Claude */
    minClaudeSeconds: parseInt(process.env.AG_CLAUDE_MIN_SECONDS || '60', 10),

    /** Minimum percentage remaining to prefer Claude */
    minClaudePct: parseInt(process.env.AG_CLAUDE_MIN_PCT || '5', 10),

    /** Whether Cockpit integration is enabled */
    enabled: process.env.AG_COCKPIT_ENABLE === '1',
};

/**
 * Check if Claude should be preferred based on quota snapshot
 * @param {QuotaSnapshot|null} snapshot 
 * @returns {{preferClaude: boolean, reason: string}}
 */
export function shouldPreferClaude(snapshot) {
    if (!snapshot) {
        return { preferClaude: true, reason: 'no snapshot available' };
    }

    if (snapshot.stale) {
        return { preferClaude: true, reason: 'snapshot is stale' };
    }

    // Check remaining seconds
    if (snapshot.claudeRemainingSeconds != null &&
        snapshot.claudeRemainingSeconds < QuotaConfig.minClaudeSeconds) {
        return {
            preferClaude: false,
            reason: `quota resets in ${snapshot.claudeRemainingSeconds}s < ${QuotaConfig.minClaudeSeconds}s threshold`
        };
    }

    // Check remaining percentage
    if (snapshot.claudeRemainingPct != null &&
        snapshot.claudeRemainingPct < QuotaConfig.minClaudePct) {
        return {
            preferClaude: false,
            reason: `quota at ${snapshot.claudeRemainingPct.toFixed(1)}% < ${QuotaConfig.minClaudePct}% threshold`
        };
    }

    return { preferClaude: true, reason: 'quota appears available' };
}
