/**
 * Antigravity LLM Client
 * 
 * Unified interface for LLM calls supporting multiple providers:
 * - antigravity-claude: Claude via Antigravity runtime (no external key)
 * - antigravity-gemini: Gemini via Antigravity runtime (no external key)
 * - anthropic-api: Claude via Anthropic API (requires ANTHROPIC_API_KEY)
 * - google-api: Gemini via Google API (requires GOOGLE_API_KEY)
 * 
 * Default behavior:
 * - Attempts Antigravity-native providers first
 * - Falls back to external APIs if USE_EXTERNAL_APIS=1 or native unavailable
 * 
 * LIMITATION: Antigravity-native model calls from Node.js subprocess
 * Currently, Antigravity's model APIs are not directly accessible from
 * arbitrary Node.js subprocesses. The runtime provides model access to
 * the orchestrating agent (Claude/Gemini running in Antigravity), but
 * not to spawned child processes. Therefore, we default to external APIs.
 * 
 * When running inside Antigravity's native context (future integration),
 * the Antigravity providers can be enabled.
 */

// Model identifiers
const MODELS = {
    claude: 'claude-sonnet-4-20250514',
    geminiFlash: 'gemini-2.0-flash',
    geminiPro: 'gemini-1.5-pro',
};

/**
 * Check if Antigravity-native model calls are available
 * Currently returns false as Node subprocesses cannot access Antigravity APIs
 */
function isAntigravityNativeAvailable() {
    // Antigravity's model APIs are exposed to the orchestrating agent context,
    // not to spawned Node.js subprocesses. This would need a dedicated IPC
    // channel or HTTP bridge to enable.
    //
    // Future: Check for ANTIGRAVITY_MODEL_ENDPOINT or similar
    const endpoint = process.env.ANTIGRAVITY_MODEL_ENDPOINT;
    return !!endpoint;
}

/**
 * Check if external API mode is enabled or required
 */
function shouldUseExternalAPIs() {
    // Explicit opt-in
    if (process.env.USE_EXTERNAL_APIS === '1') return true;

    // Default to external if native not available
    if (!isAntigravityNativeAvailable()) return true;

    return false;
}

/**
 * Call Claude via Anthropic API
 */
async function callAnthropicAPI(model, system, user, maxTokens) {
    const apiKey = process.env.ANTHROPIC_API_KEY;
    if (!apiKey) {
        throw new Error('ANTHROPIC_API_KEY required for anthropic-api provider');
    }

    const response = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'x-api-key': apiKey,
            'anthropic-version': '2023-06-01',
        },
        body: JSON.stringify({
            model: model || MODELS.claude,
            max_tokens: maxTokens || 8192,
            system,
            messages: [{ role: 'user', content: user }],
        }),
    });

    if (!response.ok) {
        const error = await response.text();
        const err = new Error(`Anthropic API error: ${response.status} - ${error}`);
        err.status = response.status;
        err.body = error;
        throw err;
    }

    const data = await response.json();
    return data.content[0].text;
}

/**
 * Call Gemini via Google API
 */
async function callGoogleAPI(model, system, user, maxTokens) {
    const apiKey = process.env.GOOGLE_API_KEY;
    if (!apiKey) {
        throw new Error('GOOGLE_API_KEY required for google-api provider');
    }

    const modelName = model || MODELS.geminiFlash;
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${modelName}:generateContent?key=${apiKey}`;

    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            contents: [{
                parts: [{
                    text: `${system}\n\n---\n\n${user}`
                }]
            }],
            generationConfig: {
                maxOutputTokens: maxTokens || 8192,
                temperature: 0.7,
            },
        }),
    });

    if (!response.ok) {
        const error = await response.text();
        const err = new Error(`Google API error: ${response.status} - ${error}`);
        err.status = response.status;
        err.body = error;
        throw err;
    }

    const data = await response.json();

    if (!data.candidates || !data.candidates[0]?.content?.parts?.[0]?.text) {
        throw new Error('Gemini returned empty response');
    }

    return data.candidates[0].content.parts[0].text;
}

/**
 * Call via Antigravity-native endpoint (when available)
 */
async function callAntigravityNative(provider, model, system, user, maxTokens) {
    const endpoint = process.env.ANTIGRAVITY_MODEL_ENDPOINT;
    if (!endpoint) {
        throw new Error(
            'Antigravity-native model calls not available from Node subprocess. ' +
            'Set USE_EXTERNAL_APIS=1 and provide ANTHROPIC_API_KEY or GOOGLE_API_KEY.'
        );
    }

    // Future implementation when IPC/HTTP bridge is available
    const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            provider,
            model,
            system,
            user,
            maxTokens,
        }),
    });

    if (!response.ok) {
        const error = await response.text();
        throw new Error(`Antigravity native error: ${response.status} - ${error}`);
    }

    const data = await response.json();
    return data.content;
}

/**
 * Main completion function with provider routing
 * 
 * @param {Object} options
 * @param {string} options.provider - Provider name
 * @param {string} [options.model] - Model identifier
 * @param {string} options.system - System prompt
 * @param {string} options.user - User prompt
 * @param {number} [options.maxTokens] - Max tokens (default 8192)
 * @returns {Promise<string>} Completion text
 */
export async function complete({ provider, model, system, user, maxTokens = 8192 }) {
    // Normalize provider
    const normalizedProvider = provider?.toLowerCase() || 'auto';

    // Auto-detect provider
    if (normalizedProvider === 'auto') {
        if (isAntigravityNativeAvailable()) {
            return callAntigravityNative('antigravity-claude', model || MODELS.claude, system, user, maxTokens);
        } else if (process.env.ANTHROPIC_API_KEY) {
            return callAnthropicAPI(model || MODELS.claude, system, user, maxTokens);
        } else if (process.env.GOOGLE_API_KEY) {
            return callGoogleAPI(model || MODELS.geminiFlash, system, user, maxTokens);
        } else {
            throw new Error(
                'No LLM provider available. Either:\n' +
                '  - Run inside Antigravity with native model access, or\n' +
                '  - Set ANTHROPIC_API_KEY for Claude, or\n' +
                '  - Set GOOGLE_API_KEY for Gemini'
            );
        }
    }

    // Route to specific provider
    switch (normalizedProvider) {
        case 'antigravity-claude':
        case 'antigravity-gemini':
            return callAntigravityNative(normalizedProvider, model, system, user, maxTokens);

        case 'anthropic-api':
        case 'claude':
            return callAnthropicAPI(model || MODELS.claude, system, user, maxTokens);

        case 'google-api':
        case 'gemini':
        case 'gemini-flash':
            return callGoogleAPI(model || MODELS.geminiFlash, system, user, maxTokens);

        case 'gemini-pro':
            return callGoogleAPI(model || MODELS.geminiPro, system, user, maxTokens);

        default:
            throw new Error(`Unknown LLM provider: ${provider}`);
    }
}

/**
 * Get available providers based on environment
 */
export function getAvailableProviders() {
    const providers = [];

    if (isAntigravityNativeAvailable()) {
        providers.push('antigravity-claude', 'antigravity-gemini');
    }

    if (process.env.ANTHROPIC_API_KEY) {
        providers.push('anthropic-api');
    }

    if (process.env.GOOGLE_API_KEY) {
        providers.push('google-api');
    }

    return providers;
}

/**
 * Check if a specific provider is available
 */
export function isProviderAvailable(provider) {
    switch (provider?.toLowerCase()) {
        case 'antigravity-claude':
        case 'antigravity-gemini':
            return isAntigravityNativeAvailable();
        case 'anthropic-api':
        case 'claude':
            return !!process.env.ANTHROPIC_API_KEY;
        case 'google-api':
        case 'gemini':
        case 'gemini-flash':
        case 'gemini-pro':
            return !!process.env.GOOGLE_API_KEY;
        default:
            return false;
    }
}

export const MODELS_MAP = MODELS;
export { isAntigravityNativeAvailable, shouldUseExternalAPIs };
