/**
 * Command Allowlist - Security enforcement for Ralph test commands
 * ONLY these patterns are permitted for execution
 */

const ALLOWED_PATTERNS = [
    /^pytest(\s|$)/,
    /^python\s+-m\s+pytest(\s|$)/,
    /^npm\s+test(\s|$)/,
    /^npm\s+run\s+test(\s|$)/,
    /^pnpm\s+test(\s|$)/,
    /^pnpm\s+run\s+test(\s|$)/,
    /^bun\s+test(\s|$)/,
    /^go\s+test\s+\.\/\.\.\./,
    /^cargo\s+test(\s|$)/,
    /^make\s+test(\s|$)/,
    /^npx\s+jest(\s|$)/,
    /^npx\s+vitest(\s|$)/,
];

/**
 * Check if a command is in the security allowlist
 * @param {string} cmd - The command to check
 * @returns {{allowed: boolean, reason?: string}}
 */
export function isCommandAllowed(cmd) {
    const trimmed = cmd.trim();

    if (!trimmed) {
        return { allowed: false, reason: 'Empty command' };
    }

    // Check against allowlist
    for (const pattern of ALLOWED_PATTERNS) {
        if (pattern.test(trimmed)) {
            return { allowed: true };
        }
    }

    return {
        allowed: false,
        reason: `Command not in allowlist: "${trimmed.substring(0, 50)}..."`
    };
}

/**
 * Get human-readable list of allowed commands
 * @returns {string[]}
 */
export function getAllowedCommandsList() {
    return [
        'pytest [args]',
        'python -m pytest [args]',
        'npm test',
        'npm run test',
        'pnpm test',
        'pnpm run test',
        'bun test',
        'go test ./...',
        'cargo test',
        'make test',
        'npx jest',
        'npx vitest',
    ];
}

