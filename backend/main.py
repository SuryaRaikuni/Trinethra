"""
main.py — FastAPI backend for Trinethra Supervisor Feedback Analyzer.

Endpoints:
  GET  /            → health check
  POST /analyze     → run transcript through Ollama, return structured analysis
  GET  /samples     → return sample transcripts for demo/testing
  GET  /model-check → check if Ollama is running and which models are available
"""

import json
import os
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from prompt import SYSTEM_PROMPT, build_user_message
from parser import parse_analysis

# ── Config ──────────────────────────────────────────────────────────────────
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

app = FastAPI(title="Trinethra — Supervisor Feedback Analyzer", version="1.0.0")

# Allow frontend (served from same origin or dev server) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the frontend
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


# ── Models ───────────────────────────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    transcript: str
    model: str = OLLAMA_MODEL  # allow frontend to override model


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/")
def serve_frontend():
    return FileResponse(os.path.join(frontend_dir, "index.html"))


@app.get("/health")
def health():
    return {"status": "ok", "model": OLLAMA_MODEL}


@app.get("/model-check")
def model_check():
    """Check if Ollama is reachable and list available models."""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        return {"ollama_running": True, "models": models}
    except Exception as e:
        return {"ollama_running": False, "error": str(e), "models": []}


@app.get("/samples")
def get_samples():
    """Return sample transcripts for demo use."""
    path = os.path.join(DATA_DIR, "sample-transcripts.json")
    with open(path) as f:
        data = json.load(f)
    # Return stripped version (just what the frontend needs)
    return [
        {
            "id": t["id"],
            "fellowName": t["fellow"]["name"],
            "company": t["company"]["name"],
            "supervisorRole": t["supervisor"]["role"],
            "transcript": t["transcript"],
            "expectedScoreRange": t.get("expectedScoreRange", [])
        }
        for t in data["transcripts"]
    ]


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    """
    Main endpoint: send transcript to Ollama, parse structured analysis, return it.

    Flow:
      1. Validate transcript is not empty
      2. Build prompt (system prompt with rubric + KPIs baked in)
      3. Call Ollama API
      4. Parse JSON from response (with fallback strategies)
      5. Return structured analysis or error
    """
    transcript = req.transcript.strip()
    if not transcript:
        raise HTTPException(status_code=400, detail="Transcript cannot be empty.")
    if len(transcript) < 100:
        raise HTTPException(status_code=400, detail="Transcript too short. Please paste the full supervisor call transcript.")

    # Build the prompt
    user_message = build_user_message(transcript)

    # Full prompt = system + user (Ollama's generate endpoint uses a single "prompt" field)
    full_prompt = f"{SYSTEM_PROMPT}\n\n{user_message}"

    # Call Ollama
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": req.model,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,   # low temp for consistent structured output
                    "top_p": 0.9,
                    "num_predict": 4096   # enough for full JSON response
                }
            },
            timeout=120  # local models can be slow
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to Ollama. Make sure Ollama is running: `ollama serve`"
        )
    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=504,
            detail="Ollama took too long to respond. Try a smaller model or shorter transcript."
        )
    except requests.exceptions.HTTPError as e:
        if response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Model '{req.model}' not found. Pull it first: `ollama pull {req.model}`"
            )
        raise HTTPException(status_code=500, detail=f"Ollama error: {str(e)}")

    raw_response = response.json().get("response", "")

    if not raw_response:
        raise HTTPException(status_code=500, detail="Ollama returned an empty response.")

    # Parse the JSON from the model's output
    analysis = parse_analysis(raw_response)

    return {
        "analysis": analysis,
        "model": req.model,
        "rawLength": len(raw_response)
    }
