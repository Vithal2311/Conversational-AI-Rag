from workflow_logging import logged_step
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


@logged_step
def embed_chunks(chunks):
    if not chunks:
        return []

    env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(env_path)

    with OpenAI(timeout=30.0, max_retries=1) as client:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=chunks,
            dimensions=1536,
        )

    return [
        item.embedding
        for item in sorted(response.data, key=lambda item: item.index)
    ]
