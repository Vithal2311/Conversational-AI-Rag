"""Session-owned DynamoDB memory. AWS clients are created only on request."""
import os
import time
from pathlib import Path
from uuid import UUID, uuid4

from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from dotenv import load_dotenv

from workflow_logging import logged_step, logger


class SessionUnavailable(ValueError):
    """The session is missing, expired or belongs to another user."""


class ConversationMemory:
    def __init__(self, table, *, retention_days=7, history_turns=10, clock=time.time):
        if retention_days < 1 or not 1 <= history_turns <= 50:
            raise ValueError('Invalid retention or history limit')
        self.table = table
        self.retention_seconds = retention_days * 86400
        self.history_turns = history_turns
        self.clock = clock

    @classmethod
    def from_env(cls):
        import boto3
        from botocore.config import Config
        load_dotenv(Path(__file__).resolve().parents[2] / '.env')
        name = os.getenv('DYNAMODB_TABLE_NAME', '').strip()
        if not name:
            raise ValueError('Set DYNAMODB_TABLE_NAME in .env')
        resource = boto3.resource(
            'dynamodb', region_name=os.getenv('AWS_DEFAULT_REGION', 'ap-southeast-2'),
            config=Config(connect_timeout=10, read_timeout=30,
                          retries={'total_max_attempts': 2}))
        return cls(resource.Table(name))

    @logged_step
    def create_session(self, user_id):
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError('A trusted user_id is required')
        session_id = str(uuid4())
        now = int(self.clock())
        self.table.put_item(Item={
            'session_id': session_id, 'message_id': 'SESSION',
            'user_id': user_id, 'revision': 0, 'created_at': now,
            'expires_at': now + self.retention_seconds,
        }, ConditionExpression='attribute_not_exists(session_id)')
        return session_id

    def _session(self, session_id, user_id):
        try:
            UUID(session_id)
        except (ValueError, TypeError, AttributeError):
            raise SessionUnavailable('Session unavailable') from None
        item = self.table.get_item(
            Key={'session_id': session_id, 'message_id': 'SESSION'},
            ConsistentRead=True).get('Item')
        if not item or item['user_id'] != user_id or item['expires_at'] <= int(self.clock()):
            raise SessionUnavailable('Session unavailable')
        return item

    @logged_step
    def load_history(self, session_id, user_id):
        session = self._session(session_id, user_id)
        now = int(self.clock())
        turns = []
        options = dict(
            KeyConditionExpression=Key('session_id').eq(session_id) & Key('message_id').begins_with('TURN#'),
            FilterExpression=Attr('expires_at').gt(now),
            ScanIndexForward=False, ConsistentRead=True)
        while len(turns) < self.history_turns:
            response = self.table.query(**options, Limit=self.history_turns - len(turns))
            turns.extend(response.get('Items', []))
            if not response.get('LastEvaluatedKey'):
                break
            options['ExclusiveStartKey'] = response['LastEvaluatedKey']
        history = []
        for turn in reversed(turns):
            history.extend([{'role': 'user', 'content': turn['user_content']},
                            {'role': 'assistant', 'content': turn['assistant_content']}])
        logger.info('memory loaded turn_count=%d', len(turns))
        return history, int(session['revision'])

    @logged_step
    def save_turn(self, session_id, user_id, question, answer, revision):
        for content in (question, answer):
            if not isinstance(content, str) or not content.strip():
                raise ValueError('Messages must be nonempty strings')
            if len(content.encode('utf-8')) > 100_000:
                raise ValueError('Message exceeds memory size limit')
        now = int(self.clock())
        # The resource's client has DynamoDB's native-value transformation hooks.
        encode = dict
        # Atomic pair plus optimistic revision check prevents concurrent turns
        # generated from the same history from silently overwriting one another.
        try:
            self.table.meta.client.transact_write_items(TransactItems=[
                {'Update': {
                    'TableName': self.table.name,
                    'Key': encode({'session_id': session_id, 'message_id': 'SESSION'}),
                    'UpdateExpression': 'SET revision = :next, expires_at = :expiry',
                    'ConditionExpression': 'user_id = :user AND expires_at > :now AND revision = :revision',
                    'ExpressionAttributeValues': encode({
                        ':user': user_id, ':now': now, ':revision': revision,
                        ':next': revision + 1, ':expiry': now + self.retention_seconds}),
                }},
                {'Put': {'TableName': self.table.name,
                         'Item': encode({
                             'session_id': session_id,
                             'message_id': f'TURN#{revision + 1:020d}',
                             'user_content': question, 'assistant_content': answer,
                             'created_at': now, 'expires_at': now + self.retention_seconds}),
                         'ConditionExpression': 'attribute_not_exists(session_id)'}},
            ], ClientRequestToken=str(uuid4()))
        except ClientError as error:
            if error.response['Error']['Code'] == 'TransactionCanceledException':
                raise SessionUnavailable('Session expired, changed, or unavailable; reload before retrying') from error
            raise
