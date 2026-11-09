"""Load session memory, invoke retrieval, then persist the completed exchange."""
import asyncio

from workflow_logging import logged_step
from .conversation_memory import ConversationMemory


@logged_step
async def chat(user_query, *, user_id, session_id=None, memory=None, graph=None):
    if not isinstance(user_query, str) or not user_query.strip():
        raise ValueError('A nonempty question is required')
    memory = memory if memory is not None else ConversationMemory.from_env()
    if session_id is None:
        session_id = await asyncio.to_thread(memory.create_session, user_id)
    history, revision = await asyncio.to_thread(memory.load_history, session_id, user_id)
    if graph is None:
        from retrieval.core.graph import build_graph
        # Query repair is still unfinished; an empty search returns no_answer.
        graph = build_graph(enable_fallback=False)
    result = await graph.ainvoke({'user_query': user_query, 'history': history})
    await asyncio.to_thread(memory.save_turn, session_id, user_id, user_query,
                            result['message'], revision)
    return {'session_id': session_id, 'message': result['message'], 'status': result['status']}
