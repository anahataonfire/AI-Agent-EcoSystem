import { NextRequest, NextResponse } from 'next/server';
import { spawn, ChildProcess } from 'child_process';
import { randomUUID } from 'crypto';
import path from 'path';

// Store running processes
const runningProcesses = new Map<string, {
    process: ChildProcess;
    logs: string[];
    done: boolean;
}>();

// Clean up old processes
setInterval(() => {
    const now = Date.now();
    for (const [id, data] of runningProcesses) {
        if (data.done && data.logs.length === 0) {
            runningProcesses.delete(id);
        }
    }
}, 60000);

export async function POST(req: NextRequest) {
    try {
        const { path: projectPath, tool, maxIterations } = await req.json();

        if (!projectPath) {
            return NextResponse.json({ error: 'Path is required' }, { status: 400 });
        }

        const runId = randomUUID();

        // Find ralph.sh - look up from project path to ralph-cli
        const ralphScript = path.resolve(projectPath, '../ralph.sh');

        // Spawn ralph.sh
        const proc = spawn('bash', [
            ralphScript,
            '--tool', tool || 'antigravity-claude',
            String(maxIterations || 10)
        ], {
            cwd: projectPath,
            env: {
                ...process.env,
                RALPH_PROJECT_PATH: projectPath,
            },
        });

        const data = {
            process: proc,
            logs: [] as string[],
            done: false,
        };

        runningProcesses.set(runId, data);

        proc.stdout?.on('data', (chunk) => {
            const lines = chunk.toString().split('\n').filter(Boolean);
            data.logs.push(...lines);
        });

        proc.stderr?.on('data', (chunk) => {
            const lines = chunk.toString().split('\n').filter(Boolean);
            data.logs.push(...lines);
        });

        proc.on('close', () => {
            data.done = true;
            data.logs.push('[Process exited]');
        });

        proc.on('error', (err) => {
            data.done = true;
            data.logs.push(`[Error: ${err.message}]`);
        });

        return NextResponse.json({ runId });
    } catch (err: any) {
        return NextResponse.json({ error: err.message }, { status: 500 });
    }
}

// Export the map for other routes
export { runningProcesses };
