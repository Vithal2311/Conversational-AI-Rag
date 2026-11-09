"""Offline checks for domain detection; no OpenAI requests are sent."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from retrieval.core.graph import build_graph
from retrieval.core.router import route_intent
from retrieval.nodes.intent import detect_intent


class DomainTests(unittest.IsolatedAsyncioTestCase):
    async def run_detection(self, payload):
        client = AsyncMock()
        client.responses.create.return_value = SimpleNamespace(output_text=json.dumps(payload))
        with patch("retrieval.nodes.intent.AsyncOpenAI") as factory, patch(
            "retrieval.nodes.intent.os.getenv", return_value="test-model"
        ), patch("retrieval.nodes.intent.load_dotenv"):
            factory.return_value.__aenter__ = AsyncMock(return_value=client)
            factory.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await detect_intent({"user_query": "How do I request it?",
                                         "history": [{"role": "user", "content": "Annual leave"}]})
        self.assertIn("Annual leave", client.responses.create.call_args.kwargs["input"][1]["content"])
        return result

    async def test_domains(self):
        for domain in ("HR", "FINANCE", "IT_SUPPORT"):
            payload = dict(intent=domain, sources=[domain], needs_clarification=False, clarification="")
            self.assertEqual(await self.run_detection(payload), payload)
            self.assertEqual(route_intent(payload), "rewrite_query")

    async def test_empty_input(self):
        with patch("retrieval.nodes.intent.AsyncOpenAI") as factory:
            result = await detect_intent({"user_query": " "})
        factory.assert_not_called()
        self.assertEqual(route_intent(result), "respond")

    async def test_unknown(self):
        payload = dict(intent="UNKNOWN", sources=[], needs_clarification=True,
                       clarification="Which department can help?")
        self.assertEqual(await self.run_detection(payload), payload)
        self.assertEqual(route_intent(payload), "respond")

    async def test_multiple(self):
        payload = dict(intent="MULTIPLE", sources=["HR", "FINANCE"],
                       needs_clarification=False, clarification="")
        self.assertEqual(await self.run_detection(payload), payload)

    async def test_invalid_domain(self):
        with self.assertRaisesRegex(ValueError, "unsupported domain"):
            await self.run_detection({"intent": "OTHER"})

    def test_graph(self):
        edges = {(edge.source, edge.target) for edge in build_graph().get_graph().edges}
        self.assertIn(("__start__", "detect_intent"), edges)
        self.assertIn(("detect_intent", "rewrite_query"), edges)
