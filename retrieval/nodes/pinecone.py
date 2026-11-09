from workflow_logging import logged_step
from ..services.vector_store import search


@logged_step
async def query_pinecone(state):
    return await search(state)
