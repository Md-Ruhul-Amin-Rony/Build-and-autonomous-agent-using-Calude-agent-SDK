"""
Production-Ready Web Interface for Autonomous Research Agent

Features:
  - Left sidebar: new research form + session history
  - Main area: real-time agent output + report viewer + PDF browser
  - Per-session folder structure with dedicated papers
  - Elegant, intuitive UI with streaming output
"""

import asyncio
import json
from pathlib import Path

import streamlit as st
from research_agent import (
    ResearchGoal,
    create_research_session,
    load_all_sessions,
    run_autonomous_agent,
)

# ─────────────────────────────────────────────────────────────────────────
# Page configuration
# ─────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Research Agent",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for elegant styling
st.markdown(
    """
    <style>
    .main-container {
        max-width: 1400px;
        margin: 0 auto;
    }
    .session-card {
        padding: 15px;
        border-radius: 8px;
        background-color: #f0f2f6;
        margin: 10px 0;
        cursor: pointer;
        transition: 0.2s;
    }
    .session-card:hover {
        background-color: #e0e2e6;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .status-running {
        color: #ff9800;
        font-weight: bold;
    }
    .status-complete {
        color: #4caf50;
        font-weight: bold;
    }
    .output-container {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #2196f3;
        margin: 15px 0;
        font-family: 'Courier New', monospace;
        max-height: 600px;
        overflow-y: auto;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────────
# Session state management
# ─────────────────────────────────────────────────────────────────────────

if "current_session" not in st.session_state:
    st.session_state.current_session = None
if "research_running" not in st.session_state:
    st.session_state.research_running = False
if "output_buffer" not in st.session_state:
    st.session_state.output_buffer = []
if "selected_pdf" not in st.session_state:
    st.session_state.selected_pdf = None


# ─────────────────────────────────────────────────────────────────────────
# Sidebar: New Research Form + Session History
# ─────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🔬 Research Agent")
    st.divider()

    # ── New Research Form ──────────────────────────────────────────────
    with st.form("new_research_form", border=True):
        st.subheader("Start New Research")

        topic = st.text_input(
            "Research Topic",
            placeholder="e.g., Quantum Computing",
            help="The main subject of your research",
        )

        question = st.text_area(
            "Research Question",
            placeholder="What specific aspect do you want to explore?",
            height=80,
            help="The core question your research should answer",
        )

        focus_areas = st.text_area(
            "Focus Areas (one per line)",
            placeholder="Area 1\nArea 2\nArea 3",
            height=100,
            help="Key topics the agent should explore",
        )

        depth = st.selectbox(
            "Research Depth",
            ["overview", "comprehensive", "deep-dive"],
            help="How thorough should the research be?",
        )

        min_sources = st.slider(
            "Minimum Sources",
            min_value=3,
            max_value=15,
            value=6,
            help="Minimum number of sources to find",
        )

        submitted = st.form_submit_button("🚀 Start Research", use_container_width=True)

        if submitted:
            if not topic or not question:
                st.error("Please fill in topic and question")
            else:
                # Create research goal
                focus_list = [f.strip() for f in focus_areas.split("\n") if f.strip()]

                goal = ResearchGoal(
                    topic=topic,
                    question=question,
                    focus_areas=focus_list,
                    depth=depth,
                    min_sources=min_sources,
                    output_format="comprehensive research report with findings and sources",
                )

                # Create session
                session_dir = create_research_session(goal)
                st.session_state.current_session = {
                    "goal": goal,
                    "session_dir": session_dir,
                }
                st.session_state.research_running = True
                st.session_state.output_buffer = []
                st.rerun()

    st.divider()

    # ── Session History ────────────────────────────────────────────────
    st.subheader("📋 Past Sessions")

    sessions = load_all_sessions()
    if sessions:
        for session in sessions:
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])

                with col1:
                    st.markdown(f"**{session['topic']}**")
                    st.caption(f"📅 {session['created_at'][:10]}")
                    st.caption(
                        f"📄 {session['paper_count']} papers · "
                        f"📚 {session['source_count']} sources"
                    )

                with col2:
                    status_class = (
                        "status-complete"
                        if session["status"] == "complete"
                        else "status-running"
                    )
                    st.markdown(
                        f"<span class='{status_class}'>{session['status']}</span>",
                        unsafe_allow_html=True,
                    )

                # Click to load session
                if st.button("📂 View", key=f"load_{session['session_id']}", use_container_width=True):
                    st.session_state.current_session = {
                        "session_dir": Path(session["session_dir"]),
                        "metadata": session,
                    }
                    st.rerun()
    else:
        st.info("No sessions yet. Start a new research to begin!")


# ─────────────────────────────────────────────────────────────────────────
# Main Area: Research Interface
# ─────────────────────────────────────────────────────────────────────────

if st.session_state.current_session:
    session_data = st.session_state.current_session
    session_dir = session_data["session_dir"]

    # Load session metadata
    meta_file = session_dir / "session.json"
    if meta_file.exists():
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
    else:
        meta = {"topic": "Unknown", "status": "running"}

    # Header
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.title(f"🔍 {meta.get('topic', 'Research')}")
    with col2:
        status_badge = (
            "✅ Complete" if meta.get("status") == "complete" else "⏳ Running"
        )
        st.metric("Status", status_badge)
    with col3:
        st.metric("Papers", meta.get("paper_count", 0))

    st.divider()

    # Session metadata
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(f"**Depth:** {meta.get('depth', 'N/A')}")
    with col2:
        st.write(f"**Min Sources:** {meta.get('min_sources', 'N/A')}")
    with col3:
        st.write(f"**Created:** {meta.get('created_at', 'N/A')[:10]}")

    st.divider()

    # Main content area
    col_main, col_pdf = st.columns([2, 1])

    with col_main:
        st.subheader("📖 Research Output")

        # Run research if needed
        if st.session_state.research_running and "goal" in session_data:
            goal = session_data["goal"]

            # Output streaming container
            output_placeholder = st.empty()

            def on_output_callback(text: str) -> None:
                """Callback to receive streaming output from agent."""
                st.session_state.output_buffer.append(text)
                combined = "".join(st.session_state.output_buffer)
                with output_placeholder.container():
                    st.markdown(combined)

            # Run the agent
            with st.spinner("🔬 Research in progress..."):
                report = asyncio.run(
                    run_autonomous_agent(
                        goal=goal,
                        session_dir=session_dir,
                        on_output=on_output_callback,
                    )
                )

            st.success("✅ Research complete!")
            st.session_state.research_running = False
            st.rerun()

        # Display report if it exists
        report_file = session_dir / "report.md"
        if report_file.exists():
            report_text = report_file.read_text(encoding="utf-8")

            # Tabs for different views
            tab1, tab2 = st.tabs(["📄 Report", "📑 Raw Markdown"])

            with tab1:
                st.markdown(report_text)

            with tab2:
                st.code(report_text, language="markdown")

            # Download button
            st.download_button(
                label="⬇️ Download Report",
                data=report_text,
                file_name=f"{meta.get('topic', 'report')}.md",
                mime="text/markdown",
            )
        else:
            st.info("Report will appear here once research is complete.")

    with col_pdf:
        st.subheader("📚 Papers")

        papers_dir = session_dir / "papers"
        if papers_dir.exists():
            pdf_files = list(papers_dir.glob("*.pdf"))

            if pdf_files:
                # PDF selector
                pdf_names = [p.name for p in pdf_files]
                selected_pdf_name = st.selectbox(
                    "Select PDF",
                    pdf_names,
                    key="pdf_selector",
                )

                selected_pdf_path = papers_dir / selected_pdf_name
                st.info(f"📄 {selected_pdf_name}")
                st.caption(
                    f"Size: {selected_pdf_path.stat().st_size // 1024} KB"
                )

                # PDF viewer (download link for now)
                with open(selected_pdf_path, "rb") as f:
                    st.download_button(
                        label="⬇️ Download PDF",
                        data=f.read(),
                        file_name=selected_pdf_name,
                        mime="application/pdf",
                    )

                # List all papers
                st.markdown("**All Papers:**")
                for pdf in pdf_files:
                    size_kb = pdf.stat().st_size // 1024
                    st.caption(f"📄 {pdf.name} ({size_kb} KB)")
            else:
                st.info("No PDFs downloaded yet.")
        else:
            st.info("Papers folder not found.")

else:
    # Welcome screen
    st.title("🎓 Autonomous Research Agent")
    st.markdown(
        """
        Welcome to your personal research assistant! 

        **How it works:**
        1. 📝 Enter your research topic and question in the sidebar
        2. 🔍 The agent autonomously searches for papers and gathers evidence
        3. 📚 All papers are organized in dedicated folders per research
        4. 📖 Get a comprehensive report with all sources cited

        **Features:**
        - ✅ Autonomous research (no user input needed during process)
        - ✅ Dedicated folders for each research query
        - ✅ PDF management and viewing
        - ✅ Real-time streaming of research progress
        - ✅ Beautiful markdown reports with citations

        **Get started:** Fill in the form in the left sidebar to begin your research!
        """
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("**🔍 Web Search**\n\nSearches Tavily for academic papers")
    with col2:
        st.info("**📥 PDF Download**\n\nAutomatically saves papers locally")
    with col3:
        st.info("**✍️ Report Gen**\n\nGenerates comprehensive reports")
