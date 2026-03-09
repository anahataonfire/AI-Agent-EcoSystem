import { NextRequest, NextResponse } from 'next/server';
import { execSync } from 'child_process';
import path from 'path';
import fs from 'fs';

export async function GET(req: NextRequest) {
    const projectPath = req.nextUrl.searchParams.get('path');

    if (!projectPath) {
        return NextResponse.json({ error: 'Path is required' }, { status: 400 });
    }

    try {
        // Check if it's a git repo
        const gitDir = path.join(projectPath, '.git');
        if (!fs.existsSync(gitDir)) {
            return NextResponse.json({ branch: '', log: [] });
        }

        // Get current branch
        let branch = '';
        try {
            branch = execSync('git branch --show-current', {
                cwd: projectPath,
                encoding: 'utf-8',
            }).trim();
        } catch { }

        // Get log
        const log: { hash: string; message: string }[] = [];
        try {
            const logOutput = execSync('git log --oneline -10', {
                cwd: projectPath,
                encoding: 'utf-8',
            });

            for (const line of logOutput.trim().split('\n')) {
                const [hash, ...messageParts] = line.split(' ');
                if (hash) {
                    log.push({ hash: hash.substring(0, 7), message: messageParts.join(' ') });
                }
            }
        } catch { }

        return NextResponse.json({ branch, log });
    } catch (err: any) {
        return NextResponse.json({ error: err.message }, { status: 500 });
    }
}
