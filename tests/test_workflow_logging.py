"""Offline checks that instrumentation preserves behavior and protects payloads."""
import unittest
from workflow_logging import logged_step


class LoggingTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_result_and_safe_counts(self):
        result = {'matches': [{'text': 'private document'}],
                  'message': 'private answer', 'status': 'answered'}

        @logged_step
        async def node(state):
            return result

        with self.assertLogs('rag.workflow', level='INFO') as logs:
            self.assertIs(await node({'user_query': 'private question'}), result)
        output = '\n'.join(logs.output)
        self.assertIn('started', output)
        self.assertIn('matches_count=1', output)
        self.assertIn('status=answered', output)
        self.assertIn('duration_ms=', output)
        self.assertNotIn('private', output)

    async def test_original_exception_is_preserved_without_payload(self):
        error = ValueError('private API payload')

        @logged_step
        async def node():
            raise error

        with self.assertLogs('rag.workflow', level='INFO') as logs:
            with self.assertRaises(ValueError) as caught:
                await node()
        self.assertIs(caught.exception, error)
        output = '\n'.join(logs.output)
        self.assertIn('error_type=ValueError', output)
        self.assertNotIn('private API payload', output)

    async def test_sync_routing(self):
        @logged_step
        def route(state):
            return 'respond'

        with self.assertLogs('rag.workflow', level='INFO') as logs:
            self.assertEqual(route({}), 'respond')
        self.assertIn('route=respond', '\n'.join(logs.output))
