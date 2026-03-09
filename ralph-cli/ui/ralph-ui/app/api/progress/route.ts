import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET(req: NextRequest) {
    const projectPath = req.nextUrl.searchParams.get('path');

    if (!projectPath) {
        return NextResponse.json({ error: 'Path is required' }, { status: 400 });
    }

    try {
        const progressPath = path.join(projectPath, 'progress.txt');

        if (!fs.existsSync(progressPath)) {
            return NextResponse.json({ content: '' });
        }

        const content = fs.readFileSync(progressPath, 'utf-8');
        return NextResponse.json({ content });
    } catch (err: any) {
        return NextResponse.json({ error: err.message }, { status: 500 });
    }
}
