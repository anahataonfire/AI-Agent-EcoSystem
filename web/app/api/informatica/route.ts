import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";

const DATA_DIR = path.join(process.cwd(), "..", "data", "informatica_docs");
const MANIFEST_PATH = path.join(DATA_DIR, "download_manifest.json");

interface Document {
    url: string;
    title: string;
    category: string;
    local_path: string;
    sha256: string;
    downloaded_at: string;
    size_bytes: number;
    version: string;
    updated: boolean;
}

interface Manifest {
    last_run: string;
    documents: Document[];
}

async function loadManifest(): Promise<Manifest> {
    try {
        const data = await fs.readFile(MANIFEST_PATH, "utf-8");
        return JSON.parse(data);
    } catch {
        return { last_run: "", documents: [] };
    }
}

function calculateStats(manifest: Manifest) {
    const totalSize = manifest.documents.reduce((sum, d) => sum + d.size_bytes, 0);
    const updatedCount = manifest.documents.filter(d => d.updated).length;

    // Group by category
    const byCategory: Record<string, { count: number; size: number }> = {};
    for (const doc of manifest.documents) {
        if (!byCategory[doc.category]) {
            byCategory[doc.category] = { count: 0, size: 0 };
        }
        byCategory[doc.category].count++;
        byCategory[doc.category].size += doc.size_bytes;
    }

    return {
        total_documents: manifest.documents.length,
        total_size_bytes: totalSize,
        total_size_mb: Math.round(totalSize / 1024 / 1024 * 100) / 100,
        updated_count: updatedCount,
        last_run: manifest.last_run,
        by_category: byCategory
    };
}

export async function GET() {
    try {
        const manifest = await loadManifest();
        const stats = calculateStats(manifest);

        return NextResponse.json({
            manifest,
            stats
        });
    } catch (error) {
        console.error("Error loading manifest:", error);
        return NextResponse.json(
            { error: "Failed to load manifest" },
            { status: 500 }
        );
    }
}
