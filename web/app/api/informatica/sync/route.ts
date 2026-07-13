import { NextResponse } from "next/server";
import { spawn } from "child_process";
import path from "path";

// Store sync state in memory (in production, use a database or cache)
let syncState = {
    running: false,
    message: "",
    startedAt: "",
    progress: 0
};

export async function POST() {
    if (syncState.running) {
        return NextResponse.json(
            { error: "Sync already in progress" },
            { status: 409 }
        );
    }

    syncState = {
        running: true,
        message: "Starting sync...",
        startedAt: new Date().toISOString(),
        progress: 0
    };

    try {
        // Run the scraper script
        const scriptPath = path.join(process.cwd(), "..", "scripts", "scrape_informatica.py");
        const pythonProcess = spawn("python", [scriptPath, "--download-all", "--max-pages", "100"], {
            cwd: path.join(process.cwd(), ".."),
            env: { ...process.env }
        });

        pythonProcess.stdout.on("data", (data) => {
            const output = data.toString();
            console.log("Scraper output:", output);

            // Parse progress from output
            if (output.includes("Discovered")) {
                syncState.message = output.trim();
            } else if (output.includes("Downloading:")) {
                syncState.message = output.trim();
            } else if (output.includes("Complete:")) {
                syncState.message = output.trim();
            }
        });

        pythonProcess.stderr.on("data", (data) => {
            console.error("Scraper error:", data.toString());
        });

        pythonProcess.on("close", (code) => {
            syncState.running = false;
            if (code === 0) {
                syncState.message = "Sync completed successfully";
            } else {
                syncState.message = `Sync failed with code ${code}`;
            }
        });

        pythonProcess.on("error", (error) => {
            syncState.running = false;
            syncState.message = `Sync error: ${error.message}`;
        });

        return NextResponse.json({
            success: true,
            message: "Sync started"
        });
    } catch (error) {
        syncState.running = false;
        syncState.message = `Failed to start sync: ${error}`;
        return NextResponse.json(
            { error: "Failed to start sync" },
            { status: 500 }
        );
    }
}

export async function GET() {
    return NextResponse.json(syncState);
}
