"""Console logging for workflow steps without recording user or document text."""
import inspect
import logging
import os
from functools import wraps
from time import perf_counter
from uuid import uuid4
from contextvars import ContextVar

_run_id = ContextVar('workflow_run_id', default='-')
logger = logging.getLogger('rag.workflow')


def configure_logging():
    """Configure only our logger; leave SDK and application loggers alone."""
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s %(name)s %(message)s'))
        logger.addHandler(handler)
        logger.propagate = False
    level = os.getenv('LOG_LEVEL', 'INFO').upper()
    logger.setLevel(getattr(logging, level, logging.INFO)
                    if level in {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
                    else logging.INFO)


def _summary(result):
    if isinstance(result, str) and result in {'respond', 'rewrite_query', 'embed_query', 'fallback'}:
        # Used only for the fixed graph routing destinations.
        return ' route=' + result
    if not isinstance(result, dict):
        return ''
    fields = []
    for key, allowed in (
        ('intent', {'HR', 'FINANCE', 'IT_SUPPORT', 'MULTIPLE', 'UNKNOWN'}),
        ('status', {'clarification', 'no_answer', 'answered'}),
    ):
        value = result.get(key)
        if isinstance(value, str) and value in allowed:
            fields.append(f'{key}={value}')
    sources = result.get('sources')
    if isinstance(sources, list) and all(
        isinstance(value, str) and value in {'HR', 'FINANCE', 'IT_SUPPORT'}
        for value in sources
    ):
        fields.append('sources=' + ','.join(sources))
    for key in ('needs_clarification', 'retry_count'):
        value = result.get(key)
        if type(value) in (bool, int):
            fields.append(f'{key}={value}')
    for key in ('candidates', 'matches', 'query_embedding'):
        if isinstance(result.get(key), list):
            fields.append(f'{key}_count={len(result[key])}')
    return ' ' + ' '.join(fields) if fields else ''


def logged_step(function):
    """Log start, duration and safe counts; preserve exceptions and signatures."""
    step = function.__module__ + '.' + function.__name__

    def begin(args):
        configure_logging()
        token = None
        if _run_id.get() == '-':
            token = _run_id.set(uuid4().hex[:12])
        started = perf_counter()
        summary = _summary(args[0]) if args and isinstance(args[0], dict) else ''
        logger.info('run=%s step=%s started%s', _run_id.get(), step, summary)
        return token, started

    def finish(token, started, result=None, error=None):
        try:
            if error is None:
                logger.info('run=%s step=%s completed duration_ms=%.1f%s',
                            _run_id.get(), step, (perf_counter() - started) * 1000,
                            _summary(result))
            else:
                # Exception messages can contain API payloads or credentials.
                logger.error('run=%s step=%s failed duration_ms=%.1f error_type=%s',
                             _run_id.get(), step, (perf_counter() - started) * 1000,
                             type(error).__name__)
        finally:
            if token is not None:
                _run_id.reset(token)

    if inspect.iscoroutinefunction(function):
        @wraps(function)
        async def async_wrapper(*args, **kwargs):
            token, started = begin(args)
            try:
                result = await function(*args, **kwargs)
            except BaseException as error:
                finish(token, started, error=error)
                raise
            finish(token, started, result=result)
            return result
        return async_wrapper

    @wraps(function)
    def wrapper(*args, **kwargs):
        token, started = begin(args)
        try:
            result = function(*args, **kwargs)
        except BaseException as error:
            finish(token, started, error=error)
            raise
        finish(token, started, result=result)
        return result
    return wrapper
