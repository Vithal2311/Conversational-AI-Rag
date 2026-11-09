"""Select retrieved chunks that help answer the question."""
from workflow_logging import logged_step, logger
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import AsyncOpenAI
from ..prompts.prompt import RELEVANCE_PROMPT


@logged_step
async def evaluate_relevance(state):
    candidates = state.get('candidates', [])
    if not candidates:
        return {'matches': [], 'feedback': 'No document text was retrieved.'}
    load_dotenv(Path(__file__).resolve().parents[2] / '.env')
    model = os.getenv('OPENAI_CHAT_MODEL', '').strip()
    if not model:
        raise ValueError('Set OPENAI_CHAT_MODEL in .env')
    chunks = [{'index': i, 'text': item['metadata']['text']}
              for i, item in enumerate(candidates)]
    async with AsyncOpenAI(timeout=30.0, max_retries=1) as client:
        response = await client.responses.create(
            model=model,
            input=[{'role': 'system', 'content': RELEVANCE_PROMPT},
                   {'role': 'user', 'content': json.dumps({
                       'question': state.get('query') or state['user_query'], 'chunks': chunks})}],
            text={'format': {
                'type': 'json_schema',
                'name': 'relevance_result',
                'strict': True,
                'schema': {
                    'type': 'object',
                    'properties': {
                        'selected_indices': {
                            'type': 'array',
                            'items': {'type': 'integer', 'minimum': 0,
                                      'maximum': len(candidates) - 1},
                        },
                        'feedback': {'type': 'string'},
                    },
                    'required': ['selected_indices', 'feedback'],
                    'additionalProperties': False,
                },
            }}, store=False)
    logger.info('step=%s.evaluate_relevance model_response=%r',
                __name__, response.output_text)
    try:
        result = json.loads(response.output_text)
    except json.JSONDecodeError:
        logger.error('step=%s.evaluate_relevance invalid_result reason=invalid_json',
                     __name__)
        raise
    indices = result.get('selected_indices') if isinstance(result, dict) else None
    problems = []
    if not isinstance(result, dict):
        problems.append('response must be a JSON object')
    else:
        if not isinstance(indices, list):
            problems.append('selected_indices must be a list')
        elif any(type(i) is not int or not 0 <= i < len(candidates) for i in indices):
            problems.append(f'selected_indices must contain integers from 0 to {len(candidates) - 1}')
        if not isinstance(result.get('feedback'), str):
            problems.append('feedback must be a string')
    if problems:
        reason = '; '.join(problems)
        logger.error('step=%s.evaluate_relevance invalid_result reason=%s',
                     __name__, reason)
        raise ValueError('Invalid relevance result from model: ' + reason)
    return {'matches': [candidates[i] for i in dict.fromkeys(indices)],
            'feedback': result['feedback']}
