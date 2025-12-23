"""
Streamlit Dashboard for the Agentic RSS Analyst.

This UI provides a web interface for running the RSS-to-Summary pipeline.
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

import streamlit as st

from src.agents.sanitizer import ALLOWLIST
from src.graph.workflow import run_pipeline
from src.core.evidence_store import EvidenceStore


# Page configuration
st.set_page_config(
    page_title="Agentic RSS Analyst v1",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 0.5rem;
        color: white;
        text-align: center;
    }
    .evidence-item {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 0.5rem;
        border-left: 4px solid #667eea;
    }
</style>
""", unsafe_allow_html=True)

# ============================================
# SIDEBAR
# ============================================
with st.sidebar:
    st.image("https://img.icons8.com/color/96/rss.png", width=80)
    st.title("📰 RSS Analyst")
    st.markdown("---")
    
    # API Key Status
    st.subheader("🔑 API Status")
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_google = bool(os.environ.get("GOOGLE_API_KEY"))
    
    if has_openai:
        st.success("✓ OpenAI API Key")
    elif has_anthropic:
        st.success("✓ Anthropic API Key")
    elif has_google:
        st.success("✓ Google API Key")
    else:
        st.warning("⚠️ No API key found")
        st.caption("Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_API_KEY")
    
    st.markdown("---")
    
    # Allowed Domains
    st.subheader("✅ Allowed Domains")
    for domain in ALLOWLIST:
        # Clean up for display
        clean_domain = domain.replace("https://", "").rstrip("/")
        st.markdown(f"• `{clean_domain}`")
    
    st.markdown("---")
    
    # Cache Clear Button
    if st.button("🗑️ Clear Cache", use_container_width=True):
        for key in ['last_result', 'test_result', 'result', 'qa_results']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()
    
    st.markdown("---")
    
    # Test Suite Launcher
    st.subheader("🧪 Test Suite")
    
    # Load test cases from YAML
    import yaml
    from pathlib import Path
    test_suite_path = Path(__file__).parent / "data" / "test_suite.yaml"
    
    test_options = {}
    if test_suite_path.exists():
        with open(test_suite_path, "r") as f:
            suite_data = yaml.safe_load(f)
            for t in suite_data.get("tests", []):
                test_options[t["test_id"]] = t
    
    if test_options:
        selected_test = st.selectbox(
            "Select Test:",
            list(test_options.keys()),
            format_func=lambda x: f"{x}: {test_options[x].get('description', '')[:40]}..."
        )
        
        if st.button("🚀 Launch Test Mission", use_container_width=True):
            test_case = test_options[selected_test]
            with st.spinner(f"Running {selected_test}..."):
                try:
                    result = run_pipeline(test_case["query"])
                    st.session_state['test_result'] = result
                    st.session_state['test_id'] = selected_test
                    st.session_state['test_success'] = True
                except Exception as e:
                    st.session_state['test_success'] = False
                    st.session_state['test_error'] = str(e)
        
        # Display test telemetry
        if 'test_result' in st.session_state and st.session_state.get('test_success'):
            tr = st.session_state['test_result']
            telemetry = tr.get('telemetry', {})
            cb = tr.get('circuit_breaker', {})
            
            step_count = cb.step_count if hasattr(cb, 'step_count') else cb.get('step_count', 0)
            rejects = telemetry.get('sanitizer_reject_count', 0)
            alignment = telemetry.get('alignment_score', 0.0)
            
            st.success(f"✅ {st.session_state.get('test_id', 'Test')} Complete")
            st.caption(f"Steps: {step_count} | Rejects: {rejects} | Align: {alignment:.1f}")
        elif st.session_state.get('test_error'):
            st.error(f"❌ {st.session_state.get('test_error', 'Unknown error')}")
    else:
        st.info("No test suite found.")
    
    st.markdown("---")
    
    # Full Regression Suite
    if st.button("Run Full Regression", use_container_width=True):
        with st.spinner("Running all tests..."):
            from src.agents.qa_node import run_all_tests
            qa_results = run_all_tests()
            st.session_state['qa_results'] = qa_results
    
    if 'qa_results' in st.session_state:
        qa = st.session_state['qa_results']
        st.markdown(f"**Total:** {qa['total']} | **Pass:** {qa['passed']} | **Fail:** {qa['failed']}")
    
    st.markdown("---")
    
    # System Vitals (Live Telemetry)
    st.subheader("📊 System Vitals")
    
    # Check if we have mission results
    result_source = None
    if 'last_result' in st.session_state:
        result_source = st.session_state['last_result']
    elif 'test_result' in st.session_state:
        result_source = st.session_state['test_result']
    
    if result_source:
        telemetry = result_source.get('telemetry', {})
        circuit_breaker = result_source.get('circuit_breaker', {})
        
        # Extract metrics
        alignment = telemetry.get('alignment_score', 100.0)
        noise_ratio = telemetry.get('noise_ratio', 0.0)
        
        if hasattr(circuit_breaker, 'step_count'):
            step_count = circuit_breaker.step_count
        else:
            step_count = circuit_breaker.get('step_count', 0) if circuit_breaker else 0
        
        # Agent Health Gauge
        if alignment > 80:
            health_color = "🟢"
            health_status = "Healthy"
        elif alignment > 50:
            health_color = "🟡"
            health_status = "Degraded"
        else:
            health_color = "🔴"
            health_status = "Critical"
        
        st.markdown(f"**Agent Health:** {health_color} {health_status}")
        st.progress(min(alignment / 100, 1.0))
        st.caption(f"Alignment: {alignment:.1f}%")
        
        # Data Signal (Noise Ratio) - Cap at 100% for display
        display_noise = min(noise_ratio, 100.0)
        st.markdown("**Data Signal:**")
        st.progress(min(display_noise / 100, 1.0))
        st.caption(f"Signal Density: {display_noise:.1f}%")
        
        # Token Efficiency
        st.markdown(f"**Token Efficiency:**")
        st.caption(f"Steps: {step_count} | Rejects: {telemetry.get('sanitizer_reject_count', 0)}")
        
        # Debug Inspector
        with st.expander("🔍 Telemetry Debug"):
            st.json(telemetry)
            st.write(f"Raw Noise Ratio: {noise_ratio}")
    else:
        st.caption("Run a mission to see vitals.")
    
    st.markdown("---")
    st.caption("Agentic RSS Analyst v2.0")

# ============================================
# MAIN CONTENT
# ============================================
st.title("🤖 Agentic RSS Analyst v1")
st.markdown("""
Enter a query to fetch and summarize news from allowed RSS feeds.
The agent will plan actions, validate them, execute, and generate a report.
""")

st.markdown("---")

# Query Input
col1, col2 = st.columns([4, 1])

with col1:
    user_query = st.text_input(
        "🔍 Enter your query",
        placeholder="e.g., Summarize the latest tech news from TechCrunch",
        help="Describe what news you want to fetch and summarize"
    )

with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    run_button = st.button("▶️ Run Agent", type="primary", use_container_width=True)

# Example queries
with st.expander("💡 Example Queries"):
    st.markdown("""
    - *"Summarize the latest world news from BBC"*
    - *"Get top headlines from NYTimes"*
    - *"What's happening in tech according to TechCrunch?"*
    - *"Fetch Reuters world news"*
    """)

st.markdown("---")

# ============================================
# EXECUTION
# ============================================
if run_button and user_query:
    # Step Visualizer using st.status
    with st.status("🔄 Agent Timeline", expanded=True) as status:
        try:
            status.update(label="🧠 Thinker: Analyzing query...")
            
            # Run the pipeline
            result = run_pipeline(user_query)
            
            # Update status based on result
            step_count = 0
            if result.get('circuit_breaker'):
                cb = result['circuit_breaker']
                step_count = cb.step_count if hasattr(cb, 'step_count') else cb.get('step_count', 0)
            
            status.update(label=f"✅ Mission Complete ({step_count} steps)")
            
            # Display step trace
            st.write("**Step Trace:**")
            st.write(f"1. 🧠 Thinker → Plan generated")
            st.write(f"2. 🛡️ Sanitizer → Plan validated")
            st.write(f"3. ⚙️ Executor → {step_count} actions executed")
            st.write(f"4. 📄 Reporter → Report generated")
            
            # Store in session state for display and System Vitals
            st.session_state['result'] = result
            st.session_state['last_result'] = result  # For System Vitals sidebar
            st.session_state['success'] = True
            st.session_state['error'] = None
            
        except Exception as e:
            status.update(label="❌ Mission Failed", state="error")
            st.session_state['success'] = False
            st.session_state['error'] = str(e)
            st.session_state['result'] = None

# ============================================
# RESULTS DISPLAY
# ============================================
if 'result' in st.session_state and st.session_state.get('success'):
    result = st.session_state['result']
    
    # Metrics Row
    st.subheader("📊 Execution Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # Extract metrics safely
    circuit_breaker = result.get('circuit_breaker', {})
    if hasattr(circuit_breaker, 'step_count'):
        step_count = circuit_breaker.step_count
        retry_count = circuit_breaker.retry_count
        max_steps = circuit_breaker.max_steps
    else:
        step_count = circuit_breaker.get('step_count', 0)
        retry_count = circuit_breaker.get('retry_count', 0)
        max_steps = circuit_breaker.get('max_steps', 50)
    
    evidence_map = result.get('evidence_map', {})
    messages = result.get('messages', [])
    
    with col1:
        st.metric("Steps Executed", step_count)
    with col2:
        st.metric("Retries", retry_count)
    with col3:
        st.metric("Evidence Items", len(evidence_map))
    with col4:
        st.metric("Messages", len(messages))
    
    # Efficacy Spine
    st.markdown("##### 🧬 Efficacy Spine")
    c1, c2, c3, c4 = st.columns(4)
    telemetry = result.get('telemetry', {})
    
    with c1:
        score = telemetry.get('alignment_score', 0.0)
        st.metric("Alignment Score", f"{score:.1f}")
    with c2:
        wasted = telemetry.get('wasted_tokens', 0)
        st.metric("Wasted Tokens", f"{wasted}")
    with c3:
        # Calculate Noise Ratio dynamically if not in telemetry
        fetched = len(evidence_map)
        cited = 0
        if result.get('structured_report'):
            cited = len(result.get('structured_report', {}).get('source_ids', []))
        
        noise_ratio = telemetry.get('noise_ratio')
        if noise_ratio is None:
             noise_ratio = 1.0 - (cited / fetched) if fetched > 0 else 0.0
        
        st.metric("Noise Ratio", f"{noise_ratio:.1f}%")
    with c4:
        # Placeholder or other metric
        sanitizer_rejects = telemetry.get("sanitizer_reject_count", 0)
        st.metric("Sanitizer Rejects", sanitizer_rejects)
    
    st.markdown("---")
    
    # Final Report
    st.subheader("📝 Final Report")
    
    structured_report = result.get('structured_report')
    final_report = result.get('final_report', '')
    
    if structured_report:
        # 1. Executive Summary in a highlight box
        st.info(f"**Executive Summary:** {structured_report.get('executive_summary', 'N/A')}")
        
        # 2. Key Entities & Sentiment
        m1, m2 = st.columns(2)
        with m1:
            sentiment = structured_report.get('sentiment_score', 5)
            # Color logic for sentiment
            color = "green" if sentiment >= 7 else "red" if sentiment <= 4 else "orange"
            st.markdown(f"**Sentiment Score:** :{color}[**{sentiment}/10**]")
            st.progress(sentiment / 10)
            
        with m2:
            entities = structured_report.get('key_entities', [])
            st.markdown("**Key Entities:**")
            if entities:
                # Display as pills/tags
                st.markdown(" ".join([f"`{e}`" for e in entities]))
            else:
                st.caption("None identified")
        
        st.markdown("---")
        
        # 3. Source Citations
        source_ids = structured_report.get('source_ids', [])
        if source_ids:
            st.markdown("**📚 Sources Used:**")
            evidence_store = EvidenceStore()
            for sid in source_ids:
                # Resolve title from evidence store
                # Note: This requires evidence to be persisted or accessible
                # For now, we try to find it in the evidence_map if available
                meta = result.get('evidence_map', {}).get(sid, {})
                source_url = meta.get('source_url', sid)
                st.caption(f"- `{sid}` ({source_url})")
        
        st.markdown("---")
        
    # Render Markdown Body
    if final_report:
        st.markdown(final_report)
    else:
        # Try to get from last message (legacy fallback)
        if messages:
            last_msg = messages[-1]
            if hasattr(last_msg, 'content'):
                st.markdown(last_msg.content)
            else:
                st.info("No final report generated.")
        else:
            st.info("No final report generated.")
    
    st.markdown("---")
    
    # Evidence Map
    st.subheader("🗂️ Evidence Collected")
    
    if evidence_map:
        evidence_store = EvidenceStore()
        
        for eid, metadata in evidence_map.items():
            with st.expander(f"📄 {eid}", expanded=False):
                # Get the payload
                payload = evidence_store.get(eid)
                
                if payload:
                    st.markdown(f"**Title:** {payload.get('title', 'N/A')}")
                    
                    link = payload.get('link', '')
                    if link:
                        st.markdown(f"**Link:** [{link}]({link})")
                    
                    summary = payload.get('summary', '')
                    if summary:
                        st.markdown(f"**Summary:** {summary[:300]}...")
                    
                    st.markdown(f"**Published:** {payload.get('published', 'N/A')}")
                
                st.json(metadata)
    else:
        st.info("No evidence collected during this run.")
    
    st.markdown("---")
    
    # Message History
    with st.expander("💬 Agent Message History", expanded=False):
        for i, msg in enumerate(messages):
            role = type(msg).__name__.replace("Message", "")
            content = msg.content if hasattr(msg, 'content') else str(msg)
            
            if role == "Human":
                st.markdown(f"**👤 User:** {content}")
            else:
                st.markdown(f"**🤖 Agent:** {content}")
            
            if i < len(messages) - 1:
                st.markdown("---")

elif 'error' in st.session_state and st.session_state.get('error'):
    st.error(f"❌ Pipeline failed: {st.session_state['error']}")
    
    with st.expander("🔧 Troubleshooting"):
        st.markdown("""
        **Common issues:**
        1. No API key set - export `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GOOGLE_API_KEY`
        2. Invalid URL - make sure the query references an allowed domain
        3. Network error - check your internet connection
        """)

# Footer
st.markdown("---")
st.caption("Built with Streamlit • Powered by LangGraph • 🚀")
