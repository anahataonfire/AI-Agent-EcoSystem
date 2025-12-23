
import os
import sys
import json
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.graph.workflow import run_pipeline
from src.core.evidence_store import EvidenceStore

load_dotenv()

def run_stress_test():
    query = "Fetch the top 3 tech stories from TechCrunch (https://techcrunch.com/feed/) AND the top 3 from BBC Technology (http://feeds.bbci.co.uk/news/technology/rss.xml). Compare them. Identify if any company is mentioned in both. Provide one structured report with Source IDs for both feeds."
    
    print(f"🚀 Executing Mission: {query}")
    final_state = run_pipeline(query)
    
    print("\n--- 🔍 FORENSIC AUDIT ---\n")
    
    # 1. Context Pruning Check
    messages = final_state.get("messages", [])
    msg_count = len(messages)
    pruning_status = "Active" if msg_count < 8 else "Inactive/Failed"
    print(f"Message Count: {msg_count}")
    print(f"Memory Pruning: {pruning_status}")
    
    # 2. Synthesis Check (Sources)
    structured = final_state.get("structured_report", {})
    if not structured:
        print("Structured Report: MISSING")
        return

    source_ids = structured.get("source_ids", [])
    evidence_map = final_state.get("evidence_map", {})
    
    domains_found = set()
    for sid in source_ids:
        meta = evidence_map.get(sid, {})
        url = meta.get("source_url", "")
        if "techcrunch.com" in url:
            domains_found.add("techcrunch")
        elif "bbc.co.uk" in url:
            domains_found.add("bbc")
            
    multi_source_linkage = "SUCCESS" if len(domains_found) >= 2 else "FAIL"
    print(f"Sources Cited: {len(source_ids)}")
    print(f"Source IDs: {source_ids}")
    
    for sid in source_ids:
        meta = evidence_map.get(sid, {})
        print(f"  - ID: {sid}, URL: {meta.get('source_url', 'N/A')}")
        
    for sid in source_ids:
        meta = evidence_map.get(sid, {})
        url = meta.get("source_url", "")
        if "techcrunch.com" in url:
            domains_found.add("techcrunch")
        elif "bbc.co.uk" in url:
            domains_found.add("bbc")
    
    # 3. Grounding Check (Entities)
    entities = structured.get("key_entities", [])
    store = EvidenceStore()
    
    verified_entities = []
    hallucin_entities = []
    
    # Concatenate all raw text for checking
    all_text = ""
    for eid in source_ids:
        payload = store.get(eid)
        if payload:
            all_text += payload.get("title", "") + " " + payload.get("summary", "") + " "
    
    all_text_lower = all_text.lower()
    
    for entity in entities:
        if entity.lower() in all_text_lower:
            verified_entities.append(entity)
        else:
            hallucin_entities.append(entity)
            
    entity_accuracy = "Verified" if not hallucin_entities else f"Ambiguous ({len(hallucin_entities)} unverified)"
    
    print(f"Entities Found: {len(entities)}")
    if hallucin_entities:
        print(f"Unverified Entities: {hallucin_entities}")
    print(f"Entity Extraction Accuracy: {entity_accuracy}")
    
    # 4. Step Count
    cb = final_state.get("circuit_breaker")
    step_count = cb.step_count if cb else "N/A"
    print(f"Step Count: {step_count}")
    
    print("\n--- 🏁 AUDIT SUMMARY ---\n")
    print(f"Multi-Source Linkage: {multi_source_linkage}")
    print(f"Memory Pruning: {pruning_status} ({msg_count} msgs)")
    print(f"Entity Extraction Accuracy: {entity_accuracy}")
    print(f"Step Count: {step_count}")

if __name__ == "__main__":
    run_stress_test()
