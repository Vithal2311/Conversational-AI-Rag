"""Embed search queries using the same model as document ingestion."""
from workflow_logging import logged_step
from math import isfinite
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI


@logged_step
async def embed_query(state):
    query = state.get("query", "")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("A nonempty rewritten query is required for embedding")

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    async with AsyncOpenAI(timeout=30.0, max_retries=1) as client:
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=query,
            dimensions=1536,
        )

    if len(response.data) != 1:
        raise ValueError("Expected one query embedding")
    query_embedding = response.data[0].embedding
    if len(query_embedding) != 1536 or not all(
        type(value) in (int, float) and isfinite(value) for value in query_embedding
    ):
        raise ValueError("Expected a finite 1536-dimensional query embedding")
    return {"query_embedding": query_embedding}
