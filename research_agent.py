import asyncio
from dotenv import load_dotenv
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ResultMessage,
)

load_dotenv()

SYSTEM_PROMPT = """\
You are an expert health and nutrition research assistant with deep knowledge in human \
physiology, biochemistry, and nutritional science. Provide thorough, evidence-based \
research responses. Balance scientific accuracy with clear, accessible language. \
Structure your answers with logical flow from broad concepts down to molecular detail \
where relevant.\
"""

MODEL = "claude-sonnet-4-6"


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
# Example 1 — Guided drill-down
#
# Each question zooms into something mentioned in the previous answer.
# Claude's earlier responses stay in the session context, so "You mentioned..."
# references work naturally without us having to re-state anything.
# ---------------------------------------------------------------------------

async def run_guided_deep_dive() -> None:
    options = ClaudeAgentOptions(system_prompt=SYSTEM_PROMPT, model=MODEL)

    print("\n" + "=" * 70)
    print("  EXAMPLE 1: Guided Deep-Dive (multi-turn with memory)")
    print("  Each turn drills into something from the previous answer.")
    print("=" * 70)

    async with ClaudeSDKClient(options=options) as client:

        # Turn 1 — Broad overview to anchor the conversation
        await client.query(
            "Give me a concise overview of how the human body digests protein — "
            "just the main stages in order, no deep detail yet."
        )
        await print_response(client, "Turn 1 — Overview of protein digestion")

        # Turn 2 — Zoom into the stomach stage mentioned in Turn 1
        await client.query(
            "You mentioned the stomach's role. Zoom in there: explain the roles of "
            "HCl, pepsinogen, and pepsin, and how their activation cascade is "
            "controlled by the nervous and endocrine systems."
        )
        await print_response(client, "Turn 2 — Stomach deep-dive")

        # Turn 3 — Move to the small intestine, picking up where pepsin left off
        await client.query(
            "Pepsin gets things started, but the small intestine does the heavy "
            "lifting. Which pancreatic endopeptidases and brush-border "
            "exopeptidases continue the breakdown, and what are their specific "
            "substrate preferences?"
        )
        await print_response(client, "Turn 3 — Small-intestine enzymes")

        # Turn 4 — Absorption (builds on the enzyme products just discussed)
        await client.query(
            "After those enzymes produce free amino acids and di/tripeptides, how "
            "are they actually transported across the intestinal epithelium into the "
            "bloodstream? Name the transporter families and the driving gradients."
        )
        await print_response(client, "Turn 4 — Absorption mechanisms")

        # Turn 5 — Synthesis turn: pull all threads together
        await client.query(
            "Looking back at everything we've covered — the overview, the stomach "
            "cascade, the small-intestine enzymes, and the absorption transporters — "
            "what are the two or three steps most likely to become rate-limiting in "
            "a healthy adult, and why?"
        )
        await print_response(client, "Turn 5 — Synthesis & rate-limiting factors")


# ---------------------------------------------------------------------------
# Example 2 — Research phase followed by an integrative analysis turn
#
# Three independent research questions load Claude's context with facts.
# The final analysis turn asks Claude to connect across all three topics,
# demonstrating how session memory enables higher-order reasoning.
# ---------------------------------------------------------------------------

RESEARCH_TOPICS = [
    # Topic A — dietary/extrinsic factors
    "What dietary factors — food matrix, cooking method, protein source, "
    "anti-nutritional compounds — affect protein digestibility scores?",

    # Topic B — physiological/intrinsic factors
    "What physiological factors — gastric acid output, pancreatic enzyme "
    "capacity, gut microbiome, age — affect protein absorption efficiency?",

    # Topic C — protein quality metrics and source comparison
    "Compare the digestibility and absorption profile of major animal proteins "
    "(whey, casein, egg) versus plant proteins (soy, pea, rice). Include the "
    "PDCAAS and DIAAS frameworks and what each captures.",
]


async def run_research_then_analyse() -> None:
    options = ClaudeAgentOptions(system_prompt=SYSTEM_PROMPT, model=MODEL)

    print("\n" + "=" * 70)
    print("  EXAMPLE 2: Research Phase → Analysis Phase")
    print("  Three focused research turns, then one integrative analysis turn.")
    print("=" * 70)

    async with ClaudeSDKClient(options=options) as client:

        # Research phase — three independent topics, all in the same session
        for i, topic in enumerate(RESEARCH_TOPICS, start=1):
            await client.query(topic)
            await print_response(client, f"Research Turn {i}")

        # Analysis turn — Claude draws on all three prior answers in its context
        await client.query(
            "Based on everything we've just covered — dietary factors, "
            "physiological factors, and protein-source differences — draft three "
            "evidence-based, actionable recommendations for someone who wants to "
            "maximise protein absorption from a mixed diet. For each recommendation, "
            "cite the specific mechanism from our discussion that supports it."
        )
        await print_response(client, "Analysis — Practical Recommendations")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    print("=" * 70)
    print("  HEALTH RESEARCH AGENT")
    print("  Topic: Human Protein Digestion")
    print("  Mode:  Multi-turn conversational research with memory")
    print("=" * 70)

    await run_guided_deep_dive()
    await run_research_then_analyse()

    print(f"\n{'=' * 70}")
    print("  Research session complete.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
