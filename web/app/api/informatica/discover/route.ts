import { NextResponse } from "next/server";
import { spawn } from "child_process";
import path from "path";

interface DiscoveredDoc {
    url: string;
    title: string;
    category: string;
    version: string;
    product_version: string;
    release_date: string;
    last_updated: string;
    doc_type: "pdf" | "zip";
}

// Store discovery state in memory
let discoveryState = {
    running: false,
    message: "",
    startedAt: "",
    documents: [] as DiscoveredDoc[],
    complete: false
};

export async function POST(request: Request) {
    const body = await request.json().catch(() => ({}));
    const maxPages = body.maxPages || 100;
    const allVersions = body.allVersions || false;

    if (discoveryState.running) {
        return NextResponse.json(
            { error: "Discovery already in progress" },
            { status: 409 }
        );
    }

    discoveryState = {
        running: true,
        message: "Starting discovery...",
        startedAt: new Date().toISOString(),
        documents: [],
        complete: false
    };

    try {
        // Run the scraper in discover-only mode with JSON output
        const scriptPath = path.join(process.cwd(), "..", "scripts", "scrape_informatica.py");
        const args = [
            scriptPath,
            "--discover-only",
            "--max-pages", maxPages.toString(),
            "--json-output"
        ];

        // Add --all-versions flag if user wants historical versions
        if (allVersions) {
            args.push("--all-versions");
        }

        const pythonProcess = spawn("python3", args, {
            cwd: path.join(process.cwd(), ".."),
            env: { ...process.env }
        });

        let output = "";

        pythonProcess.stdout.on("data", (data) => {
            const text = data.toString();
            output += text;
            console.log("Discovery output:", text);

            // Parse progress from non-JSON output lines
            if (text.includes("Logging in")) {
                discoveryState.message = "Logging in...";
            } else if (text.includes("Login successful")) {
                discoveryState.message = "Login successful, discovering...";
            } else if (text.includes("category pages")) {
                const match = text.match(/Found (\d+) category/);
                if (match) {
                    discoveryState.message = `Found ${match[1]} categories, scanning...`;
                }
            } else if (text.includes("Scanning:")) {
                const urlMatch = text.match(/Scanning: (.+)/);
                if (urlMatch) {
                    discoveryState.message = `Scanning: ${urlMatch[1].slice(-50)}...`;
                }
            } else if (text.includes("Discovered")) {
                const countMatch = text.match(/Discovered (\d+) unique/);
                if (countMatch) {
                    discoveryState.message = `Discovered ${countMatch[1]} documents`;
                }
            }
        });

        pythonProcess.stderr.on("data", (data) => {
            console.error("Discovery error:", data.toString());
        });

        pythonProcess.on("close", (code) => {
            discoveryState.running = false;
            discoveryState.complete = true;

            if (code === 0) {
                // Parse JSON output between markers
                const jsonStart = output.indexOf("---JSON_OUTPUT_START---");
                const jsonEnd = output.indexOf("---JSON_OUTPUT_END---");

                if (jsonStart !== -1 && jsonEnd !== -1) {
                    try {
                        const jsonStr = output.slice(jsonStart + "---JSON_OUTPUT_START---".length, jsonEnd).trim();
                        const parsed = JSON.parse(jsonStr);

                        discoveryState.documents = parsed.documents.map((doc: any) => ({
                            url: doc.url,
                            title: doc.title,
                            category: doc.category,
                            version: doc.version || "",
                            product_version: doc.product_version || "",
                            release_date: doc.release_date || "",
                            last_updated: doc.last_updated || "",
                            doc_type: doc.doc_type || (doc.url.endsWith(".zip") ? "zip" : "pdf")
                        }));

                        discoveryState.message = `Discovery complete: ${discoveryState.documents.length} documents found`;
                    } catch (e) {
                        console.error("Failed to parse JSON output:", e);
                        discoveryState.message = `Discovery complete but failed to parse output`;
                    }
                } else {
                    // Fallback to simple parsing
                    const docs: DiscoveredDoc[] = [];
                    const lines = output.split("\n");
                    let inDiscoveredSection = false;

                    for (const line of lines) {
                        if (line.includes("Discovered PDFs:")) {
                            inDiscoveredSection = true;
                            continue;
                        }

                        if (inDiscoveredSection && line.trim().startsWith("- ")) {
                            const match = line.match(/^\s*-\s*(.+?):\s*(https?:\/\/.+)$/);
                            if (match) {
                                const title = match[1].trim();
                                const url = match[2].trim();

                                docs.push({
                                    url,
                                    title,
                                    category: title.split("/")[0] || "general",
                                    version: "",
                                    product_version: "",
                                    release_date: "",
                                    last_updated: "",
                                    doc_type: url.endsWith(".zip") ? "zip" : "pdf"
                                });
                            }
                        }
                    }

                    discoveryState.documents = docs;
                    discoveryState.message = `Discovery complete: ${docs.length} documents found`;
                }
            } else {
                discoveryState.message = `Discovery failed with code ${code}`;
            }
        });

        pythonProcess.on("error", (error) => {
            discoveryState.running = false;
            discoveryState.message = `Discovery error: ${error.message}`;
        });

        return NextResponse.json({
            success: true,
            message: "Discovery started"
        });
    } catch (error) {
        discoveryState.running = false;
        discoveryState.message = `Failed to start discovery: ${error}`;
        return NextResponse.json(
            { error: "Failed to start discovery" },
            { status: 500 }
        );
    }
}

export async function GET() {
    return NextResponse.json(discoveryState);
}
