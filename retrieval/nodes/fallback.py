from workflow_logging import logged_step
@logged_step
async def fallback(state):
    """TODO: LLM repairs query, preserves sources/filters and increments retry_count.

    The graph permits three retrieval retries, or routes to clarification.
    """
    raise NotImplementedError("Fallback node pending implementation")
