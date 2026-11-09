"""Search the namespaces selected by domain detection."""
from workflow_logging import logged_step
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from pinecone import Pinecone

NAMESPACES = {'HR': 'hr', 'FINANCE': 'finance', 'IT_SUPPORT': 'it'}


@logged_step
def _search(query_embedding, sources):
    load_dotenv(Path(__file__).resolve().parents[2] / '.env')
    candidates = []
    with Pinecone(api_key=os.environ['PINECONE_API_KEY']) as pc:
        description = pc.describe_index(os.environ['PINECONE_INDEX_NAME'])
        with pc.Index(host=description.host) as index:
            for source in dict.fromkeys(sources):
                namespace = NAMESPACES[source]
                result = index.query(vector=query_embedding, namespace=namespace, top_k=5,
                                     include_metadata=True, include_values=False, timeout=30)
                for match in result.matches:
                    metadata = match.metadata or {}
                    if metadata.get('text', '').strip():
                        candidates.append({'id': match.id, 'namespace': namespace,
                                           'score': match.score, 'metadata': metadata})
    return {'candidates': sorted(candidates, key=lambda item: item['score'], reverse=True)}


@logged_step
async def search(state):
    sources = state.get('sources', [])
    if not isinstance(sources, list) or not sources or any(source not in NAMESPACES for source in sources):
        raise ValueError('Valid selected domains are required for search')
    return await asyncio.to_thread(_search, state['query_embedding'], sources)
