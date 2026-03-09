/**
 * Tests for Model Router integration with Cockpit quota hints
 * 
 * These tests verify the behavioral rules:
 * 1. Stale snapshot is ignored (router proceeds normally)
 * 2. Low-seconds snapshot causes Gemini preference (NOT exhausted)
 * 3. Probe success overrides all hints
 * 4. API error (probe failure) marks exhausted authoritatively
 */

import { jest, describe, test, expect, beforeEach, afterEach } from '@jest/globals';

// Mock the LLM client
const mockLlmComplete = jest.fn();
const mockIsProviderAvailable = jest.fn();

jest.unstable_mockModule('../lib/antigravity-llm-client.js', () => ({
    complete: mockLlmComplete,
    isProviderAvailable: mockIsProviderAvailable,
    MODELS_MAP: {
        claude: 'claude-sonnet-4-20250514',
        geminiFlash: 'gemini-2.0-flash',
        geminiPro: 'gemini-1.5-pro',
    },
}));

// Mock the quota-sources module
const mockReadQuotaSnapshot = jest.fn();
const mockShouldPreferClaude = jest.fn();
const mockQuotaConfig = {
    enabled: true,
    minClaudeSeconds: 60,
    minClaudePct: 5,
};

jest.unstable_mockModule('../lib/quota-sources/antigravity-cockpit.js', () => ({
    readQuotaSnapshot: mockReadQuotaSnapshot,
    shouldPreferClaude: mockShouldPreferClaude,
    QuotaConfig: mockQuotaConfig,
}));

// Dynamic import after mocking
const { ModelRouter } = await import('../lib/model-router.js');

describe('ModelRouter with Cockpit integration', () => {
    let router;

    beforeEach(() => {
        // Reset all mocks
        jest.clearAllMocks();

        // Default env setup
        process.env.ANTHROPIC_API_KEY = 'test-anthropic-key';
        process.env.GOOGLE_API_KEY = 'test-google-key';
        process.env.AG_COCKPIT_ENABLE = '1';
        delete process.env.FORCE_FALLBACK;

        // Default mock implementations
        mockIsProviderAvailable.mockImplementation((provider) => {
            if (provider === 'claude') return true;
            if (provider === 'gemini' || provider === 'gemini-flash' || provider === 'gemini-pro') return true;
            return false;
        });
        mockLlmComplete.mockResolvedValue('test response');
        mockReadQuotaSnapshot.mockResolvedValue(null);
        mockShouldPreferClaude.mockReturnValue({ preferClaude: true, reason: 'available' });
    });

    afterEach(() => {
        if (router) {
            router.cleanup();
        }
    });

    describe('stale snapshot handling', () => {
        test('stale snapshot is ignored, router proceeds normally with Claude', async () => {
            router = new ModelRouter();

            const staleSnapshot = {
                provider: 'antigravity-cockpit',
                ts: Date.now() - 300000,
                claudeRemainingSeconds: 10,
                stale: true,
            };

            mockReadQuotaSnapshot.mockResolvedValue(staleSnapshot);
            mockShouldPreferClaude.mockReturnValue({
                preferClaude: true,
                reason: 'snapshot is stale, ignored',
            });

            mockLlmComplete.mockResolvedValueOnce('test response');

            const result = await router.complete('system', 'user');

            expect(result).toBe('test response');
            expect(router.getCurrentModel()).toBe('claude');
            // claudeExhausted should be false - stale hint doesn't mark exhausted
            expect(router.claudeExhausted).toBe(false);
        });
    });

    describe('low quota causes Gemini preference (NOT exhausted)', () => {
        test('low seconds triggers Gemini switch but does NOT mark exhausted', async () => {
            router = new ModelRouter();

            const lowQuotaSnapshot = {
                provider: 'antigravity-cockpit',
                ts: Date.now(),
                claudeRemainingSeconds: 30,
                stale: false,
            };

            mockReadQuotaSnapshot.mockResolvedValue(lowQuotaSnapshot);
            mockShouldPreferClaude.mockReturnValue({
                preferClaude: false,
                reason: 'quota resets in 30s < 60s threshold',
            });

            mockLlmComplete.mockResolvedValueOnce('gemini response');

            const result = await router.complete('system', 'user');

            expect(result).toBe('gemini response');
            expect(router.getCurrentModel()).toBe('gemini-flash');
            // Key: claudeExhausted should be FALSE - hint doesn't mark exhausted
            expect(router.claudeExhausted).toBe(false);
        });
    });

    describe('probe success overrides all hints', () => {
        test('successful Claude call clears exhausted state', async () => {
            router = new ModelRouter();
            router.claudeExhausted = true;
            router.currentModel = 'claude'; // Force back to Claude for test

            mockLlmComplete.mockResolvedValueOnce('claude response');

            await router.complete('system', 'user');

            expect(router.claudeExhausted).toBe(false);
        });
    });

    describe('API error (probe failure) is authoritative', () => {
        test('Claude 429 error triggers fallback AND marks exhausted', async () => {
            router = new ModelRouter();

            // Quota hint says available
            mockShouldPreferClaude.mockReturnValue({
                preferClaude: true,
                reason: 'quota appears available',
            });

            // But API returns quota error
            const quotaError = new Error('rate_limit exceeded - 429');
            mockLlmComplete
                .mockRejectedValueOnce(quotaError)
                .mockResolvedValueOnce('gemini response');

            const result = await router.complete('system', 'user');

            expect(result).toBe('gemini response');
            // Key: claudeExhausted should be TRUE - API error is authoritative
            expect(router.claudeExhausted).toBe(true);
            expect(router.getCurrentModel()).toBe('gemini-flash');
        });
    });

    describe('cockpit disabled', () => {
        test('router works normally when cockpit disabled', async () => {
            mockQuotaConfig.enabled = false;
            router = new ModelRouter();

            mockLlmComplete.mockResolvedValueOnce('test response');

            const result = await router.complete('system', 'user');

            expect(result).toBe('test response');
            expect(mockReadQuotaSnapshot).not.toHaveBeenCalled();

            // Restore
            mockQuotaConfig.enabled = true;
        });
    });

    describe('no fixed reset time', () => {
        test('router does not have claudeResetTime property set to fixed value', () => {
            router = new ModelRouter();

            // Verify no fixed reset time in constructor
            expect(router.claudeResetTime).toBeUndefined();
        });
    });
});
