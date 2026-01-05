"""
Valhalla V2 Dual-Mode Dashboard.

Mission Control: Live agent execution with telemetry.
The Hangar: Regression testing and skill editing.
"""

import os
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

import streamlit as st

from src.agents.sanitizer import ALLOWLIST
from src.graph.workflow import run_pipeline
from src.core.evidence_store import EvidenceStore


# Paths
DATA_DIR = Path(__file__).parent / "data"
SKILLS_DIR = Path(__file__).parent / "src" / "skills"
REGRESSION_LOG_PATH = DATA_DIR / "regression_log.json"


# Page configuration
st.set_page_config(
    page_title="Valhalla V2 Dashboard",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .stApp {
        max-width: 1400px;
        margin: 0 auto;
    }
    .telemetry-strip {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        padding: 1rem;
        border-radius: 0.5rem;
        color: white;
        margin-bottom: 1rem;
    }
    .status-green { color: #00ff88; font-weight: bold; }
    .status-red { color: #ff4444; font-weight: bold; }
    .report-block {
        background: #0a0a0f;
        color: #e0e0e0;
        padding: 1.5rem;
        border-radius: 0.5rem;
        border: 1px solid #333;
    }
    .delta-positive { color: #00ff88; }
    .delta-negative { color: #ff4444; }
</style>
""", unsafe_allow_html=True)


# ============================================
# SIDEBAR
# ============================================
with st.sidebar:
    st.image("https://img.icons8.com/color/96/rocket.png", width=80)
    st.title("Valhalla V2")
    st.markdown("---")
    
    # Mode Toggle
    mode = st.radio(
        "Dashboard Mode",
        ["🛰️ Mission Control", "🛠️ The Hangar", "🏗️ System Architecture", "🎯 Polymarket Scanner", "📚 Content Library", "🧠 Advisor Chat", "📋 Planner"],
        index=0
    )
    
    st.markdown("---")
    
    # API Key Status
    st.subheader("🔑 API Status")
    has_google = bool(os.environ.get("GOOGLE_API_KEY"))
    if has_google:
        st.success("✓ Google API Key")
    else:
        st.warning("⚠️ No API key found")
    
    st.markdown("---")
    
    # Allowed Domains
    with st.expander("✅ Allowed Domains"):
        for domain in ALLOWLIST:
            clean_domain = domain.replace("https://", "").rstrip("/")
            st.caption(f"• {clean_domain}")
    
    st.markdown("---")
    st.caption("Valhalla V2 • Agentic RSS Pipeline")


# ============================================
# HELPER FUNCTIONS
# ============================================
def load_regression_log():
    """Load the regression log."""
    if not REGRESSION_LOG_PATH.exists():
        return []
    try:
        with open(REGRESSION_LOG_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def get_last_run_metrics():
    """Get metrics from the last regression run."""
    log = load_regression_log()
    if not log:
        return None
    return log[-1]


def load_skill_content(skill_name: str) -> str:
    """Load skill markdown content."""
    skill_path = SKILLS_DIR / skill_name
    if skill_path.exists():
        return skill_path.read_text()
    return f"Skill not found: {skill_name}"


# ============================================
# MISSION CONTROL VIEW
# ============================================
if mode == "🛰️ Mission Control":
    st.title("🛰️ Mission Control", anchor="top")
    st.markdown("Execute missions and monitor live telemetry.")
    
    st.markdown("---")
    
    # Mission Briefing Input
    st.markdown("### 📋 Mission Briefing")
    st.caption("Define the objective for the autonomous agent swarm.")
    user_query = st.text_area(
        "Describe your mission:",
        placeholder="e.g., Compare AI news coverage from BBC and TechCrunch",
        height=100
    )
    
    col1, col2 = st.columns([1.5, 3.5])
    with col1:
        st.write("") # Spacer
        st.write("") # Spacer
        run_button = st.button("🚀 Execute Mission", type="primary", use_container_width=True)
    
    st.markdown("---")
    
    # Execute Pipeline
    if run_button and user_query:
        with st.spinner("🔄 Mission in progress..."):
            try:
                result = run_pipeline(user_query)
                st.session_state['mission_result'] = result
                st.session_state['mission_success'] = True
            except Exception as e:
                st.session_state['mission_success'] = False
                st.session_state['mission_error'] = str(e)
    
    # Display Results
    if 'mission_result' in st.session_state and st.session_state.get('mission_success'):
        result = st.session_state['mission_result']
        
        # Live Telemetry Strip
        st.subheader("📡 Live Telemetry")
        
        telemetry = result.get('telemetry', {})
        evidence_map = result.get('evidence_map', {})
        circuit_breaker = result.get('circuit_breaker', {})
        
        # Extract values
        if hasattr(circuit_breaker, 'step_count'):
            step_count = circuit_breaker.step_count
        else:
            step_count = circuit_breaker.get('step_count', 0)
        
        alignment = telemetry.get('alignment_score', 0.0)
        evidence_count = len(evidence_map)
        sanitizer_rejects = telemetry.get('sanitizer_reject_count', 0)
        
        # Telemetry Columns (Compact Row)
        st.caption("System Performance Metrics")
        t1, t2, t3, t4 = st.columns(4)
        
        with t1:
            st.metric("🎯 Alignment Score", f"{alignment:.1f}%")
        with t2:
            st.metric("📦 Evidence Count", evidence_count)
        with t3:
            sanitizer_status = "🟢 Secure" if sanitizer_rejects == 0 else f"🔴 {sanitizer_rejects} Rejects"
            st.metric("🛡️ Sanitizer Status", sanitizer_status)
        with t4:
            st.metric("⚙️ Steps Executed", step_count)
        
        st.markdown("---")
        
        # Final Report
        st.subheader("📄 Mission Report")
        
        final_report = result.get('final_report', '')
        structured_report = result.get('structured_report')
        
        if structured_report:
            st.info(f"**Executive Summary:** {structured_report.get('executive_summary', 'N/A')}")
            
            m1, m2 = st.columns(2)
            with m1:
                sentiment = structured_report.get('sentiment_score', 5)
                color = "green" if sentiment >= 7 else "red" if sentiment <= 4 else "orange"
                st.markdown(f"**Sentiment:** :{color}[**{sentiment}/10**]")
            with m2:
                entities = structured_report.get('key_entities', [])
                if entities:
                    st.markdown("**Entities:** " + ", ".join([f"`{e}`" for e in entities]))
        
        # High-contrast report block
        if not final_report and result.get('messages'):
            # Fallback: Extract from last message if explicit report is missing
            # This handles validation failures, groundhog clarifications, and fallback reports
            last_msg = result['messages'][-1]
            final_report = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)

        if final_report:
            if "# Report Generation Failed" in final_report:
                st.error("❌ Mission Failed Validation")
                st.markdown(final_report)
            elif "[[CLARIFICATION_REQUIRED]]" in final_report:
                st.warning("⚠️ Clarification Required")
                st.markdown(final_report)
            else:
                st.markdown(f'<div class="report-block">{final_report}</div>', unsafe_allow_html=True)
        else:
            st.info("No mission report generated.")
    
    elif 'mission_error' in st.session_state and not st.session_state.get('mission_success'):
        # Improved error display
        st.error(f"❌ **Mission Aborted**")
        with st.expander("🔍 content failure details"):
            st.code(st.session_state['mission_error'])


# ============================================
# THE HANGAR VIEW
# ============================================
elif mode == "🛠️ The Hangar":
    st.title("🛠️ The Hangar")
    st.markdown("Regression testing and skill configuration.")
    
    st.markdown("---")
    
    # Regression Suite Section
    st.markdown("## 🧪 Regression Suite")
    
    col1, col2 = st.columns([0.8, 3.2])
    with col1:
        run_regression = st.button("▶️ Run Full Suite", type="primary", use_container_width=True)
    
    if run_regression:
        with st.spinner("Running regression tests..."):
            from src.agents.qa_node import run_all_tests
            qa_results = run_all_tests()
            st.session_state['hangar_qa_results'] = qa_results
    
    if 'hangar_qa_results' in st.session_state:
        qa = st.session_state['hangar_qa_results']
        
        # Summary Metrics
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Total Tests", qa['total'])
        with c2:
            st.metric("Passed", qa['passed'], delta=None)
        with c3:
            st.metric("Failed", qa['failed'], delta=None, delta_color="inverse")
        with c4:
            st.metric("Errors", qa['errors'], delta=None, delta_color="inverse")
            
        st.write("") # Extra spacing

        
        st.markdown("---")
        
        # Delta Comparison
        st.subheader("📊 Delta Analysis")
        
        log = load_regression_log()
        if len(log) >= 2:
            # Compare current to previous
            current = log[-1]
            previous = log[-2] if len(log) > 1 else None
            
            if previous:
                current_telemetry = current.get('telemetry', {})
                previous_telemetry = previous.get('telemetry', {})
                
                d1, d2, d3 = st.columns(3)
                
                with d1:
                    curr_align = current_telemetry.get('alignment_score', 0)
                    prev_align = previous_telemetry.get('alignment_score', 0)
                    delta = curr_align - prev_align
                    st.metric(
                        "Alignment Score",
                        f"{curr_align:.1f}%",
                        delta=f"{delta:+.1f}% since last run"
                    )
                
                with d2:
                    curr_rejects = current_telemetry.get('sanitizer_reject_count', 0)
                    prev_rejects = previous_telemetry.get('sanitizer_reject_count', 0)
                    delta = curr_rejects - prev_rejects
                    st.metric(
                        "Sanitizer Rejects",
                        curr_rejects,
                        delta=f"{delta:+d} since last run",
                        delta_color="inverse"
                    )
                
                with d3:
                    curr_evidence = current.get('evidence_count', 0)
                    prev_evidence = previous.get('evidence_count', 0)
                    delta = curr_evidence - prev_evidence
                    st.metric(
                        "Evidence Count",
                        curr_evidence,
                        delta=f"{delta:+d} since last run"
                    )
        else:
            st.info("Run tests twice to see delta comparison.")
        
        st.markdown("---")
        
        # Individual Test Results
        st.subheader("📋 Test Results")
        
        for r in qa.get('results', []):
            icon = "✅" if r['status'] == 'PASS' else "❌" if r['status'] == 'FAIL' else "⚠️"
            status_color = "green" if r['status'] == 'PASS' else "red" if r['status'] == 'FAIL' else "orange"
            
            with st.expander(f"{icon} **{r['test_id']}**"):
                st.markdown(f"Status: :{status_color}[**{r['status']}**]")
                
                # Result details
                rc1, rc2 = st.columns(2)
                with rc1:
                    st.caption("🔍 Input / Context")
                    st.code(str(r.get('input', 'N/A')), language="text")
                with rc2:
                    st.caption("🤖 Actual Output")
                    st.code(str(r.get('actual', 'N/A')), language="text")
                
                if r.get('expected'):
                    st.caption("🎯 Expected")
                    st.info(str(r.get('expected')))
                
                if r.get('error'):
                    st.error(f"Error: {r['error']}")
                    
                # Raw data toggle
                if st.checkbox("Show raw JSON", key=f"raw_{r['test_id']}"):
                    st.json(r)
    
    st.markdown("---")
    
    # Skill Sandbox Section
    st.markdown("## 📝 Skill Sandbox")
    st.caption("Inspect agent skill manifests. *Editing currently disabled - modify .md files directly.*")
    
    skill_files = list(SKILLS_DIR.glob("*.md")) if SKILLS_DIR.exists() else []
    skill_names = [f.name for f in skill_files]
    
    if skill_names:
        selected_skill = st.selectbox("Select Skill:", skill_names)
        
        if selected_skill:
            skill_content = load_skill_content(selected_skill)
            
            st.text_area(
                "Skill Content (Read-Only):",
                value=skill_content,
                height=400,
                disabled=True
            )
            
            # Future: Add edit capability
            st.caption("💡 Editing coming soon. For now, modify files directly.")
    else:
        st.info("No skill files found in src/skills/")



# ============================================
# SYSTEM ARCHITECTURE VIEW
# ============================================
elif mode == "🏗️ System Architecture":
    st.title("🏗️ System Architecture")
    st.markdown("Live status of the DTL v2.0 Agent Ecosystem.")
    
    st.markdown("---")
    
    # Helper to check files
    def check_status(path_str):
        p = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), path_str)))
        return p.exists()

    # 1. Core Intelligence
    st.header("🧠 Core Intelligence")
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        if check_status("src/agents/strategist.py"):
            st.success("🧠 Strategist")
            st.caption("Planning & Asset Selection")
        else:
            st.error("❌ Strategist Missing")
            
    with c2:
        if check_status("src/agents/researcher.py"):
            st.success("🔍 Researcher")
            st.caption("Evidence Gathering")
        else:
            st.error("❌ Researcher Missing")

    with c3:
        if check_status("src/agents/reporter.py"):
            st.success("📝 Reporter")
            st.caption("Synthesis & Reporting")
        else:
            st.error("❌ Reporter Missing")

    st.markdown('<br>', unsafe_allow_html=True)
    
    # 2. Content & Planning
    st.header("🎯 Content & Planning")
    
    cp1, cp2, cp3 = st.columns(3)
    
    with cp1:
        if check_status("src/agents/curator.py"):
            st.success("🎨 Curator")
            st.caption("Content Ingestion")
        else:
            st.error("❌ Curator Missing")
            
    with cp2:
        if check_status("src/agents/advisor.py"):
            st.success("🧠 Advisor")
            st.caption("Review & Taxonomy")
        else:
            st.error("❌ Advisor Missing")
            
    with cp3:
        if check_status("src/agents/planner.py"):
            st.success("📋 Planner")
            st.caption("Task Management")
        else:
            st.error("❌ Planner Missing")
            
    st.markdown('<br>', unsafe_allow_html=True)
    
    # 3. Utility & Maintenance
    st.header("🛠️ Utility & Maintenance")
    
    u1, u2, u3 = st.columns(3)
    
    with u1:
        if check_status("src/agents/designer.py"):
            st.success("🎨 Designer")
            st.caption("UI/UX Audit")
        else:
            st.error("❌ Designer Missing")
            
    with u2:
        if check_status("src/agents/meta_analyst.py"):
            st.success("🔮 MetaAnalyst")
            st.caption("Self-Improvement Loop")
        else:
            st.error("❌ MetaAnalyst Missing")
            
    with u3:
        if check_status("src/agents/diagnostician.py"):
            st.success("🩺 Diagnostician")
            st.caption("System Health")
        else:
            st.error("❌ Diagnostician Missing")
            
    st.markdown('<hr style="border:1px solid #333;"/>', unsafe_allow_html=True)

    # 4. Data Stores
    st.header("💾 Data Stores")
    
    d1, d2, d3, d4 = st.columns(4)
    
    with d1:
        if check_status("data/content/content.db"):
            st.success("📚 Content Store")
            st.caption("SQLite (Ingested Content)")
        else:
            st.error("❌ Content DB Missing")
            
    with d2:
        if check_status("data/planner_tasks.db"):
            st.success("📋 Task Store")
            st.caption("SQLite (Planner Tasks)")
        else:
            st.error("❌ Task DB Missing")
            
    with d3:
        if check_status("data/run_scores"):
            st.success("🔢 Run Scores")
            st.caption("JSON Store")
        else:
            st.warning("⚠️ Run Scores Missing")
            
    with d4:
        if check_status("data/improvement_packets"):
            st.success("📦 Improvements")
            st.caption("Packet Store")
        else:
            st.warning("⚠️ Improvements Missing")
            
    st.markdown('<hr style="border:1px solid #333;"/>', unsafe_allow_html=True)
    

            

    
    # 4. Governance
    st.header("⚖️ Governance")
    
    g1, g2 = st.columns(2)
    
    with g1:
        if check_status("src/control_plane/human_approval_gate.py"):
            st.success("👮 Human Approval Gate")
            st.caption("CLI-based ACK Enforced")
        else:
            st.error("❌ Human Gate Missing")
            
    with g2:
        st.success("🛑 Patch Policy Strict")
        st.caption("Hash Validation Required")


# ============================================
# POLYMARKET SCANNER VIEW
# ============================================
elif mode == "🎯 Polymarket Scanner":
    st.title("🎯 Polymarket Certainty Scanner")
    st.markdown("Find high-certainty markets approaching resolution for maximum APR trades.")
    
    st.markdown("---")
    
    # Scanner Controls
    st.markdown("### ⚙️ Scanner Settings")
    st.write("") # Spacing
    
    with st.container(border=True):
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            max_hours = st.slider(
                "Max Hours to Resolution",
                min_value=1, max_value=24, value=4
            )
        
        with col2:
            min_certainty = st.slider(
                "Min Certainty %",
                min_value=50, max_value=99, value=95
            )
        
        with col3:
            min_liquidity = st.number_input(
                "Min Liquidity ($)",
                value=100, step=50
            )
            
        # Action Bar
        a1, a2 = st.columns([3, 1])
        with a2:
            auto_refresh = st.checkbox("Auto-refresh (5 min)", value=False)
            if auto_refresh:
                st.caption(f"Last updated: {st.session_state.get('pm_scan_time', 'N/A')}")
        
        with a1:
            if not auto_refresh:
                scan_button = st.button("🔍 Scan Markets", type="primary", use_container_width=True)
            else:
                scan_button = False
                st.info("🔄 Auto-refresh active. Scanning every 5 minutes.")
    
    st.markdown("---")
    
    # Run scan
    if scan_button or auto_refresh:
        with st.spinner("🔄 Scanning Polymarket for opportunities..."):
            try:
                from src.polymarket_scanner import CertaintyScanner
                
                scanner = CertaintyScanner()
                opportunities = scanner.scan(
                    max_hours=float(max_hours),
                    min_certainty=min_certainty / 100.0,
                    min_liquidity=float(min_liquidity)
                )
                st.session_state['pm_opportunities'] = opportunities
                st.session_state['pm_scan_success'] = True
                st.session_state['pm_scan_time'] = st.session_state.get('pm_scan_time', '') or 'just now'
            except Exception as e:
                st.session_state['pm_scan_success'] = False
                st.session_state['pm_scan_error'] = str(e)
    
    # Display results
    if st.session_state.get('pm_scan_success') and 'pm_opportunities' in st.session_state:
        opportunities = st.session_state['pm_opportunities']
        
        # Summary metrics
        st.subheader(f"📊 Found {len(opportunities)} Opportunities")
        
        if opportunities:
            # Summary row
            total_liq = sum(o.liquidity for o in opportunities)
            avg_apr = sum(o.apr_estimate for o in opportunities) / len(opportunities)
            soonest = min(o.hours_remaining for o in opportunities)
            
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("Total Liquidity", f"${total_liq:,.0f}")
            with m2:
                st.metric("Avg APR", f"{avg_apr:,.0f}%")
            with m3:
                st.metric("Soonest Resolution", f"{soonest:.1f}h")
            with m4:
                st.metric("Opportunities", len(opportunities))
            
            st.markdown("---")
            
            # Opportunities table
            for i, opp in enumerate(opportunities, 1):
                # Color-code by urgency
                if opp.hours_remaining < 1:
                    urgency_color = "🔴"
                    urgency_style = "color: #ff4444;"
                elif opp.hours_remaining < 4:
                    urgency_color = "🟡"
                    urgency_style = "color: #ffaa00;"
                else:
                    urgency_color = "🟢"
                    urgency_style = "color: #00ff88;"
                
                with st.expander(f"{urgency_color} **{opp.apr_estimate:,.0f}% APR** | ⏳ {opp.hours_remaining:.1f}h | {opp.question[:60]}..."):
                    col_a, col_b = st.columns([2, 1])
                    
                    with col_a:
                        st.markdown(f"**Question:** {opp.question}")
                        st.markdown(f"**Certainty:** `{opp.certainty_side}` @ **{opp.certainty_pct*100:.1f}%**")
                        st.markdown(f"**Link:** [{opp.event_slug}]({opp.market_url})")
                    
                    with col_b:
                        st.metric("Liquidity", f"${opp.liquidity:,.0f}")
                        st.metric("Hours Left", f"{opp.hours_remaining:.2f}")
                        st.metric("APR", f"{opp.apr_estimate:,.0f}%")
        else:
            st.info("No opportunities found matching your criteria. Try adjusting the filters.")
    
    elif st.session_state.get('pm_scan_error'):
        st.error(f"❌ Scan failed: {st.session_state['pm_scan_error']}")
    else:
        st.info("👆 Click 'Scan Markets' to find opportunities.")
    
    # Auto-refresh
    if auto_refresh:
        import time
        time.sleep(300)  # 5 minutes
        st.rerun()


# ============================================
# CONTENT LIBRARY VIEW
# ============================================
elif mode == "📚 Content Library":
    st.title("📚 Content Library")
    st.markdown("Your curated knowledge base for AI development insights.")
    
    # Initialize store
    from src.content.store import ContentStore
    from src.content.schemas import ContentStatus, ActionType
    
    store = ContentStore()
    
    st.markdown("---")
    
    # Summary Metrics
    counts = store.count_by_status()
    total = sum(counts.values())
    unread = counts.get("unread", 0)
    action_items = store.get_action_items(limit=100)
    
    # Summary Metrics (Reordered: Total -> Read -> Unread -> Action Items)
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("📚 Total Content", total)
    with m2:
        st.metric("✅ Read", counts.get("read", 0))
    with m3:
        st.metric("📬 Unread", unread)
    with m4:
        st.metric("💡 Action Items", len(action_items))
    
    st.markdown("---")
    
    # ============================================
    # ADD CONTENT SECTION
    # ============================================
    st.subheader("➕ Add Content")
    
    with st.expander("Ingest new URL", expanded=False):
        ingest_url = st.text_input("URL to ingest", placeholder="https://example.com/article")
        ingest_tags = st.text_input("Tags (optional)", placeholder="agents, llm, priority")
        
        col1, col2 = st.columns([1.5, 3.5])
        with col2:
            ingest_btn = st.button("🚀 Ingest URL", type="primary", use_container_width=True)
            
        with col1:
             st.caption("Paste a URL to automatically fetch, categorize, and extract action items.")
        
        if ingest_btn and ingest_url:
            with st.spinner("🔄 Fetching and analyzing content..."):
                try:
                    from src.agents.curator import CuratorAgent
                    
                    curator = CuratorAgent(content_store=store)
                    tags = [t.strip() for t in ingest_tags.split(",")] if ingest_tags else []
                    
                    result = curator.process({
                        "url": ingest_url,
                        "manual_tags": tags,
                    })
                    
                    payload = result.payload
                    status = payload.get("status")
                    
                    if status == "ingested":
                        entry = payload["content_entry"]
                        st.success(f"✅ Ingested: {entry['title'][:60]}")
                        st.markdown(f"**Summary:** {entry['summary']}")
                        st.markdown(f"**Categories:** {', '.join(entry['categories'])}")
                        st.markdown(f"**Relevance:** {entry['relevance_score']:.2f}")
                        if entry["action_items"]:
                            st.markdown(f"**Action Items:** {len(entry['action_items'])}")
                        st.rerun()
                    elif status == "duplicate":
                        st.warning(f"⚠️ Already ingested as {payload.get('existing_id')}")
                    else:
                        st.error(f"❌ Error: {payload.get('error', 'Unknown')}")
                except Exception as e:
                    st.error(f"❌ Ingestion failed: {e}")
    
    st.markdown('<br>', unsafe_allow_html=True)
    
    # ============================================
    # BROWSE & SEARCH SECTION
    # ============================================
    st.subheader("🔍 Browse & Search")
    
    # Filters
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        status_filter = st.selectbox(
            "Status",
            ["all", "unread", "read", "implemented", "archived"],
            index=0
        )
    
    with col2:
        # Load taxonomy for categories
        import json
        from pathlib import Path
        taxonomy_path = Path(__file__).parent / "config" / "content_taxonomy.json"
        categories = ["all"]
        if taxonomy_path.exists():
            with open(taxonomy_path) as f:
                tax = json.load(f)
                categories += [c["id"] for c in tax.get("categories", [])]
        
        category_filter = st.selectbox("Category", categories, index=0)
    
    with col3:
        search_query = st.text_input("Search", placeholder="Search content...")
    
    # Get results
    if search_query:
        entries = store.search(search_query, limit=50)
    elif category_filter != "all":
        entries = store.list_by_category(category_filter, limit=50)
    elif status_filter != "all":
        try:
            entries = store.list_by_status(ContentStatus(status_filter), limit=50)
        except ValueError:
            entries = []
    else:
        # Default: show unread first, then recent
        entries = store.list_by_status(ContentStatus.UNREAD, limit=50)
        if len(entries) < 20:
            read_entries = store.list_by_status(ContentStatus.READ, limit=20 - len(entries))
            entries.extend(read_entries)
    
    st.markdown(f"**Showing {len(entries)} items**")
    
    # ============================================
    # CONTENT CARDS
    # ============================================
    for entry in entries:
        # Relevance bar
        rel_pct = int(entry.relevance_score * 100)
        rel_bar = "█" * int(entry.relevance_score * 5) + "░" * (5 - int(entry.relevance_score * 5))
        
        # Status icon
        status_icons = {
            ContentStatus.UNREAD: "📬",
            ContentStatus.READ: "📖",
            ContentStatus.IMPLEMENTED: "✅",
            ContentStatus.ARCHIVED: "📦",
        }
        status_icon = status_icons.get(entry.status, "📄")
        
        with st.expander(f"{status_icon} {entry.title[:70]} ({int(entry.relevance_score * 100)}%)"):
            # Content details
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**Summary:** {entry.summary}")
                with c2:
                    st.progress(entry.relevance_score, text=f"Relevance: {rel_pct}%")
                    st.caption(f"Ingested: {entry.ingested_at[:10]}")
            
            st.markdown(f"🏷️ **Categories:** `{'`, `'.join(entry.categories)}`")
            
            # Action items in this content
            if entry.action_items:
                st.info(f"**💡 {len(entry.action_items)} Action Items Detected**")
                for action in entry.action_items:
                    st.markdown(f"- **[{action.action_type.value.upper()}]** {action.description}")
                    if action.related_files:
                        st.caption(f"  Files: {', '.join(action.related_files)}")
            
            st.markdown("---")
            
            # Action buttons
            btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)
            
            with btn_col1:
                if entry.status == ContentStatus.UNREAD:
                    if st.button("✅ Mark Read", key=f"read_{entry.id}"):
                        store.update_status(entry.id, ContentStatus.READ)
                        st.rerun()
                elif entry.status == ContentStatus.READ:
                    if st.button("📬 Mark Unread", key=f"unread_{entry.id}"):
                        store.update_status(entry.id, ContentStatus.UNREAD)
                        st.rerun()
            
            with btn_col2:
                if entry.status != ContentStatus.ARCHIVED:
                    if st.button("📦 Archive", key=f"archive_{entry.id}"):
                        store.update_status(entry.id, ContentStatus.ARCHIVED)
                        st.rerun()
                else:
                    if st.button("📤 Unarchive", key=f"unarchive_{entry.id}"):
                        store.update_status(entry.id, ContentStatus.UNREAD)
                        st.rerun()
            
            with btn_col3:
                if st.button("🔬 Deep Analysis", key=f"analyze_{entry.id}"):
                    st.session_state[f"analyzing_{entry.id}"] = True
            
            with btn_col4:
                 st.link_button("🔗 Open URL", entry.url, use_container_width=True)
            
            # Deep Analysis execution
            if st.session_state.get(f"analyzing_{entry.id}"):
                with st.spinner("🔬 Running deep analysis with AI..."):
                    try:
                        import google.generativeai as genai
                        import os
                        
                        api_key = os.environ.get("GOOGLE_API_KEY")
                        if not api_key:
                            st.error("GOOGLE_API_KEY not set")
                        else:
                            genai.configure(api_key=api_key)
                            model = genai.GenerativeModel("gemini-2.0-flash")
                            
                            analysis_prompt = f"""Analyze this content in depth for an AI agent development codebase.

TITLE: {entry.title}
URL: {entry.url}
SUMMARY: {entry.summary}
CATEGORIES: {', '.join(entry.categories)}

CONTENT (if available):
{entry.raw_content[:8000] if entry.raw_content else 'Not available'}

---

Provide a deep analysis covering:
1. **Key Insights**: What are the main takeaways?
2. **Applicability**: How does this apply to a multi-agent AI system?
3. **Specific Recommendations**: Concrete changes we could make to our codebase
4. **Implementation Priority**: High/Medium/Low and why
5. **Related Concepts**: What other topics should we research?

Be specific and actionable."""

                            response = model.generate_content(analysis_prompt)
                            st.markdown("### 🔬 Deep Analysis Results")
                            st.markdown(response.text)
                            
                    except Exception as e:
                        st.error(f"Analysis failed: {e}")
                    finally:
                        st.session_state[f"analyzing_{entry.id}"] = False
    
    if not entries:
        st.info("No content found. Add some URLs above!")
    
    st.markdown("---")
    
    # ============================================
    # ACTION ITEMS PANEL
    # ============================================
    st.subheader("💡 Action Items Across All Content")
    
    # Filter by type
    action_type_filter = st.selectbox(
        "Filter by type",
        ["all", "enhancement", "correction", "research", "documentation", "idea"],
        index=0
    )
    
    filtered_type = action_type_filter if action_type_filter != "all" else None
    all_actions = store.get_action_items(action_type=filtered_type, limit=20)
    
    if all_actions:
        for entry, action in all_actions:
            type_colors = {
                ActionType.ENHANCEMENT: "🟢",
                ActionType.CORRECTION: "🔴",
                ActionType.RESEARCH: "🔵",
                ActionType.DOCUMENTATION: "🟡",
                ActionType.IDEA: "🟣",
            }
            type_icon = type_colors.get(action.action_type, "⚪")
            
            with st.container():
                st.markdown(f"{type_icon} **[{action.action_type.value.upper()}]** P{action.priority} - {action.description}")
                st.caption(f"From: {entry.title[:50]} ({entry.id})")
                if action.related_files:
                    st.caption(f"Files: {', '.join(action.related_files)}")
                st.markdown("---")
    else:
        st.info("No action items found.")


# ============================================
# 🧠 ADVISOR CHAT
# ============================================
elif mode == "🧠 Advisor Chat":
    st.title("🧠 Advisor Chat")
    st.caption("AI-powered content review and categorization assistant")
    
    try:
        from src.content.store import ContentStore
        from src.agents.advisor import CuratorAdvisor
        
        content_store = ContentStore()
        
        # Initialize advisor in session state
        if "advisor" not in st.session_state:
            st.session_state.advisor = CuratorAdvisor(content_store=content_store)
        
        if "advisor_chat_history" not in st.session_state:
            st.session_state.advisor_chat_history = []
        
        advisor = st.session_state.advisor
        
        # Get all content for selection
        all_content = content_store.list_entries(limit=50)
        
        if not all_content:
            st.info("📭 No content ingested yet. Use the **Content Library** to ingest URLs first.")
        else:
            # --- Content Selection Card ---
            with st.container(border=True):
                st.markdown("##### 📄 Select Content")
                content_options = {f"{c.title[:60]}..." if len(c.title) > 60 else c.title: c.id for c in all_content}
                selected_label = st.selectbox(
                    "Choose content to review:", 
                    list(content_options.keys()),
                    label_visibility="collapsed"
                )
                selected_id = content_options[selected_label]
                
                # Show content preview
                selected_content = content_store.read(selected_id)
                if selected_content:
                    st.caption(f"🏷️ {', '.join(selected_content.categories[:3])} • 📊 {selected_content.relevance_score:.0%} relevance")
            
            # Action buttons
            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                get_suggestions = st.button("🔍 Get Suggestions", use_container_width=True, type="primary")
            with col2:
                send_to_planner = st.button("📋 Send to Planner", use_container_width=True)
            
            if get_suggestions:
                with st.spinner("🧠 Analyzing content..."):
                    result = advisor._review_content(selected_id)
                    st.session_state.current_suggestions = result
            
            if send_to_planner:
                from src.agents.planner import PlannerAgent
                planner = PlannerAgent(content_store=content_store)
                result = planner._import_content_actions(selected_id)
                if "error" not in result:
                    st.success(f"✅ Created {result.get('tasks_created', 0)} tasks in Planner")
                else:
                    st.error(result["error"])
            
            # Display suggestions
            if "current_suggestions" in st.session_state:
                suggestions = st.session_state.current_suggestions
                
                if "error" in suggestions:
                    st.error(suggestions["error"])
                else:
                    st.markdown("---")
                    
                    sugg_data = suggestions.get("suggestions", {})
                    
                    # --- Category Suggestions Card ---
                    if "category_suggestions" in sugg_data and sugg_data["category_suggestions"]:
                        with st.container(border=True):
                            st.markdown("##### 🏷️ Category Suggestions")
                            for cs in sugg_data["category_suggestions"]:
                                col1, col2, col3 = st.columns([4, 1, 1])
                                with col1:
                                    current = cs.get('current', 'None')
                                    suggested = cs.get('suggested', 'N/A')
                                    st.markdown(f"**{current}** → {st.session_state.get('advisor_suggestion_highlight', '')} :blue-background[**{suggested}**]")
                                    st.caption(f"💡 {cs.get('reasoning', '')}")
                                with col2:
                                    if st.button("✅", key=f"cat_accept_{cs.get('suggested')}", help="Accept"):
                                        advisor._learn_from_feedback({
                                            "content_id": selected_id,
                                            "type": "category",
                                            "suggested": cs.get("suggested"),
                                            "accepted": True,
                                        })
                                        st.toast("✅ Learned preference!")
                                        st.rerun()  # Rerun to update state
                                with col3:
                                    if st.button("❌", key=f"cat_reject_{cs.get('suggested')}", help="Reject"):
                                        advisor._learn_from_feedback({
                                            "content_id": selected_id,
                                            "type": "category",
                                            "suggested": cs.get("suggested"),
                                            "accepted": False,
                                        })
                                        st.toast("📝 Noted")
                    
                    # --- Action Suggestions Card ---
                    if "action_suggestions" in sugg_data and sugg_data["action_suggestions"]:
                        with st.container(border=True):
                            st.markdown("##### ⚡ Suggested Actions")
                            
                            for idx, action in enumerate(sugg_data["action_suggestions"]):
                                priority = action.get('priority', 3)
                                # Priority badges
                                badge = {1: "🔴", 2: "🟠", 3: "🟡", 4: "🟢", 5: "⚪"}.get(priority, "⚪")
                                
                                # Layout: Priority select first, then details
                                col_prio, col_desc, col_act = st.columns([1, 4, 1])
                                
                                with col_prio:
                                    new_priority = st.selectbox(
                                        "Priority",
                                        [1, 2, 3, 4, 5],
                                        index=priority - 1,
                                        key=f"action_prio_{idx}_{action.get('description', '')[:10]}",
                                        label_visibility="collapsed"
                                    )
                                    
                                with col_desc:
                                    st.markdown(f"{badge} **{action.get('description', '')}**")
                                    st.caption(f"💡 {action.get('reasoning', '')}")
                                
                                with col_act:
                                    if st.button("➕", key=f"action_accept_{idx}_{action.get('description', '')[:10]}", help="Add to Planner"):
                                        from src.agents.planner import PlannerAgent
                                        planner = PlannerAgent(content_store=content_store)
                                        result = planner._create_task({
                                            "description": action.get('description', ''),
                                            "priority": new_priority,
                                            "source_type": "content",
                                            "source_id": selected_id,
                                            "notes": f"From Advisor: {action.get('reasoning', '')}",
                                        })
                                        if "error" not in result:
                                            # Improved success feedback
                                            task_id = result.get('task', {}).get('id', '')
                                            st.success(f"✅ Task created: {task_id}")
                                        else:
                                            st.error(result["error"])
                                
                                if idx < len(sugg_data["action_suggestions"]) - 1:
                                    st.divider()
                    
                    # --- Priority Suggestion ---
                    if "priority_suggestion" in sugg_data:
                        ps = sugg_data["priority_suggestion"]
                        st.markdown(f"**Priority:** {ps.get('current', 'N/A')} → **{ps.get('suggested', 'N/A')}**")
                        st.caption(ps.get("reasoning", ""))
            
            st.markdown("---")
            
            # --- Chat Interface Card ---
            with st.container(border=True):
                col_title, col_clear = st.columns([4, 1])
                with col_title:
                    st.markdown("##### 💬 Chat with Advisor")
                with col_clear:
                    if st.button("🗑️ Clear", help="Clear chat history"):
                        st.session_state.advisor_chat_history = []
                        st.rerun()
                
                # Display chat history with bubbles
                chat_container = st.container(height=300)
                with chat_container:
                    if not st.session_state.advisor_chat_history:
                        st.caption("Ask questions about this content...")
                    else:
                        for msg in st.session_state.advisor_chat_history[-10:]:
                            if msg["role"] == "user":
                                with st.chat_message("user"):
                                    st.write(msg['content'])
                            else:
                                with st.chat_message("assistant", avatar="🧠"):
                                    st.write(msg['content'])
            
            # Chat input (outside the scrollable container)
            user_message = st.chat_input("Ask about this content...")
            if user_message:
                with st.spinner("🧠 Thinking..."):
                    result = advisor._chat_response(selected_id, user_message)
                    
                    st.session_state.advisor_chat_history.append({
                        "role": "user",
                        "content": user_message,
                    })
                    
                    if "error" not in result:
                        st.session_state.advisor_chat_history.append({
                            "role": "advisor",
                            "content": result.get("advisor_response", ""),
                        })
                    else:
                        st.error(result["error"])
                    
                    st.rerun()
            
            # --- Learning Stats (Side Panel Style) ---
            st.markdown("---")
            stats = advisor.get_memory_stats()
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📊 Feedback", stats["total_feedback"])
            with col2:
                st.metric("🏷️ Categories", stats["categories_learned"])
            with col3:
                st.metric("🔄 Patterns", stats.get("patterns_learned", 0))
    
    except ImportError as e:
        st.error(f"Import error: {e}")
    except Exception as e:
        st.error(f"Error: {e}")


# ============================================
# 📋 PLANNER
# ============================================
elif mode == "📋 Planner":
    st.title("📋 Planner")
    st.caption("Prioritized task management across content and system")
    
    try:
        from src.content.store import ContentStore
        from src.agents.planner import PlannerAgent, TaskStatus
        
        content_store = ContentStore()
        planner = PlannerAgent(content_store=content_store)
        
        # Quick stats
        stats = planner.get_stats()
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Tasks", stats["total_tasks"])
        with col2:
            st.metric("To Do", stats["by_status"].get("todo", 0))
        with col3:
            st.metric("In Progress", stats["by_status"].get("in_progress", 0))
        with col4:
            st.metric("Done", stats["by_status"].get("done", 0))
        
        st.markdown("---")
        
        # Filters and actions
        with st.expander("🔎 Filters & Utilities", expanded=True):
            f1, f2, f3 = st.columns([1, 1, 1])
            with f1:
                status_filter = st.selectbox("Status", ["All", "todo", "in_progress", "done", "archived"])
            with f2:
                source_filter = st.selectbox("Source", ["All", "content", "system", "manual"])
            with f3:
                # Import utility
                if st.button("📥 Import System Backlog", use_container_width=True):
                    result = planner._import_system_backlog()
                    if "error" not in result:
                        st.success(f"✓ Imported {result.get('tasks_created', 0)} tasks")
                    else:
                        st.error(result["error"])

        # Add Task Popover
        with st.popover("➕ Add Manual Task", use_container_width=True):
             with st.form("add_task_form"):
                st.subheader("Add New Task")
                task_desc = st.text_area("Description")
                task_priority = st.slider("Priority", 1, 5, 3)
                task_due = st.date_input("Due Date (optional)")
                
                if st.form_submit_button("Create Task"):
                     result = planner._create_task({
                        "description": task_desc,
                        "priority": task_priority,
                        "due_date": str(task_due) if task_due else None,
                        "source_type": "manual",
                     })
                     if "error" not in result:
                        st.success(f"✓ Created {result.get('task', {}).get('id', 'task')}")
                        st.rerun()
                     else:
                        st.error(result["error"])
        
        # Add task form
        st.markdown("")  # Spacing
        
        st.markdown("---")
        
        # Get tasks
        filters = {}
        if status_filter != "All":
            filters["status"] = status_filter
        if source_filter != "All":
            filters["source_type"] = source_filter
        
        result = planner._list_tasks(filters)
        tasks = result.get("tasks", [])
        
        # Group by priority
        priority_groups = {1: [], 2: [], 3: [], 4: [], 5: []}
        for task in tasks:
            p = task.get("priority", 3)
            if p in priority_groups:
                priority_groups[p].append(task)
        
        priority_labels = {
            1: "🔴 P1 - Critical",
            2: "🟠 P2 - High",
            3: "🟡 P3 - Medium",
            4: "🟢 P4 - Low",
            5: "⚪ P5 - Minimal",
        }
        
        for priority, group in priority_groups.items():
            if group:
                st.subheader(priority_labels[priority])
                
                for task in group:
                    with st.container(border=True):
                        col1, col2, col3 = st.columns([4, 1.2, 0.5])
                        
                        with col1:
                            # Status indicator helper within card
                            card_color = {1: "red", 2: "orange", 3: "yellow", 4: "green", 5: "grey"}[priority]
                            
                            st.markdown(f"**:{card_color}[{task.get('description', '')}]**")
                            
                            notes_col, meta_col = st.columns(2)
                            with notes_col:
                                if task.get("notes"):
                                    st.caption(f"📝 {task.get('notes')}")
                            
                            with meta_col:
                                source_text = {
                                    "content": f"📚 Content: {task.get('source_id')}",
                                    "system": f"⚙️ System: {task.get('source_id')}",
                                    "manual": "✏️ Manual task"
                                }.get(task.get("source_type"), "Task")
                                st.caption(source_text)
                                if task.get("due_date"):
                                    st.caption(f"📅 Due: {task.get('due_date')}")
                        
                        with col2:
                            current_status = task.get("status", "todo")
                            options = ["todo", "in_progress", "done"]
                            if current_status not in options:
                                options.append(current_status)
                            
                            new_status = st.selectbox(
                                "Status",
                                options,
                                index=options.index(current_status),
                                key=f"status_{task.get('id')}",
                                label_visibility="collapsed"
                            )
                            if new_status != current_status:
                                planner._update_task(task.get("id"), {"status": new_status})
                                st.rerun()
                        
                        with col3:
                            if st.button("🗑️", key=f"archive_{task.get('id')}"):
                                planner._update_task(task.get("id"), {"status": "archived"})
                                st.rerun()
        
        if not tasks:
            st.info("No tasks found. Import from content or system backlog, or add manually.")
    
    except ImportError as e:
        st.error(f"Import error: {e}")
    except Exception as e:
        st.error(f"Error: {e}")


# Footer
st.markdown("---")
st.caption("Valhalla V2 Dashboard • Built with Streamlit • Powered by LangGraph")

