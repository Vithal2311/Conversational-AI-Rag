"""Generate an answer grounded in relevant chunks."""
from workflow_logging import logged_step
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import AsyncOpenAI
from ..prompts.prompt import RESPONSE_PROMPT


@logged_step
async def respond(state):
    if state.get('needs_clarification'):
        return {'message': state['clarification'], 'status': 'clarification'}
    matches = state.get('matches', [])
    if not matches:
        return {'message': "I couldn't find an answer in the available documents. Please contact the relevant HR, Finance or IT Helpdesk team.",
                'status': 'no_answer'}
    load_dotenv(Path(__file__).resolve().parents[2] / '.env')
    model = os.getenv('OPENAI_CHAT_MODEL', '').strip()
    if not model:
        raise ValueError('Set OPENAI_CHAT_MODEL in .env')
    chunks = [{'reference': i, 'title': item['metadata'].get('title', 'Document'),
               'text': item['metadata']['text']} for i, item in enumerate(matches, start=1)]
    async with AsyncOpenAI(timeout=30.0, max_retries=1) as client:
        response = await client.responses.create(
            model=model,
            input=[{'role': 'system', 'content': RESPONSE_PROMPT},
                   {'role': 'user', 'content': json.dumps({
                       'question': state['user_query'], 'standalone_query': state.get('query'),
                       'chunks': chunks})}],
            text={'format': {'type': 'json_object'}}, store=False)
    result = json.loads(response.output_text)
    if not isinstance(result, dict) or not isinstance(result.get('answer'), str) or not result['answer'].strip():
        raise ValueError('Invalid answer from model')
    indices = result.get('source_indices')
    if not isinstance(indices, list) or any(type(i) is not int or not 1 <= i <= len(matches) for i in indices):
        raise ValueError('Invalid answer sources from model')
    sources = [f"[{i}] {matches[i - 1]['metadata'].get('title', 'Document')}"
               for i in dict.fromkeys(indices)]
    message = result['answer'].strip()
    if sources:
        message += '\n\nSources:\n' + '\n'.join(sources)
    return {'message': message, 'status': 'answered' if sources else 'no_answer'}
