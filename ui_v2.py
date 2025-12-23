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
        ["🛰️ Mission Control", "🛠️ The Hangar"],
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
    st.title("🛰️ Mission Control")
    st.markdown("Execute missions and monitor live telemetry.")
    
    st.markdown("---")
    
    # Mission Briefing Input
    st.subheader("📋 Mission Briefing")
    user_query = st.text_area(
        "Describe your mission:",
        placeholder="e.g., Compare AI news coverage from BBC and TechCrunch",
        height=100
    )
    
    col1, col2 = st.columns([1, 4])
    with col1:
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
        
        # Telemetry Columns
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
        if final_report:
            st.markdown(f'<div class="report-block">{final_report}</div>', unsafe_allow_html=True)
        else:
            st.info("No mission report generated.")
    
    elif 'mission_error' in st.session_state and not st.session_state.get('mission_success'):
        st.error(f"❌ Mission failed: {st.session_state['mission_error']}")


# ============================================
# THE HANGAR VIEW
# ============================================
elif mode == "🛠️ The Hangar":
    st.title("🛠️ The Hangar")
    st.markdown("Regression testing and skill configuration.")
    
    st.markdown("---")
    
    # Regression Suite Section
    st.subheader("🧪 Regression Suite")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        run_regression = st.button("🧪 Run Full Regression Suite", type="primary", use_container_width=True)
    
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
            with st.expander(f"{icon} {r['test_id']}: {r['status']}"):
                st.json(r)
    
    st.markdown("---")
    
    # Skill Sandbox Section
    st.subheader("📝 Skill Sandbox")
    
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


# Footer
st.markdown("---")
st.caption("Valhalla V2 Dashboard • Built with Streamlit • Powered by LangGraph")
