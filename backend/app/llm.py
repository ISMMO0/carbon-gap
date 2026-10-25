"""Shared OpenAI call for the agents, retried with backoff when many agents run at once (rate limits)."""
import asyncio
import os

import openai
from openai import AsyncOpenAI

# One model for every text feature; set OPENAI_MODEL to switch (e.g. gpt-5.5 for best quality, a mini model for cost).
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")

_client: AsyncOpenAI | None = None


async def respond(**kwargs):
    global _client
    _client = _client or AsyncOpenAI()
    for attempt in range(5):
        try:
            return await _client.responses.create(**kwargs)
        except (openai.RateLimitError, openai.APIConnectionError, openai.InternalServerError):
            if attempt == 4:
                raise
            await asyncio.sleep(3 * 2 ** attempt)
