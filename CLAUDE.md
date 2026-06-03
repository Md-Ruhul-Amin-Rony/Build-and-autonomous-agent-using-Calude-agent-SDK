# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

1. Copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`.
2. Install dependencies: `pip install -r requirements.txt`

## Running the agent

```
python research_agent.py
```

## Architecture

This is a single-file Python project (`research_agent.py`) that runs a multi-turn conversational health research agent using the Claude Agent SDK.

**Key design**: The agent uses `ClaudeSDKClient` (stateful) instead of the bare `query()` function (stateless). Each `async with ClaudeSDKClient(...) as client:` block is one session — Claude retains the full conversation history across every `client.query()` / `client.receive_response()` exchange within that block.

**Two example conversation patterns**:

1. **`run_guided_deep_dive()`** — five turns where each question explicitly zooms into something the previous answer mentioned ("You mentioned the stomach's role — zoom in there…"). Demonstrates how back-references work naturally with session memory.

2. **`run_research_then_analyse()`** — three independent research turns that load Claude's context with facts, followed by a single synthesis turn that asks Claude to connect across all three topics. Demonstrates using accumulated session context for higher-order analysis.

**Core SDK primitives**:
- `ClaudeSDKClient(options)` as an async context manager — manages the session lifecycle.
- `await client.query(prompt)` — sends a turn.
- `async for message in client.receive_response()` — streams the response for that turn; yields `AssistantMessage` / `TextBlock` (text) and `ResultMessage` (cost/session metadata).
- `ClaudeAgentOptions(system_prompt, model)` — shared config applied at session start.

**Model**: `claude-sonnet-4-6` (set in `MODEL` constant).
