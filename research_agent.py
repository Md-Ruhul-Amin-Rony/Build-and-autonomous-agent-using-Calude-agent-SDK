import asyncio
import contextvars
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import requests
from dotenv import load_dotenv
from tavily import TavilyClient
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ResultMessage,
    tool,
    ToolAnnotations,
    create_sdk_mcp_server,
)

load_dotenv()

# Ensure stdout handles the full Unicode range on Windows consoles.
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-16"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL = "claude-sonnet-4-6"
RESEARCH_DIR = Path("research")   # per-session folders live here
PAPERS_DIR = Path("papers")       # legacy fallback for CLI use
REPORTS_DIR = Path("reports")     # legacy fallback for CLI use
RESEARCH_DIR.mkdir(exist_ok=True)
PAPERS_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

MAX_TURNS = 10

# Context variable: points to the current session's papers directory.
# Set once at the start of run_autonomous_agent(); inherited by all
# coroutines called from it (including tool functions).
_session_papers_dir: contextvars.ContextVar[Path] = contextvars.ContextVar(
    "_session_papers_dir", default=PAPERS_DIR
)

AUTONOMOUS_SYSTEM_PROMPT = """\
You are a fully autonomous research agent. You work independently from start to finish \
without asking the user any questions at any point. You have three tools: \
web_search, download_pdfs, and finish_research.

OPERATING RULES — follow exactly:
1. NEVER ask the user for clarification or guidance. If something is ambiguous, \
   make a reasonable assumption, note it, and proceed.
2. Begin by briefly stating your research plan (2-3 sentences), then execute it immediately.
3. Use web_search with varied, targeted queries — search at least once per focus area.
4. Pass every direct PDF URL you find to download_pdfs.
5. After gathering evidence, synthesise your findings into a complete, structured report.
6. Signal completion by calling finish_research with the full report and all source URLs.
7. Be decisive — do not loop indefinitely. Conclude once you meet the source target.\
"""

# ---------------------------------------------------------------------------
# API key validation
# ---------------------------------------------------------------------------

_anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
_tavily_key = os.getenv("TAVILY_API_KEY", "").strip()
_missing = [
    k for k, v in {"ANTHROPIC_API_KEY": _anthropic_key, "TAVILY_API_KEY": _tavily_key}.items()
    if not v
]
if _missing:
    raise EnvironmentError(
        f"Missing required env vars: {', '.join(_missing)}. "
        "Copy .env.example to .env and fill in the keys."
    )

_tavily = TavilyClient(api_key=_tavily_key)

# ---------------------------------------------------------------------------
# Tool 1 — Web search (module-level, no per-session state)
# ---------------------------------------------------------------------------

RESEARCH_DOMAINS = [
    "pubmed.ncbi.nlm.nih.gov",
    "pmc.ncbi.nlm.nih.gov",
    "ncbi.nlm.nih.gov",
    "researchgate.net",
    "semanticscholar.org",
    "nature.com",
    "sciencedirect.com",
    "springer.com",
    "plos.org",
    "biorxiv.org",
    "medrxiv.org",
    "jnutrition.org",
    "academic.oup.com",
    "journals.physiology.org",
    "frontiersin.org",
    "mdpi.com",
]


@tool(
    "web_search",
    (
        "Search the web for recent research papers, reviews, and credible scientific articles. "
        "Prioritises academic and peer-reviewed sources. Returns titles, URLs, relevance scores, "
        "and summaries. PDF links end in .pdf — pass them to download_pdfs to save locally."
    ),
    {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query, e.g. 'gut microbiome protein digestion review 2024 PDF'",
            },
            "max_results": {
                "type": "integer",
                "description": "Number of results (1–15). Default 8.",
            },
        },
        "required": ["query"],
    },
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
)
async def web_search(args: dict[str, Any]) -> dict[str, Any]:
    query = str(args["query"])
    max_results = min(int(args.get("max_results", 8)), 15)

    response = await asyncio.to_thread(
        _tavily.search,
        query,
        search_depth="advanced",
        max_results=max_results,
        include_domains=RESEARCH_DOMAINS,
        include_raw_content=False,
    )

    results = response.get("results", [])
    pdf_urls = [r["url"] for r in results if r["url"].lower().endswith(".pdf")]

    lines = [f"Search: '{query}'  |  {len(results)} results\n"]
    for i, r in enumerate(results, 1):
        tag = "[PDF] " if r["url"].lower().endswith(".pdf") else ""
        lines.append(
            f"{i}. {tag}{r['title']}\n"
            f"   URL:   {r['url']}\n"
            f"   Score: {r['score']:.3f}\n"
            f"   Summary: {r['content'][:350]}\n"
        )

    if pdf_urls:
        lines.append(f"\nDirect PDF URLs ({len(pdf_urls)}):")
        lines.extend(f"  {u}" for u in pdf_urls)

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


# ---------------------------------------------------------------------------
# Tool 2 — PDF downloader (uses _session_papers_dir context var)
# ---------------------------------------------------------------------------


def _safe_filename(url: str) -> str:
    name = url.rstrip("/").split("?")[0].split("#")[0].split("/")[-1] or "paper"
    name = re.sub(r"[^\w.\-]", "_", name)
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name[:120]


@tool(
    "download_pdfs",
    (
        "Download PDFs from the provided URLs and save them to the session's papers folder. "
        "Returns the filenames and sizes of successfully saved files."
    ),
    {
        "type": "object",
        "properties": {
            "urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of PDF URLs to download",
            }
        },
        "required": ["urls"],
    },
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
    ),
)
async def download_pdfs(args: dict[str, Any]) -> dict[str, Any]:
    urls = args.get("urls", [])
    # Resolve the per-session papers directory from the context var.
    papers_dir = _session_papers_dir.get()
    papers_dir.mkdir(parents=True, exist_ok=True)

    saved, failed = [], []

    for url in urls:
        filename = _safe_filename(url)
        dest = papers_dir / filename
        try:
            resp = await asyncio.to_thread(
                requests.get,
                url,
                timeout=30,
                headers={"User-Agent": "Mozilla/5.0 (research-agent/1.0)"},
            )
            resp.raise_for_status()
            if resp.content[:5] != b"%PDF-":
                failed.append(f"{url} — response is not a valid PDF")
                continue
            dest.write_bytes(resp.content)
            saved.append(f"{filename} ({len(resp.content) // 1024} KB)")
        except Exception as exc:
            failed.append(f"{url} — {exc}")

    lines: list[str] = []
    if saved:
        lines.append(f"Saved {len(saved)} PDF(s) to {papers_dir}:")
        lines.extend(f"  + {f}" for f in saved)
    if failed:
        lines.append(f"Failed ({len(failed)}):")
        lines.extend(f"  - {f}" for f in failed)
    if not saved and not failed:
        lines.append("No URLs provided.")

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ResearchGoal:
    """Everything the agent needs to know about what to research and deliver."""

    topic: str
    question: str
    focus_areas: list[str] = field(default_factory=list)
    depth: str = "comprehensive"
    min_sources: int = 5
    output_format: str = "research report"


@dataclass
class AgentState:
    """Mutable state shared between the driver loop and finish_research closure."""

    completed: bool = False
    report: str = ""
    sources: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------


def create_research_session(goal: ResearchGoal) -> Path:
    """
    Create a timestamped directory for this research session.

    Structure:
        research/<topic_slug>_<YYYYMMDD_HHMMSS>/
            session.json    ← metadata
            report.md       ← written by finish_research
            papers/         ← PDFs downloaded during session
    """
    slug = re.sub(r"[^\w]+", "_", goal.topic.lower()).strip("_")[:40]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = RESEARCH_DIR / f"{slug}_{ts}"
    (session_dir / "papers").mkdir(parents=True, exist_ok=True)

    meta = {
        "session_id": f"{slug}_{ts}",
        "topic": goal.topic,
        "question": goal.question,
        "focus_areas": goal.focus_areas,
        "depth": goal.depth,
        "min_sources": goal.min_sources,
        "output_format": goal.output_format,
        "created_at": datetime.now().isoformat(),
        "status": "running",
        "paper_count": 0,
        "source_count": 0,
    }
    (session_dir / "session.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return session_dir


def update_session_meta(session_dir: Path, **kwargs: Any) -> None:
    """Merge kwargs into session.json."""
    meta_path = session_dir / "session.json"
    if not meta_path.exists():
        return
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update(kwargs)
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


def load_all_sessions() -> list[dict]:
    """Return all session metadata dicts, newest first."""
    sessions = []
    for d in sorted(RESEARCH_DIR.iterdir(), reverse=True):
        meta_file = d / "session.json"
        if d.is_dir() and meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                meta["session_dir"] = str(d)
                # Recount papers from disk (stays accurate after re-runs)
                papers_dir = d / "papers"
                meta["paper_count"] = len(list(papers_dir.glob("*.pdf"))) if papers_dir.exists() else 0
                sessions.append(meta)
            except Exception:
                pass
    return sessions


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def build_initial_prompt(goal: ResearchGoal) -> str:
    focus_block = ""
    if goal.focus_areas:
        items = "\n".join(f"  {i+1}. {a}" for i, a in enumerate(goal.focus_areas))
        focus_block = f"\n\nFOCUS AREAS (cover each one):\n{items}"

    return (
        f"RESEARCH MISSION\n{'=' * 40}\n"
        f"Topic:    {goal.topic}\n"
        f"Depth:    {goal.depth}\n"
        f"Question: {goal.question}"
        f"{focus_block}\n\n"
        f"DELIVERABLE\n{'=' * 40}\n"
        f"Produce a {goal.output_format} that directly answers the question.\n"
        f"Minimum sources: {goal.min_sources} (from actual search results this session).\n\n"
        f"SUCCESS CRITERIA\n{'=' * 40}\n"
        f"  - Directly answers the research question\n"
        f"  - Addresses every focus area listed above\n"
        f"  - Cites at least {goal.min_sources} sources found during this session\n"
        f"  - Contains an executive summary and clear conclusions\n\n"
        f"BEGIN NOW. State your plan briefly, then search and deliver. "
        f"Call finish_research when your report is ready."
    )


def _nudge_prompt(turn: int, max_turns: int) -> str:
    remaining = max_turns - turn - 1
    if remaining == 1:
        return (
            "One turn remaining. Write and submit your report now by calling "
            "finish_research. If you have a critical gap, do one final targeted "
            "search first, then submit."
        )
    return (
        f"Continue ({remaining} turns left). "
        "Search where you still have gaps, then call finish_research with your complete report. "
        "Do not ask questions."
    )


# ---------------------------------------------------------------------------
# Response printer — console + optional Streamlit callback
# ---------------------------------------------------------------------------


async def print_response(
    client: ClaudeSDKClient,
    on_output: Callable[[str], None] | None = None,
) -> None:
    """
    Stream and print the current response.

    on_output: optional callback that receives Markdown-formatted strings
               suitable for rendering in a Streamlit st.write_stream().
    """
    async for message in client.receive_response():
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text)
                    if on_output:
                        on_output(block.text)

                elif hasattr(block, "name") and hasattr(block, "input"):
                    inp = block.input or {}
                    name = block.name

                    if "query" in inp:
                        console = f"\n  [TOOL -> {name}]  query: \"{inp['query']}\""
                        markdown = f"\n\n> 🔍 **{name}** — `{inp['query']}`\n"
                    elif "urls" in inp:
                        n = len(inp.get("urls", []))
                        console = f"\n  [TOOL -> {name}]  {n} URL(s)"
                        markdown = f"\n\n> 📥 **{name}** — downloading {n} PDF(s)\n"
                    elif "report" in inp:
                        words = len(str(inp.get("report", "")).split())
                        srcs = len(inp.get("sources", []))
                        console = f"\n  [TOOL -> {name}]  report: {words} words | sources: {srcs}"
                        markdown = f"\n\n> ✅ **{name}** — {words} words, {srcs} sources\n"
                    else:
                        console = f"\n  [TOOL -> {name}]"
                        markdown = f"\n\n> 🔧 **{name}**\n"

                    print(console)
                    if on_output:
                        on_output(markdown)

        elif isinstance(message, ResultMessage):
            if message.is_error:
                print("\n  [ERROR in session]")
                if on_output:
                    on_output("\n\n❌ **Session error**\n")
            else:
                cost = (
                    f"${message.total_cost_usd:.4f}"
                    if message.total_cost_usd is not None
                    else "n/a"
                )
                print(f"\n  [turns: {message.num_turns} | cost: {cost}]")
                if on_output:
                    on_output(f"\n\n---\n*Turns: {message.num_turns} · Cost: {cost}*\n")


# ---------------------------------------------------------------------------
# Report saver
# ---------------------------------------------------------------------------


def save_report(goal: ResearchGoal, state: AgentState, session_dir: Path | None = None) -> Path:
    header = (
        f"# {goal.topic}\n\n"
        f"**Research question:** {goal.question}\n\n"
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d')}\n\n"
        "---\n\n"
    )
    body = header + state.report

    if state.sources:
        body += "\n\n---\n\n## Sources\n\n"
        body += "\n".join(f"- {s}" for s in state.sources)

    if session_dir is not None:
        path = session_dir / "report.md"
    else:
        slug = re.sub(r"[^\w]+", "_", goal.topic.lower()).strip("_")[:50]
        path = REPORTS_DIR / f"{slug}_{datetime.now().strftime('%Y-%m-%d')}.md"

    path.write_text(body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Core — autonomous research agent
# ---------------------------------------------------------------------------


async def run_autonomous_agent(
    goal: ResearchGoal,
    session_dir: Path | None = None,
    on_output: Callable[[str], None] | None = None,
) -> str:
    """
    Run a fully autonomous research session.

    Args:
        goal:        What to research and how to deliver it.
        session_dir: Per-query folder (research/<slug>_<ts>/).
                     PDFs → session_dir/papers/
                     Report → session_dir/report.md
                     If None, falls back to global ./papers/ and ./reports/.
        on_output:   Optional callback receiving Markdown-formatted strings.
                     Used by the Streamlit app to stream output to the UI.

    Returns the final report text.
    """
    state = AgentState()

    # Point download_pdfs at the session-specific papers folder.
    papers_dir = (session_dir / "papers") if session_dir else PAPERS_DIR
    papers_dir.mkdir(parents=True, exist_ok=True)
    ctx_token = _session_papers_dir.set(papers_dir)

    def _emit(text: str) -> None:
        if on_output:
            on_output(text)

    def _emit_turn(turn: int, max_turns: int) -> None:
        print(f"\n{'─' * 70}\n  Turn {turn + 1} / {max_turns}\n{'─' * 70}")
        _emit(f"\n\n---\n### Turn {turn + 1} / {max_turns}\n\n")

    # finish_research closes over `state`, `goal`, `session_dir`, `_emit`.
    async def _finish_impl(args: dict[str, Any]) -> dict[str, Any]:
        state.completed = True
        state.report = str(args.get("report", ""))
        state.sources = list(args.get("sources", []))

        report_path = save_report(goal, state, session_dir)

        if session_dir:
            update_session_meta(
                session_dir,
                status="complete",
                paper_count=len(list(papers_dir.glob("*.pdf"))),
                source_count=len(state.sources),
            )

        msg = (
            f"Research complete. Report saved to {report_path}  "
            f"({len(state.report.split())} words, {len(state.sources)} sources)"
        )
        print(f"\n  [AGENT] {msg}")
        _emit(f"\n\n✅ **Research complete** — {len(state.report.split())} words, "
              f"{len(state.sources)} sources\n")
        return {"content": [{"type": "text", "text": msg}]}

    finish_tool = tool(
        "finish_research",
        (
            "Call this when you have gathered sufficient evidence and are ready to submit "
            "the final report. This ends the session and saves the report to disk. "
            "Pass the complete Markdown report and every source URL cited."
        ),
        {
            "type": "object",
            "properties": {
                "report": {
                    "type": "string",
                    "description": (
                        "The complete research report in Markdown. Must include: "
                        "Executive Summary, Key Findings (with inline citations), "
                        "Mechanistic Analysis, Conclusions, and a References section."
                    ),
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "All source URLs cited in the report.",
                },
            },
            "required": ["report", "sources"],
        },
        annotations=ToolAnnotations(
            readOnlyHint=False, destructiveHint=False, idempotentHint=False
        ),
    )(_finish_impl)

    server = create_sdk_mcp_server(
        name="research_tools",
        version="1.0.0",
        tools=[web_search, download_pdfs, finish_tool],
    )

    options = ClaudeAgentOptions(
        system_prompt=AUTONOMOUS_SYSTEM_PROMPT,
        model=MODEL,
        mcp_servers={"research_tools": server},
        allowed_tools=[
            "mcp__research_tools__web_search",
            "mcp__research_tools__download_pdfs",
            "mcp__research_tools__finish_research",
        ],
    )

    print(f"\n{'─' * 70}")
    print(f"  TOPIC:    {goal.topic}")
    print(f"  QUESTION: {goal.question}")
    print(f"  DEPTH:    {goal.depth} | MIN SOURCES: {goal.min_sources} | MAX TURNS: {MAX_TURNS}")
    print(f"{'─' * 70}\n")

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(build_initial_prompt(goal))

            for turn in range(MAX_TURNS):
                _emit_turn(turn, MAX_TURNS)
                await print_response(client, on_output=on_output)

                if state.completed:
                    break

                if turn == MAX_TURNS - 1:
                    await client.query(
                        "This is the final turn. Submit your report now by calling "
                        "finish_research with everything you have gathered."
                    )
                    await print_response(client, on_output=on_output)
                else:
                    await client.query(_nudge_prompt(turn, MAX_TURNS))
    finally:
        _session_papers_dir.reset(ctx_token)

    return state.report


# ---------------------------------------------------------------------------
# Entry point (CLI) — edit ResearchGoal to research any topic
# ---------------------------------------------------------------------------


async def main() -> None:
    goal = ResearchGoal(
        topic="Gut Microbiome and Protein Digestion",
        question=(
            "How does the gut microbiome influence protein digestion and amino acid "
            "absorption efficiency, and what dietary interventions can optimise "
            "this relationship?"
        ),
        focus_areas=[
            "Microbial proteases and their contribution to luminal protein breakdown",
            "Short-chain fatty acids (SCFAs) and regulation of intestinal amino acid transporters",
            "Probiotic and prebiotic interventions shown to improve protein absorption",
            "Differences in microbiome response to plant-based vs animal-based protein fermentation",
        ],
        depth="comprehensive",
        min_sources=6,
        output_format=(
            "structured research report with executive summary, key findings, "
            "mechanistic analysis, dietary recommendations, and references"
        ),
    )

    print("=" * 70)
    print("  AUTONOMOUS HEALTH RESEARCH AGENT")
    print("  Tools: web_search  |  download_pdfs  |  finish_research")
    print("=" * 70)

    session_dir = create_research_session(goal)
    await run_autonomous_agent(goal, session_dir=session_dir)

    papers = sorted((session_dir / "papers").glob("*.pdf"))
    print(f"\n{'=' * 70}")
    print(f"  Done.  Session: {session_dir.name}")
    print(f"  {len(papers)} PDF(s) in {session_dir / 'papers'}")
    print(f"  Report: {session_dir / 'report.md'}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
