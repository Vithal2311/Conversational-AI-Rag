"""Shared state contract for the graph scaffold."""
from typing import Literal, TypedDict

Source = Literal["HR", "FINANCE", "IT_SUPPORT"]


class RetrievalState(TypedDict, total=False):
    user_query: str
    history: list[dict[str, str]]
    intent: Literal["HR", "FINANCE", "IT_SUPPORT", "MULTIPLE", "UNKNOWN"]
    sources: list[Source]
    query: str
    needs_clarification: bool
    clarification: str
    filters: dict[str, str]
    query_embedding: list[float]
    candidates: list[dict]
    matches: list[dict]
    feedback: str
    retry_count: int
    status: str
    message: str
