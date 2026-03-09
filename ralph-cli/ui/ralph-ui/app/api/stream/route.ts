import { NextRequest } from 'next/server';
import { runningProcesses } from '../run/route';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
    const runId = req.nextUrl.searchParams.get('runId');

    if (!runId) {
        return new Response('runId is required', { status: 400 });
    }

    const data = runningProcesses.get(runId);

    if (!data) {
        return new Response('Run not found', { status: 404 });
    }

    // Create readable stream for SSE
    const encoder = new TextEncoder();

    const stream = new ReadableStream({
        start(controller) {
            let lastIndex = 0;

            const sendLogs = () => {
                // Send any new logs
                while (lastIndex < data.logs.length) {
                    const line = data.logs[lastIndex];
                    controller.enqueue(encoder.encode(`data: ${line}\n\n`));
                    lastIndex++;
                }

                // Check if done
                if (data.done) {
                    controller.enqueue(encoder.encode(`event: done\ndata: complete\n\n`));
                    controller.close();
                    return;
                }

                // Poll for more logs
                setTimeout(sendLogs, 200);
            };

            sendLogs();
        },
        cancel() {
            // Client disconnected
        },
    });

    return new Response(stream, {
        headers: {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
        },
    });
}
