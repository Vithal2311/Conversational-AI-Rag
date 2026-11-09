# Retrieval scaffold

`core/graph.py` registers nodes and edges. `core/router.py` routes from node
outputs, allowing at most three repaired searches after the initial retrieval.
`core/state.py` defines shared state. `nodes/` owns each workflow step and its
reasoning call. `services/embeddings.py` and
`services/vector_store.py` provide external integrations. `prompts/` holds prompt
templates. Tests live in the project-root `tests/` directory.

Flow: detect_intent -> rewrite_query -> embed_query ->
query_pinecone -> evaluate_relevance -> respond. Intent detection finalizes
sources as HR, FINANCE, IT_SUPPORT or a combination. Unresolved source selection
asks for clarification. Sources constrain retrieval and stay fixed during fallback.
Conditional edges handle clarification and fallback -> embed_query.

Domain detection calls OpenAI directly from nodes/intent.py and reads JSON output. Set
OPENAI_API_KEY and OPENAI_CHAT_MODEL in the project .env (choose a model that
supports JSON output). IT Helpdesk uses the internal value IT_SUPPORT.
The node reads user_query and optional history, returning intent, sources,
needs_clarification and clarification. Empty questions request clarification
without calling the model; API failures propagate rather than guessing a domain.
Query rewriting is implemented in nodes/rewrite.py with a direct LLM call.
It uses user_query, history and selected sources to return query,
needs_clarification and clarification. It never updates the selected domains.
Unclear follow-ups request clarification rather than inventing context.
Query embedding uses text-embedding-3-small with 1536 dimensions, matching ingestion.
It embeds the rewritten query and returns vector. Metadata extraction is bypassed.
Pinecone search targets only selected domain namespaces and returns stored chunk text.
Relevance checking selects useful chunks with an LLM; response generation uses those
chunks to write an answer with source references. Empty results produce a no-answer
message. The graph's query-repair fallback is still unimplemented.

Run the implemented steps, without fallback retries, from the project root:

```powershell
python scripts/test_retrieval.py "How many annual leave days do I get?"
```
Call the first node independently while the rest of the graph is being built:

```python
import asyncio
from retrieval.nodes.intent import detect_intent

result = asyncio.run(detect_intent({"user_query": "How do I reset my password?"}))
print(result)
```

Domain and rewrite prompts live in prompts/prompt.py. There is no separate LLM service or schema class.

No clients are created and no API calls occur on import or graph construction.

