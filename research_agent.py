import asyncio
import os
import re
import sys
from pathlib import Path
from typing import Any

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
PAPERS_DIR = Path("papers")
PAPERS_DIR.mkdir(exist_ok=True)

SYSTEM_PROMPT = """\
You are an expert health and nutrition research assistant with deep knowledge in human \
physiology, biochemistry, and nutritional science. You have access to web search and PDF \
download tools. When researching a topic, search for the latest evidence first, download \
relevant PDFs, and ground your analysis in what you find. \
Balance scientific accuracy with clear, accessible language. \
Structure answers with logical flow from broad concepts down to molecular detail.\
"""

# ---------------------------------------------------------------------------
# Tool 1 — Web search via Tavily
# ---------------------------------------------------------------------------

_tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY", ""))

# Credible academic and scientific domains to prioritise in results.
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
        "and content summaries. PDF links end in .pdf — pass them to download_pdfs to save locally."
    ),
    {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Search query, e.g. 'protein digestion amino acid absorption review 2023 PDF'"
                ),
            },
            "max_results": {
                "type": "integer",
                "description": "Number of results to return (1–15). Default 8.",
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
# Tool 2 — PDF downloader
# ---------------------------------------------------------------------------

def _safe_filename(url: str) -> str:
    """Derive a safe filesystem name from a URL."""
    name = url.rstrip("/").split("?")[0].split("#")[0].split("/")[-1] or "paper"
    name = re.sub(r"[^\w.\-]", "_", name)
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name[:120]


@tool(
    "download_pdfs",
    (
        "Download PDFs from the provided URLs and save them to the local 'papers/' folder. "
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
    saved, failed = [], []

    for url in urls:
        filename = _safe_filename(url)
        dest = PAPERS_DIR / filename
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
        lines.append(f"Saved {len(saved)} PDF(s) to ./papers/:")
        lines.extend(f"  + {f}" for f in saved)
    if failed:
        lines.append(f"\nFailed ({len(failed)}):")
        lines.extend(f"  - {f}" for f in failed)
    if not saved and not failed:
        lines.append("No URLs provided.")

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


# ---------------------------------------------------------------------------
# MCP server — registers both tools for the agent
# ---------------------------------------------------------------------------

_research_server = create_sdk_mcp_server(
    name="research_tools",
    version="1.0.0",
    tools=[web_search, download_pdfs],
)

AGENT_OPTIONS = ClaudeAgentOptions(
    system_prompt=SYSTEM_PROMPT,
    model=MODEL,
    mcp_servers={"research_tools": _research_server},
    allowed_tools=[
        "mcp__research_tools__web_search",
        "mcp__research_tools__download_pdfs",
    ],
)

# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------


async def print_response(client: ClaudeSDKClient, label: str = "") -> None:
    """Print all text from the next complete response, then show cost metadata."""
    if label:
        print(f"\n--- {label} ---")
    async for message in client.receive_response():
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text)
        elif isinstance(message, ResultMessage):
            if message.is_error:
                print("[ERROR]")
            else:
                cost = (
                    f"${message.total_cost_usd:.4f}"
                    if message.total_cost_usd is not None
                    else "n/a"
                )
                print(
                    f"\n[turns: {message.num_turns} | cost: {cost}"
                    f" | session: {message.session_id}]"
                )


# ---------------------------------------------------------------------------
# Example 1 — Tool-augmented multi-turn research
#
# Claude calls web_search and download_pdfs during the conversation.
# Each turn builds on search results from prior turns — demonstrating
# both tool use AND session memory working together.
# ---------------------------------------------------------------------------


async def run_tool_augmented_research() -> None:
    print("\n" + "=" * 70)
    print("  EXAMPLE 1: Tool-Augmented Research")
    print("  Claude searches Tavily for papers and downloads PDFs each turn.")
    print("=" * 70)

    async with ClaudeSDKClient(options=AGENT_OPTIONS) as client:

        # Turn 1 — broad search to anchor the session
        await client.query(
            "Search for recent research papers and reviews on the molecular mechanisms "
            "of protein digestion and amino acid absorption in the small intestine. "
            "Download any PDFs you find, then summarise the key themes across the results."
        )
        await print_response(client, "Turn 1 — Search & download: protein digestion mechanisms")

        # Turn 2 — drill into transporter science based on Turn 1 results
        await client.query(
            "Based on what you just found, focus on intestinal amino acid transporter "
            "families (SLC1, SLC3, SLC6, SLC7, etc.). Search specifically for papers on "
            "their structure and regulation, download any PDFs, and explain how each "
            "family differs in substrate selectivity and driving gradient."
        )
        await print_response(client, "Turn 2 — Search & download: amino acid transporters")

        # Turn 3 — plant vs animal protein (new search, same session context)
        await client.query(
            "Now search for studies comparing the digestibility and bioavailability of "
            "plant-based versus animal-based proteins, including PDCAAS and DIAAS scoring. "
            "Download the PDFs and note which protein sources score highest and why."
        )
        await print_response(client, "Turn 3 — Search & download: plant vs animal protein")

        # Turn 4 — synthesis across all three searches
        await client.query(
            "Drawing on everything you found across all three searches — digestion "
            "mechanisms, transporter biology, and protein-source comparisons — write a "
            "concise evidence-based briefing (4–5 bullet points) for a sports nutritionist "
            "advising athletes on maximising protein absorption. Cite specific URLs where "
            "you can from the papers we downloaded."
        )
        await print_response(client, "Turn 4 — Synthesis: evidence-based briefing")


# ---------------------------------------------------------------------------
# Example 2 — Guided deep-dive (multi-turn memory, tools on demand)
#
# Questions progressively zoom into each prior answer.
# Claude can invoke the search tool when it wants to cite recent evidence,
# illustrating how tools integrate naturally into a flowing conversation.
# ---------------------------------------------------------------------------


async def run_guided_deep_dive() -> None:
    print("\n" + "=" * 70)
    print("  EXAMPLE 2: Guided Deep-Dive (multi-turn memory, tools on demand)")
    print("  Each turn drills into the previous answer; tools available if needed.")
    print("=" * 70)

    async with ClaudeSDKClient(options=AGENT_OPTIONS) as client:

        await client.query(
            "Give me a concise overview of protein digestion — the main stages in order, "
            "no deep detail yet. Search for a recent review if you'd like a citation."
        )
        await print_response(client, "Turn 1 — Overview")

        await client.query(
            "You mentioned the stomach's role. Zoom in: explain the HCl → pepsinogen → "
            "pepsin cascade and its neuro-endocrine control."
        )
        await print_response(client, "Turn 2 — Stomach cascade")

        await client.query(
            "Move to the small intestine. Which pancreatic endopeptidases and brush-border "
            "exopeptidases continue what pepsin started? Include substrate specificities. "
            "Search for a recent paper if you want to ground a specific claim."
        )
        await print_response(client, "Turn 3 — Small-intestine enzymes")

        await client.query(
            "Looking back at everything we've covered — overview, stomach cascade, and "
            "small-intestine enzymes — what are the two most clinically relevant "
            "rate-limiting steps in protein absorption, and what dietary interventions "
            "most effectively address them?"
        )
        await print_response(client, "Turn 4 — Synthesis & interventions")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    print("=" * 70)
    print("  HEALTH RESEARCH AGENT")
    print("  Tools: Tavily web search  |  PDF downloader -> ./papers/")
    print("  Mode:  Multi-turn conversational research with memory")
    print("=" * 70)

    await run_tool_augmented_research()
    await run_guided_deep_dive()

    papers = sorted(PAPERS_DIR.glob("*.pdf"))
    print(f"\n{'=' * 70}")
    print(f"  Session complete. {len(papers)} PDF(s) saved to ./papers/:")
    for p in papers:
        print(f"    {p.name}  ({p.stat().st_size // 1024} KB)")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
