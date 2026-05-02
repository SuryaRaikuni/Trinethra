# Trinethra — Supervisor Feedback Analyzer

An AI-assisted tool that analyzes supervisor call transcripts and produces structured Fellow performance assessments. Built for DeepThought's psychology intern team.

---

## What It Does

Paste a supervisor transcript → click **Run Analysis** → get:
- **Score (1–10)** with label, band, justification, and confidence
- **Extracted Evidence** — quotes tagged positive/negative/neutral with bias-corrected interpretation
- **KPI Mapping** — which business outcomes the Fellow's work connects to
- **Coverage Gaps** — which assessment dimensions the transcript didn't cover
- **Follow-up Questions** — targeted questions for the next call

The UI labels everything as **"AI Draft"** — the intern reviews, not rubber-stamps.

---

## Setup (5 steps)

### 1. Install Ollama
Download from [ollama.com](https://ollama.com) and install.

### 2. Pull a model
```bash
ollama pull llama3.2
```
*(Or `mistral`, `phi3`, `gemma` — any model works. `llama3.2` recommended.)*

### 3. Start Ollama
```bash
ollama serve
```
Ollama runs at `http://localhost:11434`. Keep this terminal open.

### 4. Install Python dependencies and start backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 5. Open the app
Visit **http://localhost:8000** in your browser.

That's it. The frontend is served by the backend — no separate server needed.

---

## Model Choice

**Using: `llama3.2` (3B parameters)**

Why:
- Runs on most laptops (8 GB RAM minimum)
- Strong instruction-following for structured JSON output
- Fast enough for a 10-minute transcript (30-60 seconds on CPU)
- Free, local, no API key

Alternative: `mistral` (7B) gives better analysis quality but needs 12+ GB RAM and is slower.

The model dropdown in the UI lets you switch between any installed model without restarting.

---

## Architecture

```
Browser (index.html)
    │
    │  POST /analyze  { transcript, model }
    ▼
FastAPI (main.py) — serves frontend + API
    │
    │  POST http://localhost:11434/api/generate
    ▼
Ollama (llama3.2 running locally)
    │
    │  { response: "...JSON..." }
    ▼
parser.py — extracts JSON with 3-strategy fallback
    │
    ▼
Frontend renders 5-section analysis
```

- **No database** — stateless, everything in memory per request
- **No auth** — internal tool, localhost only
- **No deployment** — runs entirely on the intern's machine

---

## Design Challenges Tackled

### Challenge 2: Structured Output Reliability

LLMs don't always return clean JSON. My approach (in `parser.py`):
1. Direct `json.loads()` — works when model is well-behaved
2. Strip markdown fences (` ```json ``` `) and retry
3. Regex-extract the first `{...}` block and retry (handles preamble/postamble)
4. If all fail → return structured error to the UI with the raw output for debugging

In the prompt, I explicitly say: *"Respond ONLY with valid JSON. No preamble. No markdown fences. No commentary."* I also set `temperature: 0.1` to reduce randomness in output format.

### Challenge 5: Gap Detection

Detecting what a transcript *doesn't say* is harder than extracting what it does say. My approach:

The system prompt lists all 4 assessment dimensions explicitly and instructs the model:
> *"For each dimension, determine whether the supervisor provided evidence. If a dimension has no evidence, include it in the gaps array with a specific explanation of what's missing and why it matters."*

This forces the model to reason about absence, not just presence. It also prevents the common failure of the model only listing gaps for things it noticed were missing — instead it reasons over a fixed checklist.

Additionally, I injected 5 named bias patterns (helpfulness bias, presence bias, halo effect, recency bias, task absorption trap) into the system prompt with concrete examples. This directly addresses the 3 "trap" transcripts in the sample data.

---

## Testing with Sample Transcripts

The UI has 3 sample transcript buttons. Expected scores:

| Fellow | Expected | Trap the model must avoid |
|--------|----------|--------------------------|
| Karthik | 6–7 | Don't score 8+ just because supervisor is positive |
| Meena | 7–8 | Don't score 4 just because supervisor uses presence bias |
| Anil | 5–6 | Don't score 9 just because supervisor is glowing |

If your model scores incorrectly, iterate on `prompt.py` — specifically the bias warnings section.

---

## What I'd Improve With More Time

1. **Side-by-side view** — split panel showing transcript on left, analysis on right, so intern can cross-reference quotes with source text while reviewing
2. **Editable output** — each evidence card and score should be inline-editable, with a "finalize" button that exports a clean PDF summary
3. **Transcript highlighting** — clicking a quote in the evidence section should scroll to and highlight that sentence in the transcript view
4. **Session persistence** — save the analysis to localStorage so the intern can refresh without losing work
5. **Model comparison mode** — run the same transcript through two models and show results side by side to detect where models disagree

---

## Project Structure

```
trinethra/
├── backend/
│   ├── main.py          # FastAPI: routes, Ollama integration
│   ├── prompt.py        # System prompt with rubric + KPIs baked in
│   ├── parser.py        # JSON extraction with 3-strategy fallback
│   └── requirements.txt
├── frontend/
│   └── index.html       # Single-file UI (all HTML/CSS/JS)
├── data/
│   ├── rubric.json          # 1-10 rubric as structured data
│   └── sample-transcripts.json  # 3 test transcripts
└── README.md
```

---

## Assumptions Made

- Intern is running this on a laptop with at least 8 GB RAM
- Ollama is already installed (per assignment guidelines)
- The tool is for internal use only — no auth, no rate limiting
- "Clean and functional" UI is the target, not visual polish (per assignment spec)
