# Session conversation memory

Each new chat creates a UUID session ID. Continue the chat by sending the same
ID. `app.services.chat.chat()` loads its history, invokes the retrieval graph,
saves the completed user/assistant exchange atomically, and returns the answer
and session ID. Clarifications are saved too; failed graph calls are not saved.
No AI agent is involved in storage.

## Setup and use

Set `DYNAMODB_TABLE_NAME=company-chat-memory` in `.env` and configure AWS access
using the normal Boto3 credential chain. Create the table once:

```powershell
& .\.venv\Scripts\python.exe scripts/create_memory_table.py
```

Start a new chat:

```powershell
& .\.venv\Scripts\python.exe scripts/chat.py "How many annual leave days do I get?" --user-id local-user
```

Copy the session ID printed by the command to continue:

```powershell
& .\.venv\Scripts\python.exe scripts/chat.py "Can I carry them forward?" --user-id local-user --session-id YOUR_SESSION_ID
```

Omit `--session-id` to start another chat. The existing `scripts/test_retrieval.py`
remains a stateless retrieval diagnostic. The new chat command uses the real
LangGraph with fallback disabled until the query-repair node is implemented.

For a future HTTP endpoint, call the async service with the authenticated user's
ID, question and optional session ID. Obtain user identity from authentication,
not an arbitrary request-body user ID. The CLI's `--user-id` is for local use;
this project does not yet have an authentication layer or chat UI.

## Storage and retention

The DynamoDB table uses string partition key `session_id` and string sort key
`message_id`. A `SESSION` item owns the chat, tracks its revision and expiry.
Each `TURN#...` item stores one question and its answer together. Incrementing
revision numbers preserve exchange order. A transaction checks owner, expiry
and revision while inserting a turn and extending session expiry; concurrent
requests based on the same history cannot both commit. On a conflict, reload
history before retrying. Storage errors propagate, so unsaved answers are not
reported as successfully persisted.

Sessions expire after seven days without a successful exchange. Individual turns
are retained for seven days from creation. History loads the latest ten unexpired
turns (twenty messages), in chronological order. Thus this is a rolling memory
window, not indefinite transcript archival. These limits can be changed through
the `ConversationMemory` constructor. Long-history summarization is not included.

TTL on `expires_at` provides eventual physical cleanup. Application checks reject
expired sessions immediately and filter expired turns while paginating queries.
Wrong-owner, missing and expired sessions produce the same unavailable error.
Use a new chat after expiration. Logs include operations and counts, never text.

The setup identity needs DynamoDB DescribeTable, CreateTable (if absent),
DescribeTimeToLive and UpdateTimeToLive. Runtime access needs GetItem, Query,
PutItem and UpdateItem on this table, including the transaction's item operations.
No scans or table deletes are required. Existing tables with incompatible keys
or TTL configuration are rejected rather than modified.

`conversation_memory_iam_policy.json` contains a policy scoped to the configured
AWS account, region and table. An AWS administrator can grant it to the runtime
identity. The setup statement can be removed from a production runtime role
after provisioning. Table setup was attempted but AWS returned AccessDenied for
DescribeTable; live validation must be repeated after those permissions are granted.

Run the offline memory tests:

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_conversation_memory.py
```
