"""Offline relevance and answer checks."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from retrieval.nodes.relevance import evaluate_relevance
from retrieval.nodes.response import respond

CHUNK = {'metadata': {'title': 'HR guide', 'text': 'Full-time employees receive 18 days of annual leave.'}}


class AnswerTests(unittest.IsolatedAsyncioTestCase):
    async def call_model(self, module, function, state, output):
        client = AsyncMock()
        client.responses.create.return_value = SimpleNamespace(output_text=json.dumps(output))
        with patch(module + '.AsyncOpenAI') as factory, patch(module + '.load_dotenv'), patch(module + '.os.getenv', return_value='test-model'):
            factory.return_value.__aenter__ = AsyncMock(return_value=client)
            factory.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await function(state)
        return result

    async def test_select_only_relevant_chunk(self):
        result = await self.call_model('retrieval.nodes.relevance', evaluate_relevance,
            {'user_query': 'Annual leave?', 'candidates': [CHUNK, {'metadata': {'text': 'Reset a password'}}]},
            {'selected_indices': [0], 'feedback': 'Leave entitlement'})
        self.assertEqual(result['matches'], [CHUNK])

    async def test_invalid_relevance_reference(self):
        for indices in ([2], [-1], [True]):
            with self.assertRaises(ValueError):
                await self.call_model('retrieval.nodes.relevance', evaluate_relevance,
                    {'user_query': 'Leave?', 'candidates': [CHUNK]},
                    {'selected_indices': indices, 'feedback': 'Invalid'})

    async def test_answer_has_source(self):
        result = await self.call_model('retrieval.nodes.response', respond,
            {'user_query': 'Leave?', 'matches': [CHUNK]},
            {'answer': 'Full-time employees receive 18 days per year [1].', 'source_indices': [1]})
        self.assertIn('[1] HR guide', result['message'])
        self.assertEqual(result['status'], 'answered')

    async def test_invalid_answer_reference(self):
        with self.assertRaises(ValueError):
            await self.call_model('retrieval.nodes.response', respond,
                {'user_query': 'Leave?', 'matches': [CHUNK]},
                {'answer': '18 days [2]', 'source_indices': [2]})

    async def test_no_evidence_or_clarification_needs_no_api(self):
        with patch('retrieval.nodes.response.AsyncOpenAI') as factory:
            result = await respond({'user_query': 'Leave?', 'matches': []})
            self.assertEqual(result['status'], 'no_answer')
            result = await respond({'needs_clarification': True, 'clarification': 'Which department?'})
            self.assertEqual(result['message'], 'Which department?')
        factory.assert_not_called()
