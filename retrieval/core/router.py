"""Conditional edges inspect node outputs; they do not call the LLM."""
from workflow_logging import logged_step
from typing import Literal
from .state import RetrievalState

MAX_RETRIES = 3


@logged_step
def route_intent(state: RetrievalState) -> Literal["rewrite_query", "respond"]:
    intent = state["intent"]
    if intent == "UNKNOWN":
        return "respond"
    if intent in {"HR", "FINANCE", "IT_SUPPORT", "MULTIPLE"}:
        if state.get("needs_clarification", False):
            return "respond"
        sources = state.get("sources", [])
        if not isinstance(sources, list) or any(
            source not in {"HR", "FINANCE", "IT_SUPPORT"} for source in sources
        ):
            raise ValueError("Unsupported retrieval sources")
        if not sources:
            return "respond"
        if (intent == "MULTIPLE" and len(set(sources)) < 2) or (
            intent != "MULTIPLE" and set(sources) != {intent}
        ):
            raise ValueError("Intent and selected sources do not match")
        return "rewrite_query"
    raise ValueError("Intent must identify HR, FINANCE, IT_SUPPORT, MULTIPLE or UNKNOWN")


@logged_step
def route_rewrite(state: RetrievalState) -> Literal["embed_query", "respond"]:
    return "respond" if state["needs_clarification"] else "embed_query"


@logged_step
def route_relevance(state: RetrievalState) -> Literal["fallback", "respond"]:
    count = state.get("retry_count", 0)
    if type(count) is not int or count < 0:
        raise ValueError("retry_count must be a nonnegative integer")
    if state["matches"] or count >= MAX_RETRIES:
        return "respond"
    return "fallback"


@logged_step
def route_fallback(state: RetrievalState) -> Literal["embed_query", "respond"]:
    return "respond" if state["needs_clarification"] else "embed_query"
