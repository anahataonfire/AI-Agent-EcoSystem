/**
 * Tests for Antigravity Cockpit Quota Source
 */

import { jest, describe, test, expect } from '@jest/globals';

import {
    hashEmail,
    findClaudeModel,
    parseResetTimeToSeconds,
    shouldPreferClaude,
} from '../lib/quota-sources/antigravity-cockpit.js';

describe('hashEmail', () => {
    test('normalizes and hashes email', () => {
        const hash1 = hashEmail('Test@Example.com');
        const hash2 = hashEmail('test@example.com');
        const hash3 = hashEmail('  TEST@EXAMPLE.COM  ');

        expect(hash1).toBe(hash2);
        expect(hash2).toBe(hash3);
        expect(hash1).toHaveLength(64); // SHA256 hex length
    });
});

describe('findClaudeModel', () => {
    test('finds claude-sonnet model', () => {
        const record = {
            models: [
                { id: 'gpt-4', displayName: 'GPT-4' },
                { id: 'claude-3-sonnet', displayName: 'Sonnet', remainingPercentage: 50 },
            ]
        };

        const model = findClaudeModel(record);
        expect(model).not.toBeNull();
        expect(model.id).toBe('claude-3-sonnet');
    });

    test('finds model by displayName', () => {
        const record = {
            models: [
                { id: 'model-123', displayName: 'Claude Opus', remainingPercentage: 75 },
            ]
        };

        const model = findClaudeModel(record);
        expect(model).not.toBeNull();
        expect(model.displayName).toBe('Claude Opus');
    });

    test('returns null when no Claude model', () => {
        const record = {
            models: [
                { id: 'gpt-4', displayName: 'GPT-4' },
            ]
        };

        expect(findClaudeModel(record)).toBeNull();
    });

    test('handles empty models array', () => {
        expect(findClaudeModel({ models: [] })).toBeNull();
        expect(findClaudeModel({})).toBeNull();
    });
});

describe('parseResetTimeToSeconds', () => {
    test('parses ISO date string', () => {
        const futureDate = new Date(Date.now() + 3600000); // 1 hour from now
        const seconds = parseResetTimeToSeconds(futureDate.toISOString());

        expect(seconds).toBeGreaterThan(3500);
        expect(seconds).toBeLessThanOrEqual(3600);
    });

    test('returns 0 for past dates', () => {
        const pastDate = new Date(Date.now() - 3600000);
        const seconds = parseResetTimeToSeconds(pastDate.toISOString());

        expect(seconds).toBe(0);
    });

    test('returns null for invalid input', () => {
        expect(parseResetTimeToSeconds(null)).toBeNull();
        expect(parseResetTimeToSeconds('')).toBeNull();
        expect(parseResetTimeToSeconds('invalid')).toBeNull();
    });
});

describe('shouldPreferClaude', () => {
    test('returns preferClaude=true when snapshot is null', () => {
        const result = shouldPreferClaude(null);
        expect(result.preferClaude).toBe(true);
        expect(result.reason).toContain('no snapshot');
    });

    test('returns preferClaude=true when snapshot is stale', () => {
        const snapshot = {
            provider: 'antigravity-cockpit',
            ts: Date.now() - 300000, // 5 minutes ago
            claudeRemainingSeconds: 30, // Would normally trigger avoid
            claudeRemainingPct: 2,
            stale: true, // But marked stale
        };

        const result = shouldPreferClaude(snapshot);
        expect(result.preferClaude).toBe(true);
        expect(result.reason).toContain('stale');
    });

    test('returns preferClaude=false when seconds below threshold', () => {
        const snapshot = {
            provider: 'antigravity-cockpit',
            ts: Date.now(),
            claudeRemainingSeconds: 30, // Below default 60s threshold
            claudeRemainingPct: 50,
            stale: false,
        };

        const result = shouldPreferClaude(snapshot);
        expect(result.preferClaude).toBe(false);
        expect(result.reason).toContain('30s');
    });

    test('returns preferClaude=false when percentage below threshold', () => {
        const snapshot = {
            provider: 'antigravity-cockpit',
            ts: Date.now(),
            claudeRemainingSeconds: 3600,
            claudeRemainingPct: 2, // Below default 5% threshold
            stale: false,
        };

        const result = shouldPreferClaude(snapshot);
        expect(result.preferClaude).toBe(false);
        expect(result.reason).toContain('%');
    });

    test('returns preferClaude=true when quota appears available', () => {
        const snapshot = {
            provider: 'antigravity-cockpit',
            ts: Date.now(),
            claudeRemainingSeconds: 3600,
            claudeRemainingPct: 80,
            stale: false,
        };

        const result = shouldPreferClaude(snapshot);
        expect(result.preferClaude).toBe(true);
        expect(result.reason).toContain('available');
    });
});
