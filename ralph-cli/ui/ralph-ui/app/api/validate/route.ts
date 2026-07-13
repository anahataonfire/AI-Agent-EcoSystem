import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function POST(req: NextRequest) {
    try {
        const { path: projectPath } = await req.json();

        if (!projectPath) {
            return NextResponse.json({ valid: false, error: 'Path is required' });
        }

        // Security: resolve and check path
        const resolved = path.resolve(projectPath);

        // Check if directory exists
        if (!fs.existsSync(resolved)) {
            return NextResponse.json({ valid: false, error: 'Directory does not exist' });
        }

        if (!fs.statSync(resolved).isDirectory()) {
            return NextResponse.json({ valid: false, error: 'Path is not a directory' });
        }

        // Check for prd.json
        const prdPath = path.join(resolved, 'prd.json');
        if (!fs.existsSync(prdPath)) {
            return NextResponse.json({ valid: false, error: 'prd.json not found in directory' });
        }

        // Verify prd.json is valid JSON
        try {
            JSON.parse(fs.readFileSync(prdPath, 'utf-8'));
        } catch {
            return NextResponse.json({ valid: false, error: 'prd.json is not valid JSON' });
        }

        return NextResponse.json({ valid: true, path: resolved });
    } catch (err: any) {
        return NextResponse.json({ valid: false, error: err.message });
    }
}
