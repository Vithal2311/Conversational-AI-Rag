"""Rewrite follow-up questions using conversation history."""
from workflow_logging import logged_step
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

from ..prompts.prompt import REWRITE_PROMPT


@logged_step
async def rewrite_query(state):
    # Read the user's question.
    user_query = state.get("user_query", "")
    if not isinstance(user_query, str):
        raise ValueError("user_query must be a string")
    if not user_query.strip():
        return {"query": "", "needs_clarification": True,
                "clarification": "What would you like to ask?"}

    # Load the API key and model from .env.
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    model = os.getenv("OPENAI_CHAT_MODEL", "").strip()
    if not model:
        raise ValueError("Set OPENAI_CHAT_MODEL in .env")

    # Ask the model to turn the question into a standalone search query.
    async with AsyncOpenAI(timeout=30.0, max_retries=1) as client:
        response = await client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": REWRITE_PROMPT},
                {"role": "user", "content": json.dumps({
                    "user_query": user_query,
                    "history": state.get("history", []),
                    "sources": state.get("sources", []),
                })},
            ],
            text={"format": {"type": "json_object"}},
            store=False,
        )

    # Read the JSON answer. Return only rewrite fields, preserving selected domains.
    result = json.loads(response.output_text)
    if not isinstance(result, dict) or not isinstance(result.get("query"), str):
        raise ValueError("The model returned an invalid rewritten query")
    if type(result.get("needs_clarification")) is not bool or not isinstance(result.get("clarification"), str):
        raise ValueError("The model returned invalid clarification fields")
    if result["needs_clarification"]:
        if not result["clarification"].strip():
            raise ValueError("A clarification question is required")
        result["query"] = ""
    elif not result["query"].strip() or result["clarification"].strip():
        raise ValueError("Expected a standalone query without a clarification question")
    return {
        "query": result["query"],
        "needs_clarification": result["needs_clarification"],
        "clarification": result["clarification"],
    }
