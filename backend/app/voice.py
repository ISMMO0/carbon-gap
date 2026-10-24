"""Voice mode: speech-to-text with OpenAI, spoken answers with ElevenLabs (streamed)."""
import os
from collections.abc import Iterator

import httpx

from .agent import client

STT_MODEL = "gpt-4o-transcribe"
VOICE_ID = "EXAVITQu4vr4xnSDxMaL"  # ElevenLabs "Sarah", same voice as the film
TTS_MODEL = "eleven_flash_v2_5"     # lowest latency


def transcribe(audio: bytes, filename: str) -> str:
    r = client.audio.transcriptions.create(
        model=STT_MODEL, file=(filename, audio),
        prompt="Carbon Gap, emissions, UNFCCC, Climate TRACE, MtCO2e, EU ETS, CBAM, country names.")
    return r.text.strip()


def speak(text: str) -> Iterator[bytes]:
    """Stream MP3 audio from ElevenLabs as it is generated."""
    with httpx.stream(
        "POST", f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream",
        params={"output_format": "mp3_44100_128", "optimize_streaming_latency": 3},
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
        json={"text": text, "model_id": TTS_MODEL,
              "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.2}},
        timeout=60,
    ) as r:
        r.raise_for_status()
        yield from r.iter_bytes()
