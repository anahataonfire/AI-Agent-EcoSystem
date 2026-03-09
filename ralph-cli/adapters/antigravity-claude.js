#!/usr/bin/env node
/**
 * Antigravity-Claude Adapter for Ralph
 * 
 * This adapter runs inside Ralph's iteration loop and:
 * 1. Reads prd.json to find highest-priority failing story
 * 2. Reads progress.txt for context
 * 3. Calls LLM with coding instructions (auto-failover: Claude -> Gemini)
 * 4. Applies unified diffs from response
 * 5. Runs allowlisted test commands
 * 6. Updates progress.txt and prd.json
 * 7. Commits changes
 * 8. Emits <promise>COMPLETE</promise> when all stories pass
 * 
 * Environment:
 *   ANTHROPIC_API_KEY - Claude API key (or use Antigravity-native when available)
 *   GOOGLE_API_KEY - Gemini API key (fallback model)
 *   FORCE_FALLBACK - Set to "1" to simulate Claude quota exhaustion
 *   RALPH_PROJECT_PATH - Target project path (default: cwd)
 */

import fs from 'fs';
import path from 'path';
import { execSync, spawn } from 'child_process';
import { isCommandAllowed, getAllowedCommandsList } from '../lib/command-allowlist.js';
import { applyDiff } from '../lib/diff-applier.js';
import { ModelRouter } from '../lib/model-router.js';




/**
 * Git operations
 */
function gitCommit(projectPath, message) {
    try {
        execSync('git add -A', { cwd: projectPath, stdio: 'pipe' });
        execSync(`git commit -m "${message.replace(/"/g, '\\"')}"`, {
            cwd: projectPath,
            stdio: 'pipe'
        });
        console.log(`[Git] Committed: ${message}`);
        return true;
    } catch (err) {
        console.error(`[Git] Commit failed: ${err.message}`);
        return false;
    }
}

function ensureBranch(projectPath, branchName) {
    try {
        const currentBranch = execSync('git branch --show-current', {
            cwd: projectPath,
            encoding: 'utf-8'
        }).trim();

        if (currentBranch !== branchName) {
            try {
                execSync(`git checkout ${branchName}`, { cwd: projectPath, stdio: 'pipe' });
            } catch {
                execSync(`git checkout -b ${branchName}`, { cwd: projectPath, stdio: 'pipe' });
            }
            console.log(`[Git] Switched to branch: ${branchName}`);
        }
        return true;
    } catch (err) {
        console.error(`[Git] Branch error: ${err.message}`);
        return false;
    }
}

/**
 * Run a test command with security check
 */
function runTestCommand(projectPath, command) {
    const check = isCommandAllowed(command);
    if (!check.allowed) {
        console.error(`[Security] BLOCKED: ${check.reason}`);
        console.error(`[Security] Allowed commands: ${getAllowedCommandsList().join(', ')}`);
        return { success: false, output: check.reason };
    }

    console.log(`[Test] Running: ${command}`);
    try {
        const output = execSync(command, {
            cwd: projectPath,
            encoding: 'utf-8',
            stdio: ['pipe', 'pipe', 'pipe'],
            timeout: 120000 // 2 minute timeout
        });
        console.log(`[Test] PASSED`);
        return { success: true, output };
    } catch (err) {
        console.log(`[Test] FAILED`);
        return { success: false, output: err.stdout + '\n' + err.stderr };
    }
}

/**
 * Read project context files
 */
function readContext(projectPath) {
    const prdPath = path.join(projectPath, 'prd.json');
    const progressPath = path.join(projectPath, 'progress.txt');

    let prd = null;
    let progress = '';

    try {
        prd = JSON.parse(fs.readFileSync(prdPath, 'utf-8'));
    } catch (err) {
        console.error(`[Context] Cannot read prd.json: ${err.message}`);
        return null;
    }

    try {
        progress = fs.readFileSync(progressPath, 'utf-8');
    } catch {
        progress = '# Ralph Progress Log\n---\n';
    }

    return { prd, progress, prdPath, progressPath };
}

/**
 * Find the next story to work on (highest priority with passes=false)
 */
function findNextStory(prd) {
    const stories = prd.userStories || prd.stories || [];
    const pending = stories
        .filter(s => !s.passes)
        .sort((a, b) => (a.priority || 0) - (b.priority || 0));

    return pending.length > 0 ? pending[0] : null;
}

/**
 * Check if all stories pass
 */
function allStoriesPass(prd) {
    const stories = prd.userStories || prd.stories || [];
    return stories.every(s => s.passes);
}

/**
 * Build the system prompt for Claude
 */
function buildSystemPrompt() {
    return `You are an autonomous coding agent. You will be given a user story to implement.

OUTPUT FORMAT:
You MUST output ONLY a unified diff that implements the required changes. No explanations, no markdown code fences around the entire response.

Example output:
--- a/src/example.js
+++ b/src/example.js
@@ -1,3 +1,4 @@
 function add(a, b) {
-  return a - b; // bug
+  return a + b; // fixed
 }

RULES:
1. Output ONLY unified diff format
2. Make minimal, focused changes
3. Follow existing code patterns
4. Ensure the changes will make tests pass
5. Do not include explanations outside the diff`;
}

/**
 * Build the user prompt for a story
 */
function buildUserPrompt(story, progress, projectFiles) {
    const criteria = story.acceptanceCriteria || story.acceptance_criteria || [];

    return `# Story: ${story.id} - ${story.title}

${story.description || ''}

## Acceptance Criteria
${criteria.map(c => `- ${c}`).join('\n')}

## Progress Context
${progress.substring(0, 2000)}

## Relevant Files
${projectFiles}

Implement this story. Output ONLY the unified diff.`;
}

/**
 * Read relevant project files for context
 */
function readProjectFiles(projectPath) {
    const extensions = ['.js', '.ts', '.jsx', '.tsx', '.py', '.json', '.md'];
    const ignoreDirs = ['node_modules', '.git', 'dist', 'build', '__pycache__'];
    const files = [];

    function walk(dir, depth = 0) {
        if (depth > 3) return; // Limit depth

        try {
            const entries = fs.readdirSync(dir, { withFileTypes: true });
            for (const entry of entries) {
                if (ignoreDirs.includes(entry.name)) continue;

                const fullPath = path.join(dir, entry.name);
                const relPath = path.relative(projectPath, fullPath);

                if (entry.isDirectory()) {
                    walk(fullPath, depth + 1);
                } else if (extensions.some(ext => entry.name.endsWith(ext))) {
                    try {
                        const content = fs.readFileSync(fullPath, 'utf-8');
                        if (content.length < 5000) { // Only include small files
                            files.push(`### ${relPath}\n\`\`\`\n${content}\n\`\`\``);
                        }
                    } catch { }
                }
            }
        } catch { }
    }

    walk(projectPath);
    return files.slice(0, 10).join('\n\n'); // Limit to 10 files
}

/**
 * Update prd.json to mark story as passing
 */
function markStoryPassing(prdPath, prd, storyId) {
    const stories = prd.userStories || prd.stories || [];
    const story = stories.find(s => s.id === storyId);
    if (story) {
        story.passes = true;
    }
    fs.writeFileSync(prdPath, JSON.stringify(prd, null, 2), 'utf-8');
    console.log(`[PRD] Marked ${storyId} as passing`);
}

/**
 * Append to progress.txt
 */
function appendProgress(progressPath, storyId, storyTitle, filesChanged, learnings) {
    const timestamp = new Date().toISOString();
    const entry = `
## ${timestamp} - ${storyId}
- Implemented: ${storyTitle}
- Files changed: ${filesChanged.join(', ')}
- **Learnings:** ${learnings || 'No specific learnings'}
---
`;
    fs.appendFileSync(progressPath, entry, 'utf-8');
    console.log(`[Progress] Appended entry for ${storyId}`);
}

/**
 * Detect test command from project
 */
function detectTestCommand(projectPath) {
    // Check package.json for npm test
    const pkgPath = path.join(projectPath, 'package.json');
    if (fs.existsSync(pkgPath)) {
        return 'npm test';
    }

    // Check for pytest
    if (fs.existsSync(path.join(projectPath, 'pytest.ini')) ||
        fs.existsSync(path.join(projectPath, 'pyproject.toml')) ||
        fs.existsSync(path.join(projectPath, 'test')) ||
        fs.existsSync(path.join(projectPath, 'tests'))) {
        return 'pytest';
    }

    // Check for Makefile
    if (fs.existsSync(path.join(projectPath, 'Makefile'))) {
        return 'make test';
    }

    return null;
}

/**
 * Main execution
 */
async function main() {
    const projectPath = process.env.RALPH_PROJECT_PATH || process.cwd();
    console.log(`[Ralph] Antigravity-Claude adapter starting`);
    console.log(`[Ralph] Project path: ${projectPath}`);

    // Read context
    const context = readContext(projectPath);
    if (!context) {
        console.error('[Ralph] Failed to read project context');
        process.exit(1);
    }

    const { prd, progress, prdPath, progressPath } = context;

    // Check if all stories already pass
    if (allStoriesPass(prd)) {
        console.log('<promise>COMPLETE</promise>');
        process.exit(0);
    }

    // Ensure we're on the correct branch
    if (prd.branchName) {
        ensureBranch(projectPath, prd.branchName);
    }

    // Find next story
    const story = findNextStory(prd);
    if (!story) {
        console.log('[Ralph] No pending stories found');
        console.log('<promise>COMPLETE</promise>');
        process.exit(0);
    }

    console.log(`[Ralph] Working on: ${story.id} - ${story.title}`);

    // Initialize model router (with auto-failover)
    const router = new ModelRouter();

    // Read project files for context
    const projectFiles = readProjectFiles(projectPath);

    // Build prompts
    const systemPrompt = buildSystemPrompt();
    const userPrompt = buildUserPrompt(story, progress, projectFiles);

    // Call model (with automatic failover)
    console.log('[Model] Requesting implementation...');
    let response;
    try {
        response = await router.complete(systemPrompt, userPrompt);
    } catch (err) {
        console.error(`[Model] API error: ${err.message}`);
        router.cleanup();
        process.exit(1);
    }

    // Apply diff
    console.log('[Diff] Applying changes...');
    const diffResult = applyDiff(projectPath, response);

    if (diffResult.applied.length === 0) {
        console.error('[Diff] No changes were applied');
        console.error('[Diff] Response was:', response.substring(0, 500));
        process.exit(1);
    }

    console.log(`[Diff] Applied changes to: ${diffResult.applied.join(', ')}`);

    if (diffResult.errors.length > 0) {
        console.warn(`[Diff] Errors: ${diffResult.errors.join('; ')}`);
    }

    // Detect and run tests
    const testCmd = detectTestCommand(projectPath);
    if (testCmd) {
        const testResult = runTestCommand(projectPath, testCmd);

        if (!testResult.success) {
            console.error('[Test] Tests failed, not marking story as passing');
            // Still commit the attempt
            gitCommit(projectPath, `wip: ${story.id} - attempt (tests failing)`);
            process.exit(1);
        }
    } else {
        console.log('[Test] No test command detected, skipping tests');
    }

    // Mark story as passing
    markStoryPassing(prdPath, prd, story.id);

    // Append progress
    appendProgress(
        progressPath,
        story.id,
        story.title,
        diffResult.applied,
        'Implementation complete via ' + router.getCurrentModel() + ' adapter'
    );

    // Commit
    gitCommit(projectPath, `feat: ${story.id} - ${story.title}`);

    // Check if all stories now pass
    const updatedPrd = JSON.parse(fs.readFileSync(prdPath, 'utf-8'));
    if (allStoriesPass(updatedPrd)) {
        console.log('[Ralph] All stories complete!');
        console.log('<promise>COMPLETE</promise>');
    } else {
        console.log('[Ralph] Story complete, more stories remaining');
    }
}

main().catch(err => {
    console.error(`[Ralph] Fatal error: ${err.message}`);
    process.exit(1);
});
