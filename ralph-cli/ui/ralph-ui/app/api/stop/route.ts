import { NextRequest, NextResponse } from 'next/server';
import { runningProcesses } from '../run/route';

export async function POST(req: NextRequest) {
    try {
        const { runId } = await req.json();

        if (!runId) {
            return NextResponse.json({ error: 'runId is required' }, { status: 400 });
        }

        const data = runningProcesses.get(runId);

        if (!data) {
            return NextResponse.json({ error: 'Run not found' }, { status: 404 });
        }

        if (data.done) {
            return NextResponse.json({ success: true, message: 'Already stopped' });
        }

        const proc = data.process;

        // Try SIGTERM first
        proc.kill('SIGTERM');

        // Give it 5 seconds, then SIGKILL
        setTimeout(() => {
            try {
                if (!data.done) {
                    proc.kill('SIGKILL');
                }
            } catch { }
        }, 5000);

        data.logs.push('[Stopping...]');

        return NextResponse.json({ success: true });
    } catch (err: any) {
        return NextResponse.json({ error: err.message }, { status: 500 });
    }
}
