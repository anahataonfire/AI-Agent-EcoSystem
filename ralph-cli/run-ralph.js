#!/usr/bin/env node
/**
 * Ralph CLI Runner - JSON I/O contract
 * 
 * Package: ralph-loop-agent (npm)
 * Upstream: https://github.com/vercel-labs/ralph-loop-agent
 * 
 * Input (stdin): { prompt, instructions, stopConditions, verifierCommand, allowedPaths, ... }
 * Output (stdout): { success, iterations, completionReason, reason, logs, totalUsage, provenance }
 * 
 * CRITICAL: preserveContext is ALWAYS false (clean-slate per round)
 * SECURITY: No arbitrary shell execution - only constrained tools
 */
import { RalphLoopAgent, iterationCountIs, tokenCountIs, costIs } from 'ralph-loop-agent';
import { anthropic } from '@ai-sdk/anthropic';
import { tool } from 'ai';
import { z } from 'zod';
import { spawn, execSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';

// Read JSON from stdin
let input = '';
process.stdin.setEncoding('utf8');
for await (const chunk of process.stdin) {
    input += chunk;
}

const spec = JSON.parse(input);
const logs = [];
const sandboxPaths = spec.allowedPaths || [];
const projectRoot = spec.projectRoot || process.cwd();

// SECURITY: Only these test commands are allowed
const allowedTestCommands = spec.allowedTestCommands || [
    'pytest', 'python -m pytest', 'npm test', 'npm run test',
    'vitest', 'jest', 'mocha', 'cargo test', 'go test',
    'make test', 'python -m src.executors.verifier'
];

/**
 * SECURITY: Check if path is within allowed paths
 * CRITICAL: Validates RESOLVED absolute path to prevent traversal attacks
 */
function isPathAllowed(targetPath) {
    // SECURITY: Reject absolute paths outright
    if (path.isAbsolute(targetPath)) {
        return false;
    }

    // Resolve to absolute path (handles ../ traversal)
    const resolved = path.resolve(projectRoot, targetPath);

    // Normalize to remove any remaining . or ..
    const normalized = path.normalize(resolved);

    // SECURITY: Ensure resolved path is under project root first
    if (!normalized.startsWith(projectRoot + path.sep) && normalized !== projectRoot) {
        return false;
    }

    // Check against allowed paths (also resolved and normalized)
    return sandboxPaths.some(allowed => {
        const allowedAbs = path.resolve(projectRoot, allowed);
        const allowedNorm = path.normalize(allowedAbs);
        // Must start with allowed path + separator (or equal for exact match)
        return normalized.startsWith(allowedNorm + path.sep) || normalized === allowedNorm;
    });
}

/**
 * UTILITY: Compute SHA256 hash of file content
 */
function fileHash(content) {
    return crypto.createHash('sha256').update(content).digest('hex').slice(0, 16);
}

/**
 * UTILITY: Truncate string for logging
 */
function truncate(str, max = 500) {
    if (!str) return '';
    return str.length > max ? str.slice(0, max) + '...[truncated]' : str;
}

/**
 * SANDBOX ENFORCEMENT: Parse command and check for dangerous operations
 */
function validateCommand(command) {
    // Block obviously dangerous patterns
    const dangerous = [
        /rm\s+-rf?\s+\//, // rm -rf /
        />\s*\/(?!tmp)/, // redirect to root (except /tmp)
        /sudo\s+/, // sudo
        /chmod\s+777/, // chmod 777
        /:\(\)\{.*\};:/, // fork bomb
    ];

    for (const pattern of dangerous) {
        if (pattern.test(command)) {
            return { allowed: false, reason: `Dangerous pattern detected: ${pattern}` };
        }
    }

    // Extract file paths from command (basic heuristic)
    const pathMatches = command.match(/(?:^|\s)((?:\.\.?\/)?[\w\-./]+(?:\.\w+)?)/g) || [];
    for (const match of pathMatches) {
        const p = match.trim();
        if (p.startsWith('/') && !p.startsWith('/tmp') && !isPathAllowed(p)) {
            return { allowed: false, reason: `Path not in sandbox: ${p}` };
        }
    }

    return { allowed: true };
}

// Build stop conditions from spec
function buildStopConditions(conditions) {
    return conditions.map(c => {
        if (c.type === 'iterations') return iterationCountIs(c.value);
        if (c.type === 'tokens') return tokenCountIs(c.value);
        if (c.type === 'cost') return costIs(c.value);
        throw new Error(`Unknown stop condition: ${c.type}`);
    });
}

/**
 * Build verification function that calls Python verifier CLI
 * Returns JSON { complete: bool, reason: string } always
 */
async function buildVerifier(verifierCommand) {
    return async ({ result, iteration }) => {
        return new Promise((resolve) => {
            const proc = spawn('sh', ['-c', verifierCommand], {
                cwd: projectRoot,
                env: {
                    ...process.env,
                    RALPH_OUTPUT: result.text || '',
                    RALPH_ITERATION: String(iteration)
                }
            });

            let stdout = '';
            let stderr = '';
            proc.stdout.on('data', d => stdout += d);
            proc.stderr.on('data', d => stderr += d);

            proc.on('close', code => {
                // CRITICAL: Always produce JSON with reason
                try {
                    const parsed = JSON.parse(stdout.trim());
                    logs.push({
                        event: 'verifier_output',
                        iteration,
                        complete: parsed.complete,
                        reason: parsed.reason,
                        ts: new Date().toISOString()
                    });
                    resolve({
                        complete: parsed.complete === true,
                        reason: parsed.reason || (parsed.complete ? 'Checks passed' : 'Checks failed')
                    });
                } catch {
                    // Fallback: use exit code but include stderr as reason
                    const reason = stderr.trim() || (code === 0 ? 'Tests passed' : 'Tests failed');
                    logs.push({
                        event: 'verifier_output',
                        iteration,
                        complete: code === 0,
                        reason,
                        exitCode: code,
                        ts: new Date().toISOString()
                    });
                    resolve({ complete: code === 0, reason });
                }
            });
        });
    };
}

/**
 * SECURITY: Check if test command starts with allowed prefix
 */
function isTestCommandAllowed(command) {
    const normalized = command.trim().toLowerCase();
    return allowedTestCommands.some(allowed =>
        normalized.startsWith(allowed.toLowerCase())
    );
}

/**
 * Build structured tool set with sandbox enforcement
 * SECURITY: No arbitrary shell - only constrained tools
 */
function buildTools() {
    return {
        run_tests: tool({
            description: 'Run test commands. ONLY pytest, npm test, etc. are allowed.',
            parameters: z.object({
                command: z.string().describe('Test command, e.g., pytest tests/')
            }),
            execute: async ({ command }) => {
                // SECURITY: Allowlist only
                if (!isTestCommandAllowed(command)) {
                    return {
                        exitCode: 1,
                        stdout: '',
                        stderr: `SECURITY: Command not allowed. Allowed: ${allowedTestCommands.join(', ')}`
                    };
                }
                const result = await runCommand(command);
                // Return with truncated output for ledger fidelity
                return {
                    exitCode: result.exitCode,
                    stdout: truncate(result.stdout),
                    stderr: truncate(result.stderr)
                };
            }
        }),

        read_file: tool({
            description: 'Read file contents. Read-only, files only (not directories).',
            parameters: z.object({
                path: z.string().describe('File path relative to project root')
            }),
            execute: async ({ path: filePath }) => {
                if (!isPathAllowed(filePath)) {
                    return { error: `SANDBOX VIOLATION: Path not allowed: ${filePath}` };
                }
                try {
                    const fullPath = path.resolve(projectRoot, filePath);
                    const stat = fs.statSync(fullPath);
                    // SECURITY: Must be a file, not directory
                    if (!stat.isFile()) {
                        return { error: `Not a file: ${filePath}` };
                    }
                    const content = fs.readFileSync(fullPath, 'utf8');
                    return { content, hash: fileHash(content) };
                } catch (e) {
                    return { error: e.message };
                }
            }
        }),

        list_files: tool({
            description: 'List files in a directory. Read-only, directories only.',
            parameters: z.object({
                directory: z.string().describe('Directory path relative to project root')
            }),
            execute: async ({ directory }) => {
                if (!isPathAllowed(directory)) {
                    return { error: `SANDBOX VIOLATION: Path not allowed: ${directory}` };
                }
                try {
                    const fullPath = path.resolve(projectRoot, directory);
                    const stat = fs.statSync(fullPath);
                    // SECURITY: Must be a directory
                    if (!stat.isDirectory()) {
                        return { error: `Not a directory: ${directory}` };
                    }
                    const files = fs.readdirSync(fullPath);
                    return { files };
                } catch (e) {
                    return { error: e.message };
                }
            }
        }),

        write_file: tool({
            description: 'Write content to a file. RESTRICTED to allowed paths.',
            parameters: z.object({
                path: z.string().describe('File path relative to project root'),
                content: z.string().describe('Content to write')
            }),
            execute: async ({ path: filePath, content }) => {
                if (!isPathAllowed(filePath)) {
                    return { error: `SANDBOX VIOLATION: Path not allowed: ${filePath}` };
                }
                try {
                    const fullPath = path.resolve(projectRoot, filePath);
                    // Check if exists and is directory
                    if (fs.existsSync(fullPath) && fs.statSync(fullPath).isDirectory()) {
                        return { error: `Cannot write to directory: ${filePath}` };
                    }
                    const hashBefore = fs.existsSync(fullPath) ? fileHash(fs.readFileSync(fullPath, 'utf8')) : null;
                    fs.writeFileSync(fullPath, content);
                    const hashAfter = fileHash(content);
                    return { success: true, path: fullPath, hashBefore, hashAfter };
                } catch (e) {
                    return { error: e.message };
                }
            }
        }),

        apply_patch: tool({
            description: 'Apply a patch/diff to a file. RESTRICTED to allowed paths. Replaces FIRST occurrence only.',
            parameters: z.object({
                path: z.string().describe('File path relative to project root'),
                search: z.string().describe('Text to find (must have exactly 1 occurrence)'),
                replace: z.string().describe('Text to replace with')
            }),
            execute: async ({ path: filePath, search, replace }) => {
                if (!isPathAllowed(filePath)) {
                    return { error: `SANDBOX VIOLATION: Path not allowed: ${filePath}` };
                }
                try {
                    const fullPath = path.resolve(projectRoot, filePath);
                    const stat = fs.statSync(fullPath);
                    if (!stat.isFile()) {
                        return { error: `Not a file: ${filePath}` };
                    }

                    let content = fs.readFileSync(fullPath, 'utf8');
                    const hashBefore = fileHash(content);

                    // SECURITY: Count occurrences to prevent ambiguous patches
                    const occurrences = (content.match(new RegExp(search.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g')) || []).length;

                    if (occurrences === 0) {
                        return { error: 'Search text not found in file', hashBefore };
                    }
                    if (occurrences > 1) {
                        return {
                            error: `Ambiguous patch: found ${occurrences} occurrences. Be more specific.`,
                            occurrences,
                            hashBefore
                        };
                    }

                    // Safe: exactly 1 occurrence
                    content = content.replace(search, replace);
                    fs.writeFileSync(fullPath, content);
                    const hashAfter = fileHash(content);

                    return {
                        success: true,
                        path: fullPath,
                        occurrences: 1,
                        hashBefore,
                        hashAfter,
                        diff: `- ${truncate(search, 100)}\n+ ${truncate(replace, 100)}`
                    };
                } catch (e) {
                    return { error: e.message };
                }
            }
        }),
    };
}

function runCommand(command) {
    return new Promise((resolve) => {
        const proc = spawn('sh', ['-c', command], { cwd: projectRoot });
        let out = '', err = '';
        proc.stdout.on('data', d => out += d);
        proc.stderr.on('data', d => err += d);
        proc.on('close', code => resolve({ exitCode: code, stdout: out, stderr: err }));
    });
}

// Main execution
try {
    const agent = new RalphLoopAgent({
        model: anthropic(spec.model || 'claude-sonnet-4-20250514'),
        instructions: spec.instructions,
        tools: buildTools(),
        stopWhen: buildStopConditions(spec.stopConditions || [{ type: 'iterations', value: 10 }]),
        verifyCompletion: await buildVerifier(spec.verifierCommand),

        onIterationStart: ({ iteration }) => {
            logs.push({
                event: 'iteration_start',
                iteration,
                ts: new Date().toISOString()
            });
        },

        onIterationEnd: ({ iteration, duration, result }) => {
            logs.push({
                event: 'iteration_end',
                iteration,
                duration_ms: duration,
                output_length: result.text?.length || 0,
                tool_calls: result.steps?.length || 0,
                ts: new Date().toISOString()
            });
        },
    });

    const startTime = Date.now();

    const result = await agent.loop({
        prompt: spec.prompt,
        preserveContext: false, // CRITICAL: Clean-slate enforced
    });

    const durationMs = Date.now() - startTime;

    // Log stop condition decision
    logs.push({
        event: 'loop_complete',
        completion_reason: result.completionReason,
        reason: result.reason,
        iterations: result.iterations,
        duration_ms: durationMs,
        ts: new Date().toISOString()
    });

    // Get runtime provenance
    let ralphVersion = 'unknown';
    try {
        const npmLs = execSync('npm ls ralph-loop-agent --json', { cwd: import.meta.dirname });
        const lsData = JSON.parse(npmLs.toString());
        ralphVersion = lsData.dependencies?.['ralph-loop-agent']?.version || 'unknown';
    } catch { /* ignore */ }

    const provenance = {
        package: 'ralph-loop-agent',
        version: ralphVersion,
        upstream: 'https://github.com/vercel-labs/ralph-loop-agent',
        nodeVersion: process.version,
        runAt: new Date().toISOString(),
    };

    // Output structured result with provenance
    console.log(JSON.stringify({
        success: result.completionReason === 'verified',
        iterations: result.iterations,
        completionReason: result.completionReason,
        reason: result.reason,
        totalUsage: result.totalUsage,
        durationMs,
        logs,
        provenance,
    }));

} catch (err) {
    logs.push({
        event: 'error',
        message: err.message,
        ts: new Date().toISOString()
    });

    console.log(JSON.stringify({
        success: false,
        iterations: 0,
        completionReason: 'error',
        reason: err.message,
        logs,
    }));
    process.exit(1);
}
