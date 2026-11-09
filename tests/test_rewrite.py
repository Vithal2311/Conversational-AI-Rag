"""Offline rewrite and clarification checks."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from retrieval.core.router import route_rewrite
from retrieval.nodes.rewrite import rewrite_query


class RewriteTests(unittest.IsolatedAsyncioTestCase):
    async def run_rewrite(self, payload, query="Can I carry them forward?"):
        client = AsyncMock()
        client.responses.create.return_value = SimpleNamespace(output_text=json.dumps(payload))
        state = {"user_query": query, "history": [{"role": "user", "content": "Annual leave"}],
                 "sources": ["HR"], "intent": "HR"}
        with patch("retrieval.nodes.rewrite.AsyncOpenAI") as factory, patch(
            "retrieval.nodes.rewrite.os.getenv", return_value="test-model"
        ), patch("retrieval.nodes.rewrite.load_dotenv"):
            factory.return_value.__aenter__ = AsyncMock(return_value=client)
            factory.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await rewrite_query(state)
        self.assertEqual(state["sources"], ["HR"])
        self.assertIn("Annual leave", client.responses.create.call_args.kwargs["input"][1]["content"])
        return result

    async def test_follow_up_preserves_domain(self):
        result = await self.run_rewrite({"query": "Can I carry forward unused annual leave days?",
            "needs_clarification": False, "clarification": "", "sources": ["FINANCE"]})
        self.assertEqual(result["query"], "Can I carry forward unused annual leave days?")
        self.assertNotIn("sources", result)
        self.assertEqual(route_rewrite(result), "embed_query")

    async def test_standalone(self):
        query = "When is salary paid?"
        result = await self.run_rewrite({"query": query, "needs_clarification": False,
                                         "clarification": ""}, query=query)
        self.assertEqual(result["query"], query)

    async def test_clarification(self):
        result = await self.run_rewrite({"query": "", "needs_clarification": True,
                                         "clarification": "Which leave type do you mean?"})
        self.assertEqual(route_rewrite(result), "respond")

    async def test_invalid_output(self):
        for payload in ({"query": 3}, {"query": "", "needs_clarification": False, "clarification": ""},
                        {"query": "", "needs_clarification": True, "clarification": ""}):
            with self.assertRaises(ValueError):
                await self.run_rewrite(payload)

    async def test_empty_input(self):
        with patch("retrieval.nodes.rewrite.AsyncOpenAI") as factory:
            result = await rewrite_query({"user_query": " "})
        factory.assert_not_called()
        self.assertTrue(result["needs_clarification"])
