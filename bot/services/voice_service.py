import io
import logging
from openai import AsyncOpenAI

from bot.config import settings

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=settings.openai_api_key)


async def transcribe_voice(ogg_bytes: bytes) -> str:
    """Transcribe voice message using Whisper API."""
    audio_file = io.BytesIO(ogg_bytes)
    audio_file.name = "voice.ogg"

    transcript = await client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        language="ru",
    )

    return transcript.text
