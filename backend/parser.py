"""
parser.py — robust JSON extraction from LLM output.

Strategy:
  1. Try direct json.loads() — works if model is well-behaved
  2. Strip markdown fences (```json ... ```) and retry
  3. Find first { ... } block via regex and retry
  4. Return structured error if all strategies fail

This handles the common failure modes:
  - Model adds preamble before JSON
  - Model wraps in ```json fences
  - Model adds trailing commentary after JSON
"""

import json
import re
from typing import Optional


def extract_json(raw: str) -> Optional[dict]:
    """Try multiple strategies to extract valid JSON from LLM output."""

    # Strategy 1: direct parse
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        pass

    # Strategy 2: strip markdown code fences
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Strategy 3: find the first { ... } block (handles preamble/postamble)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def validate_analysis(data: dict) -> tuple[bool, list[str]]:
    """
    Validate that the parsed JSON has all required sections.
    Returns (is_valid, list_of_missing_fields).
    """
    required = ["score", "evidence", "kpiMapping", "gaps", "followUpQuestions"]
    missing = [field for field in required if field not in data]

    score_fields = ["value", "label", "band", "justification", "confidence"]
    if "score" in data:
        score_missing = [f for f in score_fields if f not in data.get("score", {})]
        missing.extend([f"score.{f}" for f in score_missing])

    return len(missing) == 0, missing


def parse_analysis(raw: str) -> dict:
    """
    Main entry point. Returns either a valid analysis dict or an error dict.
    """
    data = extract_json(raw)

    if data is None:
        return {
            "error": True,
            "message": "Could not extract valid JSON from model output. Try running again.",
            "raw": raw[:500]  # first 500 chars for debugging
        }

    is_valid, missing = validate_analysis(data)

    if not is_valid:
        return {
            "error": True,
            "message": f"Model output was missing required fields: {', '.join(missing)}",
            "partial": data,
            "raw": raw[:500]
        }

    # Normalize: ensure arrays are lists even if model returned single objects
    for key in ["evidence", "kpiMapping", "gaps", "followUpQuestions", "biasFlags"]:
        if key in data and not isinstance(data[key], list):
            data[key] = [data[key]]

    # Ensure biasFlags exists
    if "biasFlags" not in data:
        data["biasFlags"] = []

    return data
