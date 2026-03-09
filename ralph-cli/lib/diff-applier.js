/**
 * Diff Applier - Safely apply unified diffs to files
 */
import fs from 'fs';
import path from 'path';


/**
 * Parse a unified diff string and extract file changes
 * @param {string} diffText - Unified diff content
 * @returns {Array<{file: string, hunks: Array}>}
 */
function parseDiff(diffText) {
    const changes = [];
    const lines = diffText.split('\n');
    let currentFile = null;
    let currentHunk = null;

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];

        // Match file header: --- a/path or +++ b/path
        if (line.startsWith('--- a/') || line.startsWith('--- ')) {
            // Skip, wait for +++
        } else if (line.startsWith('+++ b/') || line.startsWith('+++ ')) {
            const filePath = line.replace(/^\+\+\+ [ab]\//, '').replace(/^\+\+\+ /, '').trim();
            if (filePath && filePath !== '/dev/null') {
                currentFile = { file: filePath, hunks: [] };
                changes.push(currentFile);
            }
        } else if (line.startsWith('@@') && currentFile) {
            // Parse hunk header: @@ -start,count +start,count @@
            const match = line.match(/@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/);
            if (match) {
                currentHunk = {
                    oldStart: parseInt(match[1], 10),
                    oldCount: match[2] ? parseInt(match[2], 10) : 1,
                    newStart: parseInt(match[3], 10),
                    newCount: match[4] ? parseInt(match[4], 10) : 1,
                    lines: []
                };
                currentFile.hunks.push(currentHunk);
            }
        } else if (currentHunk) {
            if (line.startsWith('+') || line.startsWith('-') || line.startsWith(' ')) {
                currentHunk.lines.push(line);
            } else if (line.startsWith('\\')) {
                // "\ No newline at end of file" - ignore
            }
        }
    }

    return changes;
}

/**
 * Apply a parsed diff to a file
 * @param {string} projectRoot - Project root directory
 * @param {{file: string, hunks: Array}} change - Parsed change object
 * @returns {{success: boolean, error?: string}}
 */
function applyChange(projectRoot, change) {
    const filePath = path.resolve(projectRoot, change.file);

    // Security: ensure file is within project root
    if (!filePath.startsWith(path.resolve(projectRoot))) {
        return { success: false, error: `Path traversal attempt: ${change.file}` };
    }

    let content = '';
    let isNewFile = false;

    try {
        content = fs.readFileSync(filePath, 'utf-8');
    } catch (err) {
        if (err.code === 'ENOENT') {
            isNewFile = true;
            content = '';
        } else {
            return { success: false, error: `Cannot read file: ${err.message}` };
        }
    }

    const lines = content.split('\n');

    // Apply hunks in reverse order to preserve line numbers
    const sortedHunks = [...change.hunks].sort((a, b) => b.oldStart - a.oldStart);

    for (const hunk of sortedHunks) {
        const startIdx = hunk.oldStart - 1; // Convert to 0-indexed

        // Build replacement lines
        const newLines = [];
        for (const line of hunk.lines) {
            if (line.startsWith('+')) {
                newLines.push(line.substring(1));
            } else if (line.startsWith(' ')) {
                newLines.push(line.substring(1));
            }
            // Lines starting with '-' are removed (not added to newLines)
        }

        // Count lines to remove
        let removeCount = 0;
        for (const line of hunk.lines) {
            if (line.startsWith('-') || line.startsWith(' ')) {
                removeCount++;
            }
        }

        // Apply the change
        lines.splice(startIdx, removeCount, ...newLines);
    }

    // Ensure directory exists
    const dir = path.dirname(filePath);
    fs.mkdirSync(dir, { recursive: true });

    // Write file
    fs.writeFileSync(filePath, lines.join('\n'), 'utf-8');

    return { success: true };
}

/**
 * Apply a unified diff to a project
 * @param {string} projectRoot - Project root directory
 * @param {string} diffText - Unified diff content
 * @returns {{success: boolean, applied: string[], errors: string[]}}
 */
function applyDiff(projectRoot, diffText) {
    const changes = parseDiff(diffText);
    const applied = [];
    const errors = [];

    for (const change of changes) {
        const result = applyChange(projectRoot, change);
        if (result.success) {
            applied.push(change.file);
        } else {
            errors.push(`${change.file}: ${result.error}`);
        }
    }

    return { success: errors.length === 0, applied, errors };
}

export { parseDiff, applyDiff };

