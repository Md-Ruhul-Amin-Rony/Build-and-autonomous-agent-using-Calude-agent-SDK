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

This is a single-file Python project (`research_agent.py`) that runs a multi-turn conversational health research agent using the Claude Agent SDK.

**Key design**: The agent uses `ClaudeSDKClient` (stateful) instead of the bare `query()` function (stateless). Each `async with ClaudeSDKClient(...) as client:` block is one session — Claude retains the full conversation history across every `client.query()` / `client.receive_response()` exchange within that block.

**Two tools** (defined with `@tool`, bundled into an MCP server via `create_sdk_mcp_server`):

| Tool | What it does |
|---|---|
| `web_search` | Calls Tavily (`search_depth="advanced"`) prioritising 16 academic/scientific domains. Returns titles, URLs, relevance scores, and summaries. Flags PDF URLs. |
| `download_pdfs` | Downloads a list of PDF URLs to `./papers/`. Validates the `%PDF-` magic bytes before saving. Runs HTTP via `asyncio.to_thread(requests.get, ...)`. |

Tool registration pattern:
```python
_research_server = create_sdk_mcp_server(name="research_tools", tools=[web_search, download_pdfs])
options = ClaudeAgentOptions(..., mcp_servers={"research_tools": _research_server},
                             allowed_tools=["mcp__research_tools__web_search", ...])
```
Tool names follow the convention `mcp__<server_name>__<tool_name>`.

**Two example conversation patterns**:

1. **`run_tool_augmented_research()`** — four turns where Claude actively calls `web_search` and `download_pdfs`, then synthesises across accumulated search results. Demonstrates tool use + session memory together.

2. **`run_guided_deep_dive()`** — four turns where each question zooms into the previous answer. Tools available on demand (Claude may search when it wants a citation).

**Core SDK primitives**:
- `ClaudeSDKClient(options)` as an async context manager — manages the session lifecycle.
- `await client.query(prompt)` — sends a turn.
- `async for message in client.receive_response()` — streams the response; yields `AssistantMessage`/`TextBlock` (text) and `ResultMessage` (cost/session metadata).
- `ClaudeAgentOptions(system_prompt, model, mcp_servers, allowed_tools)` — shared config.

**Output**: Downloaded PDFs are saved to `./papers/` and listed at the end of the session.

**Model**: `claude-sonnet-4-6` (set in `MODEL` constant).
