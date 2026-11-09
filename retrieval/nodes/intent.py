"""Detect the user's domain. The prompt and model call are kept in this file."""
from workflow_logging import logged_step
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

from ..prompts.prompt import INTENT_PROMPT


@logged_step
async def detect_intent(state):
    # Read the user's question.
    user_query = state.get("user_query", "")
    if not isinstance(user_query, str):
        raise ValueError("user_query must be a string")
    if not user_query.strip():
        return {
            "intent": "UNKNOWN", "sources": [],
            "needs_clarification": True,
            "clarification": "What would you like help with: HR, IT Helpdesk, or Finance?",
        }

    # Load the API key and model name from .env.
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    model = os.getenv("OPENAI_CHAT_MODEL", "").strip()
    if not model:
        raise ValueError("Set OPENAI_CHAT_MODEL in .env")

    # Send the instructions and question to OpenAI.
    async with AsyncOpenAI(timeout=30.0, max_retries=1) as client:
        response = await client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": INTENT_PROMPT},
                {"role": "user", "content": json.dumps({
                    "user_query": user_query,
                    "history": state.get("history", []),
                })},
            ],
            text={"format": {"type": "json_object"}},
            store=False,
        )

    # Convert the model's JSON answer into a Python dictionary.
    result = json.loads(response.output_text)
    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object from domain detection")
    if result.get("intent") not in {"HR", "FINANCE", "IT_SUPPORT", "MULTIPLE", "UNKNOWN"}:
        raise ValueError("The model returned an unsupported domain")
    if not isinstance(result.get("sources"), list) or not all(
        isinstance(source, str) and source in {"HR", "FINANCE", "IT_SUPPORT"}
        for source in result["sources"]
    ):
        raise ValueError("The model returned invalid sources")
    if type(result.get("needs_clarification")) is not bool or not isinstance(result.get("clarification"), str):
        raise ValueError("The model returned invalid clarification fields")
    return result

