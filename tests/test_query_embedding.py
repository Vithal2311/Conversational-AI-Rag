"""Offline checks for query embedding and graph routing."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from retrieval.core.graph import build_graph
from retrieval.nodes.embedding import embed_query


class QueryEmbeddingTests(unittest.IsolatedAsyncioTestCase):
    async def run_embedding(self, data):
        client = AsyncMock()
        client.embeddings.create.return_value = SimpleNamespace(data=data)
        state = {"query": "How many annual leave days do I get?", "sources": ["HR"]}
        with patch("retrieval.services.embeddings.AsyncOpenAI") as factory, patch(
            "retrieval.services.embeddings.load_dotenv"
        ):
            factory.return_value.__aenter__ = AsyncMock(return_value=client)
            factory.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await embed_query(state)
        client.embeddings.create.assert_awaited_once_with(
            model="text-embedding-3-small", input=state["query"], dimensions=1536
        )
        self.assertEqual(state["sources"], ["HR"])
        return result

    async def test_rewritten_query_embedding(self):
        query_embedding = [0.1] * 1536
        self.assertEqual(await self.run_embedding([SimpleNamespace(embedding=query_embedding)]),
                         {"query_embedding": query_embedding})

    async def test_invalid_query_does_not_call_api(self):
        with patch("retrieval.services.embeddings.AsyncOpenAI") as factory:
            for query in (None, "", "   ", 42):
                with self.assertRaises(ValueError):
                    await embed_query({"query": query})
        factory.assert_not_called()

    async def test_invalid_api_response(self):
        for data in ([], [SimpleNamespace(embedding=[0.1])],
                     [SimpleNamespace(embedding=[float("nan")] * 1536)]):
            with self.assertRaises(ValueError):
                await self.run_embedding(data)

    async def test_api_failure_propagates(self):
        with patch("retrieval.services.embeddings.AsyncOpenAI") as factory, patch(
            "retrieval.services.embeddings.load_dotenv"
        ):
            client = AsyncMock()
            factory.return_value.__aenter__ = AsyncMock(return_value=client)
            factory.return_value.__aexit__ = AsyncMock(return_value=False)
            client.embeddings.create.side_effect = RuntimeError("API unavailable")
            with self.assertRaisesRegex(RuntimeError, "API unavailable"):
                await embed_query({"query": "Annual leave"})

    def test_graph_bypasses_metadata(self):
        edges = {(edge.source, edge.target) for edge in build_graph().get_graph().edges}
        self.assertIn(("rewrite_query", "embed_query"), edges)
        self.assertFalse(any("extract_metadata" in edge for edge in edges))
