"""Run a new or existing chat backed by DynamoDB session memory."""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.chat import chat


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query')
    parser.add_argument('--user-id', required=True, help='Local user identity; an API must use authenticated identity')
    parser.add_argument('--session-id', help='Omit to start a new chat')
    args = parser.parse_args()
    result = await chat(args.query, user_id=args.user_id, session_id=args.session_id)
    print('Session:', result['session_id'])
    print(result['message'])


if __name__ == '__main__':
    asyncio.run(main())
