"""LangGraph structure only. Node implementations are the next step."""
from workflow_logging import logged_step
from langgraph.graph import END, START, StateGraph

from ..nodes import (
    detect_intent, rewrite_query, embed_query,
    query_pinecone, evaluate_relevance, fallback, respond,
)
from .router import route_intent, route_rewrite, route_relevance, route_fallback
from .state import RetrievalState


@logged_step
def build_graph(*, enable_fallback=True):
    builder = StateGraph(RetrievalState)

    builder.add_node("detect_intent", detect_intent)
    builder.add_node("rewrite_query", rewrite_query)
    builder.add_node("embed_query", embed_query)
    builder.add_node("query_pinecone", query_pinecone)
    builder.add_node("evaluate_relevance", evaluate_relevance)
    builder.add_node("fallback", fallback)
    builder.add_node("respond", respond)

    builder.add_edge(START, "detect_intent")
    builder.add_conditional_edges("detect_intent", route_intent, {
        "rewrite_query": "rewrite_query", "respond": "respond",
    })
    builder.add_conditional_edges("rewrite_query", route_rewrite, {
        "embed_query": "embed_query", "respond": "respond",
    })
    builder.add_edge("embed_query", "query_pinecone")
    builder.add_edge("query_pinecone", "evaluate_relevance")
    if enable_fallback:
        builder.add_conditional_edges("evaluate_relevance", route_relevance, {
            "fallback": "fallback", "respond": "respond",
        })
    else:
        builder.add_edge("evaluate_relevance", "respond")
    builder.add_conditional_edges("fallback", route_fallback, {
        "embed_query": "embed_query", "respond": "respond",
    })
    builder.add_edge("respond", END)
    return builder.compile()
