from workflow_logging import logged_step
from ..services.embeddings import embed_query as run_embedding


@logged_step
async def embed_query(state):
    return await run_embedding(state)
