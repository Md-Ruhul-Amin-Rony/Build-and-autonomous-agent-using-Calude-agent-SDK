# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

1. Copy `.env.example` to `.env` and fill in both keys:
   - `ANTHROPIC_API_KEY` — from [console.anthropic.com](https://console.anthropic.com)
   - `TAVILY_API_KEY` — from [app.tavily.com](https://app.tavily.com) (free tier: 1,000 searches/month)
2. Install dependencies: `pip install -r requirements.txt`

## Running the agent

```
python research_agent.py
```

## Architecture

A single-file fully autonomous research agent. The user provides a `ResearchGoal`; the agent plans its own search strategy, uses tools, and self-terminates when satisfied — no user input during the session.

### Three tools

Defined with `@tool`, bundled into a per-session MCP server via `create_sdk_mcp_server`.

| Tool | Level | What it does |
|---|---|---|
| `web_search` | module | Calls Tavily (`search_depth="advanced"`) prioritising 16 academic domains. Returns ranked results with titles, URLs, scores, summaries. Flags direct PDF URLs. |
| `download_pdfs` | module | Downloads a list of PDF URLs to `./papers/`. Validates `%PDF-` magic bytes. Uses `asyncio.to_thread(requests.get, ...)`. |
| `finish_research` | per-session | **The autonomy signal.** Claude calls this when done. The implementation closes over `AgentState`, sets `state.completed = True`, saves the report to `./reports/`, and returns a confirmation. The driver loop exits on this flag. |

Tool name convention: `mcp__<server_name>__<tool_name>`.

### Key data structures

- **`ResearchGoal`** — user-facing input: `topic`, `question`, `focus_areas`, `depth`, `min_sources`, `output_format`.
- **`AgentState`** — shared between driver and `finish_research` closure: `completed`, `report`, `sources`.

### Autonomy design

`finish_research` is defined **inside** `run_autonomous_agent()` as a closure over `AgentState`. Each call to `run_autonomous_agent()` gets its own isolated state and its own MCP server instance (built fresh each call). The driver loop:

1. Seeds the session with `build_initial_prompt(goal)` — one structured prompt with goal, focus areas, success criteria.
2. Calls `print_response()` after each turn (which drains all tool calls before returning).
3. Checks `state.completed` — breaks if `finish_research` was called.
4. Otherwise sends a minimal `_nudge_prompt()` (remaining turns count, no direction).
5. On the final turn, forces submission.

Claude decides what to search, when it has enough, and what to write — the driver only keeps the session alive.

### Output

- `./papers/` — PDFs downloaded during the session
- `./reports/<topic_slug>_<date>.md` — structured Markdown report with sources appended

### Customising the research goal

Edit the `ResearchGoal(...)` in `main()`. The agent works on any topic — health, science, engineering, social science, etc.

**Model**: `claude-sonnet-4-6` (set in `MODEL` constant). `MAX_TURNS = 10` is the safety ceiling.
