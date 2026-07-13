import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET(req: NextRequest) {
    const projectPath = req.nextUrl.searchParams.get('path');

    if (!projectPath) {
        return NextResponse.json({ error: 'Path is required' }, { status: 400 });
    }

    try {
        const prdPath = path.join(projectPath, 'prd.json');
        const content = fs.readFileSync(prdPath, 'utf-8');
        return NextResponse.json(JSON.parse(content));
    } catch (err: any) {
        return NextResponse.json({ error: err.message }, { status: 500 });
    }
}

export async function PUT(req: NextRequest) {
    const projectPath = req.nextUrl.searchParams.get('path');

    if (!projectPath) {
        return NextResponse.json({ error: 'Path is required' }, { status: 400 });
    }

    try {
        const prd = await req.json();
        const prdPath = path.join(projectPath, 'prd.json');

        // Atomic write: write to temp, then rename
        const tempPath = prdPath + '.tmp';
        fs.writeFileSync(tempPath, JSON.stringify(prd, null, 2), 'utf-8');
        fs.renameSync(tempPath, prdPath);

        return NextResponse.json({ success: true });
    } catch (err: any) {
        return NextResponse.json({ error: err.message }, { status: 500 });
    }
}
