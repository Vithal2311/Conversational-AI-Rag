"""Run a live query and print the answer with document sources."""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from retrieval.core.router import route_intent, route_rewrite
from retrieval.nodes.intent import detect_intent
from retrieval.nodes.rewrite import rewrite_query
from retrieval.nodes.embedding import embed_query
from retrieval.nodes.pinecone import query_pinecone
from retrieval.nodes.relevance import evaluate_relevance
from retrieval.nodes.response import respond


async def main(query):
    state = {'user_query': query, 'history': []}
    print('Searching documents and preparing your answer...', flush=True)
    state.update(await detect_intent(state))
    if route_intent(state) != 'respond':
        state.update(await rewrite_query(state))
        if route_rewrite(state) != 'respond':
            state.update(await embed_query(state))
            state.update(await query_pinecone(state))
            state.update(await evaluate_relevance(state))
    state.update(await respond(state))
    print('\n' + state['message'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query', help='Your question')
    args = parser.parse_args()
    asyncio.run(main(args.query))
