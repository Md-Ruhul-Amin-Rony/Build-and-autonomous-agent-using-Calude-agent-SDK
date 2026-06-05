# 🎓 Autonomous Research Agent

A production-ready, fully autonomous research agent built with Claude Agent SDK. The agent independently researches any topic, gathers academic papers, and generates comprehensive reports—all with a beautiful Streamlit web interface.

## 🌟 Features

✅ **Fully Autonomous** — No user input needed during research. Provide topic + question, agent runs to completion  
✅ **Multi-Turn Conversations** — Agent remembers context across turns for better synthesis  
✅ **Web Search Integration** — Tavily API searches prioritizing academic/peer-reviewed sources  
✅ **PDF Management** — Automatically downloads and organizes papers per research session  
✅ **Beautiful Web UI** — Elegant Streamlit interface with real-time streaming output  
✅ **Session History** — Browse past research with one click, view papers and reports  
✅ **Dedicated Folders** — Each research creates timestamped `research/<topic>_<timestamp>/` with organized papers  
✅ **Report Generation** — Markdown reports with citations, executive summaries, findings, and sources  
✅ **Flexible Research Goals** — Define custom focus areas, research depth, minimum sources  

---

## 📋 Quick Start

### Prerequisites

- **Python 3.8+**
- **API Keys** (both free with trial credits):
  - [Anthropic API Key](https://console.anthropic.com) ($5 free credits)
  - [Tavily API Key](https://app.tavily.com) (1,000 searches/month free)

### Installation

```bash
# 1. Clone or navigate to project
cd My_First_Agent

# 2. Create virtual environment
python -m venv .venv

# 3. Activate (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# 4. Install dependencies
pip install -r requirements.txt

# 5. Create .env file with API keys
# Copy .env.example to .env and fill in:
# ANTHROPIC_API_KEY=your-key-here
# TAVILY_API_KEY=your-key-here
```

### Run the App

**Option A: Web Interface (Recommended)**
```bash
streamlit run streamlit_app.py
```
Opens browser at `http://localhost:8501`

**Option B: CLI (Command Line)**
```bash
python research_agent.py
```

---

## 🎯 How It Works

### Architecture

```
User Input (Topic + Question + Focus Areas)
    ↓
Agent Autonomous Loop (max 10 turns)
    ├─ Turn 1: Analyze & Plan → Search for papers
    ├─ Turn 2: Download PDFs → Analyze findings
    ├─ Turn 3: Identify gaps → Search more
    ├─ Turn 4-9: Repeat as needed
    ├─ Turn 10: Force completion if needed
    └─ Completion: Generate report + save session
    ↓
Output (Report + PDFs + Session History)
```

### Key Components

#### 1. **research_agent.py** — Core Agent Engine
- Autonomous research loop with configurable depth
- Web search tool (Tavily integration)
- PDF download tool with validation
- Report generation with citations
- Session management with metadata tracking
- Supports streaming output to Streamlit

#### 2. **streamlit_app.py** — Web Interface
- New Research form (sidebar)
- Session history browser
- Real-time output streaming
- Report viewer (Markdown + raw)
- PDF browser with download
- Download reports as .md files

#### 3. **Session Structure**
```
research/
├── gut_microbiome_20260605_143022/
│   ├── session.json          (metadata)
│   ├── report.md             (final report)
│   └── papers/
│       ├── paper1.pdf
│       ├── paper2.pdf
│       └── ...
├── another_topic_20260605_150000/
│   ├── session.json
│   ├── report.md
│   └── papers/
│       └── ...
```

---

## 📚 Usage Examples

### Example 1: Research via Web Interface

1. **Open the app:**
   ```bash
   streamlit run streamlit_app.py
   ```

2. **Fill the form:**
   - Topic: "Quantum Computing Applications"
   - Question: "What are the most promising real-world applications of quantum computing?"
   - Focus Areas: 
     - Drug discovery and molecular simulation
     - Optimization problems
     - Cryptography and security
   - Depth: Comprehensive
   - Min Sources: 6

3. **Click "🚀 Start Research"**

4. **Watch real-time progress** as agent searches and downloads papers

5. **View final report** with all sources cited

6. **Browse PDFs** in right panel

### Example 2: Research via CLI

Edit `research_agent.py` main() function:

```python
goal = ResearchGoal(
    topic="Machine Learning Ethics",
    question="How can we build more fair and transparent AI systems?",
    focus_areas=[
        "Algorithmic bias detection",
        "Interpretability techniques",
        "Regulatory frameworks",
    ],
    depth="comprehensive",
    min_sources=6,
)
```

Then run:
```bash
python research_agent.py
```

---

## 🛠️ Technologies

| Technology | Purpose |
|-----------|---------|
| **Claude Agent SDK** | Core AI agent framework |
| **Anthropic Claude 3.5 Sonnet** | Language model for reasoning |
| **Tavily API** | Academic paper search |
| **Streamlit** | Web interface |
| **Python** | Backend logic |
| **asyncio** | Async operations |
| **Python-dotenv** | Environment variables |

---

## 📁 Project Structure

```
My_First_Agent/
├── research_agent.py          # Core agent engine
├── streamlit_app.py           # Web interface
├── requirements.txt           # Python dependencies
├── .env.example               # Template for API keys
├── .env                       # Your API keys (not committed)
├── .gitignore                 # Ignore sensitive files
├── README.md                  # This file
├── PROJECT_SETUP_GUIDE.md     # Step-by-step setup guide
├── CLAUDE.md                  # Claude context documentation
├── research/                  # Session data (auto-created)
│   ├── topic_20260605_143022/
│   │   ├── session.json
│   │   ├── report.md
│   │   └── papers/
│   └── ...
├── papers/                    # Legacy fallback (auto-created)
└── reports/                   # Legacy fallback (auto-created)
```

---

## 🚀 Deployment Options

### Local Development (Recommended for Testing)
```bash
streamlit run streamlit_app.py
```
- Runs on `http://localhost:8501`
- Full access to local API keys in `.env`
- Instant feedback during development

### Streamlit Cloud (Free Tier)
1. Push code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repo
4. Add API keys in **Secrets** tab:
   ```
   ANTHROPIC_API_KEY=your-key
   TAVILY_API_KEY=your-key
   ```
5. Deploy with one click

### Other Cloud Platforms
- **Railway** — Free tier available
- **Render** — Free tier available
- **Heroku** — Paid (free tier deprecated)

---

## 💰 Cost Estimates

**Free Resources:**
- Anthropic API: $5 free credits per new account
- Tavily API: 1,000 free searches/month
- Streamlit Cloud: Free tier available

**Per Research Session:**
- Typical cost: $0.50–$2.00 USD
- Depends on: search depth, PDF sizes, number of turns
- Most users can run 5–10 research sessions on free credits

---

## 🔑 API Setup

### Anthropic API Key

1. Visit [console.anthropic.com](https://console.anthropic.com)
2. Sign in or create account
3. Go to **API Keys**
4. Click **Create Key**
5. Copy key and add to `.env`:
   ```
   ANTHROPIC_API_KEY=sk-ant-v0-xxxxxxxxxxxx
   ```

### Tavily API Key

1. Visit [app.tavily.com](https://app.tavily.com)
2. Sign in or create account
3. Go to **API Keys**
4. Copy key and add to `.env`:
   ```
   TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxx
   ```

---

## 🎓 Learning Path

If you're new to this project:

1. **Read** [PROJECT_SETUP_GUIDE.md](PROJECT_SETUP_GUIDE.md) — Step-by-step guide from scratch
2. **Run** `streamlit run streamlit_app.py` — Test the interface
3. **Try** a simple research (e.g., "What is machine learning?")
4. **Explore** the generated `research/` folder structure
5. **Customize** the research goals in the code
6. **Build** your own agents for different domains

---

## 🔧 Customization

### Change the Model
In `research_agent.py`, line 35:
```python
MODEL = "claude-opus-4-1"  # Change to other available models
```

### Adjust Research Depth
- `depth="overview"` — Quick summary (3-4 turns)
- `depth="comprehensive"` — Balanced (6-8 turns)
- `depth="deep-dive"` — Thorough (10 turns)

### Add Focus Areas
In the web form or in `research_agent.py`:
```python
focus_areas=[
    "First topic to explore",
    "Second topic",
    "Third topic",
    # Add as many as needed
]
```

### Modify System Prompt
Change `AUTONOMOUS_SYSTEM_PROMPT` for different agent behavior:
```python
AUTONOMOUS_SYSTEM_PROMPT = """\
Your custom instructions here...
"""
```

---

## 🐛 Troubleshooting

### "Missing required env vars"
**Solution:** Create `.env` file with both API keys:
```
ANTHROPIC_API_KEY=your-key
TAVILY_API_KEY=your-key
```

### "No PDFs downloading"
**Causes:**
- Some publishers block automated access
- Poor search query (try more specific)
- Network timeout (try again)

**Solution:** Check Tavily search results in console output

### "Streamlit app won't start"
**Solution:** Install streamlit:
```bash
pip install streamlit
```

### "API key not working"
**Solution:**
1. Verify keys are correct in `.env`
2. Check API quotas at respective dashboards
3. Ensure keys haven't expired

---

## 📊 Example Output

### Session Metadata
```json
{
  "session_id": "machine_learning_ethics_20260605_143022",
  "topic": "Machine Learning Ethics",
  "question": "How can we build fair AI systems?",
  "status": "complete",
  "paper_count": 7,
  "source_count": 6,
  "created_at": "2026-06-05T14:30:22.123456"
}
```

### Report Structure
```markdown
# Machine Learning Ethics

**Research question:** How can we build fair AI systems?

**Generated:** 2026-06-05

---

## Executive Summary
[Agent's synthesis of key findings]

## Key Findings
[Detailed analysis with citations]

## Mechanistic Analysis
[How and why the findings matter]

## Conclusions
[Actionable insights]

---

## Sources
- [Paper 1](url)
- [Paper 2](url)
- ...
```

---

## 📞 Support & Next Steps

- **Setup Issues?** Read [PROJECT_SETUP_GUIDE.md](PROJECT_SETUP_GUIDE.md)
- **Want to Learn More?** Check [CLAUDE.md](CLAUDE.md) for architecture details
- **Found a Bug?** Create an issue with steps to reproduce

---

## 📝 License

This project uses the Claude Agent SDK from Anthropic and Tavily API.

---

## 🎉 You're All Set!

Your autonomous research agent is ready to go. Start researching with:

```bash
streamlit run streamlit_app.py
```

Happy researching! 🚀
