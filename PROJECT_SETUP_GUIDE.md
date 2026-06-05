# Building a Health Research Agent from Scratch
## Complete Step-by-Step Guide

This guide walks you through building a multi-turn health research agent using Claude Agent SDK, with web search and PDF download capabilities.

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Project Setup](#project-setup)
3. [Virtual Environment](#virtual-environment)
4. [API Keys Configuration](#api-keys-configuration)
5. [Installing Dependencies](#installing-dependencies)
6. [Understanding the Architecture](#understanding-the-architecture)
7. [Building the Agent Step-by-Step](#building-the-agent-step-by-step)
8. [Running the Agent](#running-the-agent)
9. [Extending & Customizing](#extending--customizing)

---

## Prerequisites

Before starting, you need:
- **Python 3.8+** (check with `python --version`)
- **Windows PowerShell** or Command Prompt
- **Internet connection** (for API calls)
- **Text editor**: VS Code recommended
- **API accounts** (both free with trial credits):
  - Anthropic API (for Claude)
  - Tavily API (for web search)

---

## Project Setup

### Step 1: Create Project Folder

Open PowerShell and run:
```powershell
# Create project directory
mkdir C:\Users\YourUsername\source\My_First_Agent
cd C:\Users\YourUsername\source\My_First_Agent
```

### Step 2: Initialize Git (Optional but Recommended)

```powershell
git init
```

---

## Virtual Environment

### Step 3: Create Virtual Environment

**On Windows PowerShell:**
```powershell
python -m venv .venv
```

This creates an isolated Python environment for your project.

### Step 4: Activate Virtual Environment

**On Windows PowerShell:**
```powershell
# Allow script execution for this session
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1
```

You should see `(.venv)` at the start of your PowerShell prompt, like:
```
(.venv) PS C:\Users\YourUsername\source\My_First_Agent>
```

---

## API Keys Configuration

### Step 5: Get Anthropic API Key

1. Visit: **https://console.anthropic.com/**
2. Sign in (create account if needed)
3. Go to **API Keys** section
4. Click **Create Key**
5. Copy your key (looks like: `sk-ant-v0-xxxxxxxxxxxx`)
6. **Save it somewhere safe** — you'll only see it once!

### Step 6: Get Tavily API Key

1. Visit: **https://app.tavily.com/**
2. Sign up or log in
3. Go to **API Keys**
4. Copy your API key
5. You get **1,000 free searches/month** on free tier

### Step 7: Create `.env` File

In your project folder, create a file named `.env` (with a dot at the start):

```
ANTHROPIC_API_KEY=sk-ant-v0-xxxxxxxxxxxx
TAVILY_API_KEY=your-tavily-api-key-here
```

**Replace the values with your actual keys!**

⚠️ **NEVER share this file or commit it to Git!**

### Step 8: Create `.gitignore` File

Create a file named `.gitignore`:

```
# Sensitive files
.env
.env.local

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.venv/

# Virtual environment folders
bin/
lib/
include/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Project outputs
papers/
*.pdf
```

This prevents your API keys from being uploaded to GitHub.

---

## Installing Dependencies

### Step 9: Create `requirements.txt`

Create a file named `requirements.txt`:

```
claude-agent-sdk
python-dotenv
tavily-python
requests
```

### Step 10: Install Packages

With your virtual environment activated, run:

```powershell
pip install -r requirements.txt
```

This installs:
- **claude-agent-sdk**: Anthropic's agent framework
- **python-dotenv**: Load `.env` variables
- **tavily-python**: Web search client
- **requests**: HTTP library for downloads

Verify installation:
```powershell
pip list
```

---

## Understanding the Architecture

### Project Structure

After setup, your folder should look like:
```
My_First_Agent/
├── .venv/                    # Virtual environment (ignored by git)
├── papers/                   # Downloaded PDFs go here
├── .env                      # Your API keys (NOT committed)
├── .env.example              # Template (for sharing)
├── .gitignore                # Tells git what to ignore
├── requirements.txt          # Dependencies list
├── research_agent.py         # Main agent code
└── README.md                 # Project documentation
```

### Core Concepts

#### 1. **Stateless vs Stateful Agents**
- **Stateless**: Each query is independent (no memory)
- **Stateful**: Agent remembers previous turns in conversation

This project uses **stateful agents** with `ClaudeSDKClient` for multi-turn conversations.

#### 2. **Tools**
Tools are functions Claude can call:
- **web_search**: Search the internet via Tavily
- **download_pdfs**: Save PDFs locally

Tools are registered with the MCP (Model Context Protocol) server.

#### 3. **MCP Server**
The MCP server exposes tools to Claude in a standardized format. Tool names follow pattern: `mcp__<server_name>__<tool_name>`

---

## Building the Agent Step-by-Step

### Step 11: Create Basic Agent Structure

Create `research_agent.py`:

```python
import asyncio
import os
import sys
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

# Handle Windows console encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-16"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Configuration
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

print("Agent initialized successfully!")
```

**Run it:**
```powershell
python research_agent.py
```

Expected output:
```
Agent initialized successfully!
```

---

### Step 12: Add Tavily Web Search Tool

Add this to `research_agent.py` after imports and configuration:

```python
from tavily import TavilyClient
from claude_agent_sdk import tool, ToolAnnotations
import requests
import re
import asyncio
from typing import Any

# Initialize Tavily client
_tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY", ""))

# Academic domains to prioritize
RESEARCH_DOMAINS = [
    "pubmed.ncbi.nlm.nih.gov",
    "pmc.ncbi.nlm.nih.gov",
    "nature.com",
    "sciencedirect.com",
    "springer.com",
    "biorxiv.org",
    "medrxiv.org",
]

# Define web_search tool
@tool(
    "web_search",
    "Search the web for research papers and articles. Returns titles, URLs, relevance scores, and summaries.",
    {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query, e.g., 'protein digestion amino acid absorption'",
            },
            "max_results": {
                "type": "integer",
                "description": "Number of results (1-15). Default 8.",
            },
        },
        "required": ["query"],
    },
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
)
async def web_search(args: dict[str, Any]) -> dict[str, Any]:
    query = str(args["query"])
    max_results = min(int(args.get("max_results", 8)), 15)

    # Call Tavily API
    response = await asyncio.to_thread(
        _tavily.search,
        query,
        search_depth="advanced",
        max_results=max_results,
        include_domains=RESEARCH_DOMAINS,
        include_raw_content=False,
    )

    results = response.get("results", [])
    
    # Format results for display
    lines = [f"Search: '{query}' | {len(results)} results\n"]
    for i, r in enumerate(results, 1):
        tag = "[PDF] " if r["url"].lower().endswith(".pdf") else ""
        lines.append(
            f"{i}. {tag}{r['title']}\n"
            f"   URL: {r['url']}\n"
            f"   Score: {r['score']:.3f}\n"
        )

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}
```

---

### Step 13: Add PDF Download Tool

Add this to `research_agent.py`:

```python
def _safe_filename(url: str) -> str:
    """Create safe filename from URL"""
    name = url.rstrip("/").split("?")[0].split("#")[0].split("/")[-1] or "paper"
    name = re.sub(r"[^\w.\-]", "_", name)
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name[:120]

@tool(
    "download_pdfs",
    "Download PDFs from URLs and save to papers/ folder.",
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
            
            # Validate it's a real PDF
            if resp.content[:5] != b"%PDF-":
                failed.append(f"{url} — not a valid PDF")
                continue
                
            dest.write_bytes(resp.content)
            saved.append(f"{filename} ({len(resp.content) // 1024} KB)")
        except Exception as exc:
            failed.append(f"{url} — {exc}")

    lines = []
    if saved:
        lines.append(f"Saved {len(saved)} PDF(s) to ./papers/:")
        lines.extend(f"  + {f}" for f in saved)
    if failed:
        lines.append(f"Failed ({len(failed)}):")
        lines.extend(f"  - {f}" for f in failed)

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}
```

---

### Step 14: Register Tools with MCP Server

Add this to `research_agent.py`:

```python
from claude_agent_sdk import create_sdk_mcp_server, ClaudeAgentOptions

# Create MCP server with tools
_research_server = create_sdk_mcp_server(
    name="research_tools",
    version="1.0.0",
    tools=[web_search, download_pdfs],
)

# Agent configuration
AGENT_OPTIONS = ClaudeAgentOptions(
    system_prompt=SYSTEM_PROMPT,
    model=MODEL,
    mcp_servers={"research_tools": _research_server},
    allowed_tools=[
        "mcp__research_tools__web_search",
        "mcp__research_tools__download_pdfs",
    ],
)
```

---

### Step 15: Add Helper Function for Responses

Add this to `research_agent.py`:

```python
from claude_agent_sdk import ClaudeSDKClient, AssistantMessage, TextBlock, ResultMessage

async def print_response(client: ClaudeSDKClient, label: str = "") -> None:
    """Print Claude's response and show costs"""
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
                print(f"\n[turns: {message.num_turns} | cost: {cost}]")
```

---

### Step 16: Create Main Agent Function

Add this to `research_agent.py`:

```python
async def run_research_agent() -> None:
    """Run multi-turn research with memory and tools"""
    print("\n" + "=" * 70)
    print("  HEALTH RESEARCH AGENT")
    print("  Multi-turn conversation with web search and PDF download")
    print("=" * 70)

    async with ClaudeSDKClient(options=AGENT_OPTIONS) as client:

        # Turn 1: Broad search
        await client.query(
            "Search for recent research on protein digestion mechanisms in the human body. "
            "Download any PDFs you find and summarize the key findings."
        )
        await print_response(client, "Turn 1: Protein Digestion Overview")

        # Turn 2: Deep dive (remembers Turn 1)
        await client.query(
            "Based on what you found, search specifically for information about amino acid "
            "transporters in the small intestine. Download relevant papers and explain "
            "how different transporter families work."
        )
        await print_response(client, "Turn 2: Amino Acid Transporters")

        # Turn 3: Synthesis (has context from Turns 1 & 2)
        await client.query(
            "Now draw everything together. Write a summary explaining: (1) how protein is "
            "broken down, (2) how amino acids are absorbed, and (3) factors affecting efficiency."
        )
        await print_response(client, "Turn 3: Comprehensive Summary")

    print("\n" + "=" * 70)
    print("  Research session complete!")
    print("  Check ./papers/ for downloaded PDFs")
    print("=" * 70)
```

---

### Step 17: Create Main Entry Point

Add this to `research_agent.py`:

```python
async def main() -> None:
    """Main entry point"""
    try:
        await run_research_agent()
    except KeyboardInterrupt:
        print("\n\nSession interrupted by user.")
    except Exception as e:
        print(f"\nError: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Running the Agent

### Step 18: Test the Agent

With your virtual environment activated:

```powershell
python research_agent.py
```

### Expected Flow:

1. Agent connects to Claude API (uses your ANTHROPIC_API_KEY)
2. Claude calls web_search tool → searches via Tavily
3. Tavily returns research papers
4. Claude calls download_pdfs tool → downloads PDFs to `./papers/`
5. Claude analyzes findings and responds
6. Process repeats for Turn 2 and Turn 3
7. Session shows total cost (in USD from API)

### Cost Estimate:

Each turn costs approximately **$0.10–0.50** depending on:
- Search results size
- PDF sizes downloaded
- Claude's response length

This is why you get **free trial credits** to test!

### How to Stop:

If the agent is running:
```powershell
Ctrl + C
```

---

## Extending & Customizing

### Modify System Prompt

Change the `SYSTEM_PROMPT` to different domains:

**Example: Legal Research Agent**
```python
SYSTEM_PROMPT = """\
You are an expert legal research assistant with knowledge of contract law, \
constitutional law, and case precedent. Search for relevant legal cases, \
statutes, and law review articles to support your analysis.\
"""
```

### Add More Tools

Create new tools and add to `create_sdk_mcp_server`:

```python
@tool("my_new_tool", "Description", {...})
async def my_new_tool(args: dict[str, Any]) -> dict[str, Any]:
    # Implementation here
    return {"content": [{"type": "text", "text": "result"}]}

# Register in MCP server
_research_server = create_sdk_mcp_server(
    name="research_tools",
    tools=[web_search, download_pdfs, my_new_tool],  # Add here
)
```

### Customize Research Questions

Edit the queries in `run_research_agent()`:

```python
await client.query("Your custom question here...")
```

### Change Model

Swap out the model:

```python
MODEL = "claude-opus-4-1"  # or other available models
```

---

## Troubleshooting

### Issue: "ANTHROPIC_API_KEY not found"
**Solution**: Check `.env` file has correct format and is in project root

### Issue: Tavily results not working
**Solution**: Verify `TAVILY_API_KEY` is correct in `.env`

### Issue: PDFs not downloading
**Solution**: 
- Check internet connection
- URLs might be access-restricted
- Some publishers block automated downloads

### Issue: PowerShell execution error
**Solution**: Run before activating:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

---

## Next Steps

1. **Explore different domains**: Create agents for law, medicine, finance, etc.
2. **Add more tools**: Database queries, file uploads, calculations
3. **Persist memory**: Save conversation history to database
4. **Create UI**: Build web interface with Flask/FastAPI
5. **Deploy**: Run on cloud services (AWS, Azure, Google Cloud)

---

## Key Learning Points

✅ **Virtual environments** isolate project dependencies  
✅ **Environment variables** protect sensitive data  
✅ **Async programming** enables concurrent API calls  
✅ **Tools** extend Claude's capabilities  
✅ **Session memory** creates multi-turn conversations  
✅ **MCP servers** standardize tool registration  

You now understand the complete architecture and can build similar agents for any domain!
