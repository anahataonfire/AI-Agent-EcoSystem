import os
import shutil
import zipfile
import re
from pathlib import Path

# Absolute paths based on user environment
ROOT_DIR = Path("/Users/adamc/Documents/001 AI Agents/AI Agent EcoSystem 2.0")
DATA_DIR = ROOT_DIR / "data" / "informatica_docs"
TARGET_DIR = ROOT_DIR / "data" / "informatica_notebook_ready"
TEMP_DIR = ROOT_DIR / "data" / "temp_consolidation"

def consolidate():
    if not DATA_DIR.exists():
        print(f"❌ Error: Source directory {DATA_DIR} not found.")
        return

    # Prepare directories
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)
    TEMP_DIR.mkdir(parents=True)

    print(f"🚀 Starting doc consolidation from: {DATA_DIR}")
    
    pdf_count = 0
    zip_count = 0
    
    # Process all files recursively
    for root, dirs, files in os.walk(DATA_DIR):
        for file in files:
            # Skip manifest and hidden files
            if file == "download_manifest.json" or file.startswith("."):
                continue
                
            file_path = Path(root) / file
            rel_path = file_path.relative_to(DATA_DIR)
            
            # Create a unique flat filename by joining path parts with double underscores
            prefix = str(rel_path.parent).replace(os.sep, "__").replace(".", "_")
            if prefix == "_" or prefix == "":
                flat_name = file
            else:
                flat_name = f"{prefix}__{file}"
            
            # Final sanitization
            flat_name = re.sub(r'[^\w\-_\.]', '_', flat_name)
            
            if file.lower().endswith(".pdf"):
                shutil.copy2(file_path, TEMP_DIR / flat_name)
                pdf_count += 1
            elif file.lower().endswith(".zip"):
                zip_count += 1
                try:
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        for member in zip_ref.namelist():
                            if member.lower().endswith(".pdf"):
                                # Flatten zip contents too
                                basename = os.path.basename(member)
                                if not basename: continue
                                zip_flat_name = f"{flat_name}_EXTRACTED_{basename}"
                                zip_flat_name = re.sub(r'[^\w\-_\.]', '_', zip_flat_name)
                                with zip_ref.open(member) as source, open(TEMP_DIR / zip_flat_name, "wb") as dest:
                                    shutil.copyfileobj(source, dest)
                                pdf_count += 1
                except Exception as e:
                    print(f"⚠️ Failed to process zip {file}: {e}")

    print(f"📊 Summary:")
    print(f"   - PDFs found/extracted: {pdf_count}")
    print(f"   - ZIPs processed: {zip_count}")
    
    if pdf_count == 0:
        print("⚠️ No PDFs found. Aborting cleanup.")
        shutil.rmtree(TEMP_DIR)
        return

    # Final Directory setup
    if TARGET_DIR.exists():
        shutil.rmtree(TARGET_DIR)
    shutil.move(str(TEMP_DIR), str(TARGET_DIR))
    
    # Backup manifest just in case
    manifest_src = DATA_DIR / "download_manifest.json"
    if manifest_src.exists():
        shutil.copy2(manifest_src, ROOT_DIR / "data" / "informatica_docs_manifest.json.bak")
        print(f"💾 Manifest backed up to data/informatica_docs_manifest.json.bak")

    # CLEANUP as requested
    print(f"🧹 Deleting original folders at {DATA_DIR}...")
    try:
        shutil.rmtree(DATA_DIR)
        print(f"✨ Originals deleted. All files consolidated in: {TARGET_DIR}")
    except Exception as e:
        print(f"⚠️ Cleanup of originals failed: {e}")

if __name__ == "__main__":
    consolidate()
