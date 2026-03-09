/**
 * Model Router - Automatic failover between Claude and Gemini
 * 
 * Features:
 * - Primary: Claude (claude-sonnet-4-20250514)
 * - Fallback: Gemini Flash, then Gemini Pro
 * - Automatic quota detection via API error handling
 * - Optional quota hints from Antigravity Cockpit
 * - Probe-based recovery (every 2 minutes)
 * - Cockpit resetTime integration for smarter probe timing
 * 
 * Provider Priority:
 * - Default: Uses external APIs (ANTHROPIC_API_KEY / GOOGLE_API_KEY)
 * - Future: Antigravity-native when ANTIGRAVITY_MODEL_ENDPOINT available
 * 
 * Environment:
 *   ANTHROPIC_API_KEY - Claude API key (optional if native available)
 *   GOOGLE_API_KEY - Gemini API key (optional if native available)
 *   FORCE_FALLBACK - Set to "1" to simulate Claude quota exhaustion
 *   AG_COCKPIT_ENABLE - Set to "1" to enable Cockpit quota hints
 *   AG_COCKPIT_STALE_MS - Snapshot staleness threshold (default: 180000 = 3 min)
 *   AG_CLAUDE_MIN_SECONDS - Min seconds remaining to prefer Claude (default: 60)
 */

import { complete as llmComplete, isProviderAvailable, MODELS_MAP } from './antigravity-llm-client.js';
import { readQuotaSnapshot, shouldPreferClaude, QuotaConfig } from './quota-sources/antigravity-cockpit.js';

// Default probe interval (2 minutes)
const DEFAULT_PROBE_INTERVAL_MS = 2 * 60 * 1000;

// Minimum probe interval (30 seconds) when Cockpit says reset is imminent
const MIN_PROBE_INTERVAL_MS = 30 * 1000;

// Rate limit error codes/messages
const RATE_LIMIT_INDICATORS = [
    'rate_limit',
    'quota',
    'exceeded',
    '429',
    'resource_exhausted',
    'too many requests',
];

class ModelRouter {
    constructor() {
        this.forceFailback = process.env.FORCE_FALLBACK === '1';
        this.cockpitEnabled = QuotaConfig.enabled;

        // Check provider availability
        this.claudeAvailable = isProviderAvailable('claude');
        this.geminiAvailable = isProviderAvailable('gemini');

        // State
        this.currentModel = 'claude';
        this.claudeExhausted = false;  // Only true when API confirms quota error
        this.quotaCheckTimer = null;
        this.lastQuotaSnapshot = null;
        this.probeInFlight = false;  // Guard against overlapping probes

        // Validate we have at least one provider
        if (!this.claudeAvailable && !this.geminiAvailable) {
            throw new Error(
                'No LLM provider available. Set ANTHROPIC_API_KEY or GOOGLE_API_KEY, ' +
                'or run in Antigravity with native model access.'
            );
        }

        // If no Claude, start with Gemini
        if (!this.claudeAvailable) {
            this.currentModel = 'gemini-flash';
            console.log('[Router] Claude not available, using Gemini');
        }

        // If forced fallback, use Gemini immediately
        if (this.forceFailback && this.geminiAvailable) {
            this.claudeExhausted = true;
            this.currentModel = 'gemini-flash';
            console.log('[Router] FORCE_FALLBACK enabled, simulating Claude quota exhaustion');
        }

        if (this.cockpitEnabled) {
            console.log('[Router] Antigravity Cockpit quota hints ENABLED');
        }
    }

    /**
     * Get the current model being used
     */
    getCurrentModel() {
        return this.currentModel;
    }

    /**
     * Get the actual model identifier for logging
     */
    getModelIdentifier() {
        switch (this.currentModel) {
            case 'claude': return MODELS_MAP.claude;
            case 'gemini-flash': return MODELS_MAP.geminiFlash;
            case 'gemini-pro': return MODELS_MAP.geminiPro;
            default: return this.currentModel;
        }
    }

    /**
     * Check if an error indicates quota/rate limit exhaustion
     */
    isQuotaError(error) {
        const errorStr = String(error).toLowerCase();
        return RATE_LIMIT_INDICATORS.some(indicator =>
            errorStr.includes(indicator.toLowerCase())
        );
    }

    /**
     * Switch to fallback model (API-confirmed quota exhaustion)
     * NOTE: Only call this when API error confirms quota is exhausted
     */
    switchToFallback(reason) {
        if (!this.geminiAvailable) {
            console.error('[Router] Cannot fallback: Gemini not available');
            return false;
        }

        const previousModel = this.currentModel;
        this.claudeExhausted = true;
        // NO fixed reset time - rely on probes and Cockpit hints

        if (this.currentModel === 'gemini-flash') {
            this.currentModel = 'gemini-pro';
        } else {
            this.currentModel = 'gemini-flash';
        }

        console.log(`[Router] SWITCH: ${previousModel} -> ${this.currentModel} (reason: ${reason})`);

        // Start probe-based recovery
        this.startQuotaCheckLoop();

        return true;
    }

    /**
     * Switch to Gemini based on Cockpit hint (NOT exhausted, just preference)
     * Does NOT mark Claude as exhausted
     */
    switchToGeminiPreference(reason) {
        if (!this.geminiAvailable) return false;

        const previousModel = this.currentModel;
        this.currentModel = 'gemini-flash';
        // claudeExhausted stays FALSE - this is just a preference hint

        console.log(`[Router] SWITCH: ${previousModel} -> ${this.currentModel} (reason: ${reason})`);

        // Start probing to detect when Claude is available again
        this.startQuotaCheckLoop();

        return true;
    }

    /**
     * Switch back to Claude (probe confirmed availability)
     */
    switchToClaude() {
        if (!this.claudeAvailable) return false;

        const previousModel = this.currentModel;
        this.claudeExhausted = false;
        this.currentModel = 'claude';

        console.log(`[Router] SWITCH: ${previousModel} -> claude (reason: probe confirmed available)`);

        // Stop quota check loop
        this.stopQuotaCheckLoop();

        return true;
    }

    /**
     * Calculate next probe interval
     * Uses Cockpit resetTime if available and fresh
     */
    getProbeIntervalMs() {
        if (this.lastQuotaSnapshot && !this.lastQuotaSnapshot.stale) {
            const resetSeconds = this.lastQuotaSnapshot.claudeRemainingSeconds;
            if (resetSeconds != null && resetSeconds > 0 && resetSeconds < 300) {
                // Reset is within 5 minutes - probe more frequently
                const intervalMs = Math.max(MIN_PROBE_INTERVAL_MS, (resetSeconds - 10) * 1000);
                console.log(`[Router] Cockpit suggests reset in ${resetSeconds}s, next probe in ${intervalMs / 1000}s`);
                return intervalMs;
            }
        }
        return DEFAULT_PROBE_INTERVAL_MS;
    }

    /**
     * Start background quota check loop (non-blocking, dynamic setTimeout)
     */
    startQuotaCheckLoop() {
        if (this.quotaCheckTimer) return;

        console.log('[Router] Starting quota recovery probe loop');
        this.scheduleNextProbe();
    }

    /**
     * Schedule the next probe with dynamic interval
     */
    scheduleNextProbe() {
        if (this.quotaCheckTimer) return; // Already scheduled

        const intervalMs = this.getProbeIntervalMs();
        console.log(`[Router] Next probe in ${intervalMs / 1000}s`);

        this.quotaCheckTimer = setTimeout(async () => {
            this.quotaCheckTimer = null; // Clear before probe
            await this.runProbeAndReschedule();
        }, intervalMs);
    }

    /**
     * Run probe cycle: refresh snapshot, probe, reschedule
     */
    async runProbeAndReschedule() {
        if (this.probeInFlight) return; // Guard overlapping probes
        this.probeInFlight = true;

        try {
            // Refresh cockpit snapshot if enabled
            if (this.cockpitEnabled) {
                await this.checkQuotaSnapshot();
            }

            // Probe Claude
            const success = await this.probeClaudeAvailability();

            // If probe succeeded, loop stops (switchToClaude calls stopQuotaCheckLoop)
            // If Claude is not active and probe failed, schedule next probe
            if (!success && this.currentModel !== 'claude') {
                this.scheduleNextProbe();
            }
        } finally {
            this.probeInFlight = false;
        }
    }

    /**
     * Stop quota check loop
     */
    stopQuotaCheckLoop() {
        if (this.quotaCheckTimer) {
            clearTimeout(this.quotaCheckTimer);
            this.quotaCheckTimer = null;
            console.log('[Router] Stopped quota recovery probe loop');
        }
    }

    /**
     * Probe Claude availability with minimal request
     */
    async probeClaudeAvailability() {
        if (!this.claudeAvailable) return false;

        console.log('[Router] Probing Claude availability...');

        try {
            // Make a minimal API call with auto provider
            await llmComplete({
                provider: 'auto',
                model: MODELS_MAP.claude,
                system: 'Respond with OK',
                user: 'ping',
                maxTokens: 10,
            });

            console.log('[Router] Claude probe succeeded - switching back');
            this.switchToClaude();
            return true;

        } catch (err) {
            if (this.isQuotaError(err)) {
                console.log('[Router] Claude still rate limited');
            } else {
                console.log('[Router] Claude probe failed:', err.message);
            }
            return false;
        }
    }

    /**
     * Check Cockpit quota snapshot for hints
     * NOTE: This is a HINT only - API errors are authoritative
     * @returns {Promise<{preferClaude: boolean, reason: string, snapshot: object|null}>}
     */
    async checkQuotaSnapshot() {
        if (!this.cockpitEnabled) {
            return { preferClaude: true, reason: 'cockpit disabled', snapshot: null };
        }

        try {
            const snapshot = await readQuotaSnapshot();
            this.lastQuotaSnapshot = snapshot;
            const decision = shouldPreferClaude(snapshot);
            console.log(`[Router] Cockpit hint: preferClaude=${decision.preferClaude} (${decision.reason})`);
            return { ...decision, snapshot };
        } catch (err) {
            console.log(`[Router] Cockpit check failed: ${err.message}`);
            return { preferClaude: true, reason: 'cockpit error', snapshot: null };
        }
    }

    /**
     * Main completion method with automatic failover
     * 
     * Behavioral rules:
     * 1. API errors (429/quota) are AUTHORITATIVE - trigger fallback and mark exhausted
     * 2. Cockpit snapshot is a HINT - switch preference but DON'T mark exhausted
     * 3. Probe success OVERRIDES all hints - switch back to Claude
     * 4. Probe failure OVERRIDES hints - stay on current model
     */
    async complete(systemPrompt, userPrompt) {
        const maxRetries = 3;
        let lastError = null;

        // Pre-check: consult Cockpit snapshot if enabled (hint only)
        if (this.cockpitEnabled && this.currentModel === 'claude' && !this.claudeExhausted) {
            const quotaHint = await this.checkQuotaSnapshot();

            if (!quotaHint.preferClaude && this.geminiAvailable) {
                console.log(`[Router] Cockpit suggests avoiding Claude: ${quotaHint.reason}`);
                // Switch preference but DON'T mark exhausted - this is just a hint
                this.switchToGeminiPreference('quota hint (low remaining)');
            }
        }

        for (let attempt = 0; attempt < maxRetries; attempt++) {
            try {
                const modelId = this.getModelIdentifier();
                console.log(`[Router] Using model: ${this.currentModel} (${modelId})`);

                let result;

                if (this.currentModel === 'claude') {
                    if (this.forceFailback) {
                        throw new Error('Simulated quota exhaustion (FORCE_FALLBACK=1)');
                    }
                    result = await llmComplete({
                        provider: 'auto',
                        model: MODELS_MAP.claude,
                        system: systemPrompt,
                        user: userPrompt,
                    });

                    // Success! Claude is working - this OVERRIDES any hint
                    if (this.claudeExhausted) {
                        console.log('[Router] Claude call succeeded - clearing exhausted state');
                        this.claudeExhausted = false;
                        this.stopQuotaCheckLoop();
                    }

                } else if (this.currentModel === 'gemini-flash') {
                    result = await llmComplete({
                        provider: 'auto',
                        model: MODELS_MAP.geminiFlash,
                        system: systemPrompt,
                        user: userPrompt,
                    });

                } else if (this.currentModel === 'gemini-pro') {
                    result = await llmComplete({
                        provider: 'auto',
                        model: MODELS_MAP.geminiPro,
                        system: systemPrompt,
                        user: userPrompt,
                    });
                }

                return result;

            } catch (err) {
                lastError = err;
                console.error(`[Router] Model call failed: ${err.message}`);

                // Check if quota error - this is AUTHORITATIVE
                if (this.isQuotaError(err)) {
                    console.log('[Router] API confirmed quota exhausted (authoritative)');
                    const switched = this.switchToFallback('api quota error');
                    if (switched) {
                        continue; // Retry with new model
                    }
                }

                // If on Gemini Flash and it fails, try Gemini Pro
                if (this.currentModel === 'gemini-flash' && this.geminiAvailable) {
                    this.currentModel = 'gemini-pro';
                    console.log('[Router] SWITCH: gemini-flash -> gemini-pro (reason: error fallback)');
                    continue;
                }

                // No more fallbacks available
                break;
            }
        }

        throw lastError || new Error('All model attempts failed');
    }

    /**
     * Clean up resources
     */
    cleanup() {
        this.stopQuotaCheckLoop();
    }
}

export { ModelRouter };
