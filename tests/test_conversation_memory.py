"""Offline session isolation, persistence, expiry and orchestration tests."""
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import UUID

import boto3
from botocore.stub import Stubber
from botocore.exceptions import ClientError
from app.services.conversation_memory import ConversationMemory, SessionUnavailable
from app.services.chat import chat


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.table = MagicMock()
        self.table.name = 'memory'
        self.memory = ConversationMemory(self.table, clock=lambda: 1000)
        self.session_id = '8fe1e280-262a-47d6-a671-1fdd967b8860'
        self.table.get_item.return_value = {'Item': {
            'user_id': 'alice', 'revision': 2, 'expires_at': 2000}}

    def test_new_chats_get_unique_ids(self):
        first = self.memory.create_session('alice')
        second = self.memory.create_session('alice')
        UUID(first)
        self.assertNotEqual(first, second)
        self.assertEqual(self.table.put_item.call_args.kwargs['Item']['user_id'], 'alice')

    def test_ownership_and_expiry_checked_before_reading_messages(self):
        with self.assertRaises(SessionUnavailable):
            self.memory.load_history(self.session_id, 'bob')
        self.table.query.assert_not_called()
        self.table.get_item.return_value['Item']['expires_at'] = 1000
        with self.assertRaises(SessionUnavailable):
            self.memory.load_history(self.session_id, 'alice')
        self.table.query.assert_not_called()

    def test_history_paginates_and_restores_chronological_order(self):
        self.table.query.side_effect = [
            {'Items': [], 'LastEvaluatedKey': {'session_id': self.session_id, 'message_id': 'TURN#3'}},
            {'Items': [{'user_content': 'new question', 'assistant_content': 'new answer'},
                       {'user_content': 'old question', 'assistant_content': 'old answer'}]},
        ]
        history, revision = self.memory.load_history(self.session_id, 'alice')
        self.assertEqual([row['content'] for row in history],
                         ['old question', 'old answer', 'new question', 'new answer'])
        self.assertEqual(revision, 2)
        self.assertTrue(self.table.query.call_args.kwargs['ConsistentRead'])
        self.assertFalse(self.table.query.call_args.kwargs['ScanIndexForward'])

    def test_atomic_save_checks_owner_expiry_and_revision(self):
        self.memory.save_turn(self.session_id, 'alice', 'question', 'answer', 2)
        operations = self.table.meta.client.transact_write_items.call_args.kwargs['TransactItems']
        self.assertIn('revision = :revision', operations[0]['Update']['ConditionExpression'])
        self.assertEqual(operations[0]['Update']['ExpressionAttributeValues'][':user'], 'alice')
        self.assertEqual(operations[1]['Put']['Item']['message_id'], 'TURN#00000000000000000003')
        self.assertEqual(operations[1]['Put']['Item']['assistant_content'], 'answer')

    def test_conflicting_save_is_reported(self):
        self.table.meta.client.transact_write_items.side_effect = ClientError(
            {'Error': {'Code': 'TransactionCanceledException'}}, 'TransactWriteItems')
        with self.assertRaises(SessionUnavailable):
            self.memory.save_turn(self.session_id, 'alice', 'question', 'answer', 2)

    def test_real_sdk_transaction_serialization_without_network(self):
        resource = boto3.resource('dynamodb', region_name='us-east-1',
                                  aws_access_key_id='testing', aws_secret_access_key='testing')
        table = resource.Table('memory')
        with Stubber(table.meta.client) as stub:
            stub.add_response('transact_write_items', {})
            ConversationMemory(table, clock=lambda: 1000).save_turn(
                self.session_id, 'alice', 'question', 'answer', 2)
            stub.assert_no_pending_responses()


class ChatTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_chat_graph_returns_no_answer_without_unfinished_fallback(self):
        from retrieval.core import graph as graph_module

        async def intent(state):
            return {'intent': 'HR', 'sources': ['HR'], 'needs_clarification': False}

        async def rewrite(state):
            return {'query': state['user_query'], 'needs_clarification': False}

        async def embed(state):
            return {'query_embedding': [0.0]}

        async def search(state):
            return {'candidates': []}

        async def relevance(state):
            return {'matches': [], 'feedback': 'No evidence'}

        with patch.multiple(graph_module, detect_intent=intent, rewrite_query=rewrite,
                            embed_query=embed, query_pinecone=search, evaluate_relevance=relevance):
            result = await graph_module.build_graph(enable_fallback=False).ainvoke(
                {'user_query': 'Annual leave?', 'history': []})
        self.assertEqual(result['status'], 'no_answer')

    async def test_followup_uses_session_history_and_saves_clarification(self):
        memory = MagicMock()
        history = [{'role': 'user', 'content': 'annual leave'}]
        memory.load_history.return_value = (history, 3)
        graph = MagicMock()
        graph.ainvoke = AsyncMock(return_value={'message': 'Which year?', 'status': 'clarification'})
        result = await chat('Can I carry it forward?', user_id='alice', session_id='existing',
                            memory=memory, graph=graph)
        memory.create_session.assert_not_called()
        self.assertEqual(graph.ainvoke.call_args.args[0]['history'], history)
        memory.save_turn.assert_called_once_with('existing', 'alice', 'Can I carry it forward?', 'Which year?', 3)
        self.assertEqual(result['session_id'], 'existing')

    async def test_graph_failure_does_not_save_partial_exchange(self):
        memory = MagicMock()
        memory.create_session.return_value = 'new'
        memory.load_history.return_value = ([], 0)
        graph = MagicMock()
        graph.ainvoke = AsyncMock(side_effect=RuntimeError('failed'))
        with self.assertRaises(RuntimeError):
            await chat('question', user_id='alice', memory=memory, graph=graph)
        memory.create_session.assert_called_once_with('alice')
        memory.save_turn.assert_not_called()
