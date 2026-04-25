import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_group_message(text: str) -> None:
    url = f"{settings.evolution_api_url}/message/sendText/{settings.evolution_instance_name}"
    headers = {"apikey": settings.evolution_api_key}
    body = {"number": settings.group_jid, "text": text}

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, json=body, headers=headers)
        response.raise_for_status()
        logger.info("Message sent to group (%d chars)", len(text))
