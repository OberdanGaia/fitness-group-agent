import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.core.config import settings
from app.handlers.workout_handler import handle_incoming_message

logger = logging.getLogger(__name__)

RECOVERY_WINDOW_HOURS = 24


async def recover_missed_messages() -> None:
    logger.info("Starting missed message recovery (last %dh)...", RECOVERY_WINDOW_HOURS)
    try:
        messages = await _fetch_recent_messages()
    except Exception:
        logger.warning("Could not fetch message history from Evolution API — skipping recovery")
        return

    if not messages:
        logger.info("No recent messages found for recovery.")
        return

    cutoff = datetime.now(timezone.utc) - timedelta(hours=RECOVERY_WINDOW_HOURS)
    recovered = 0

    for msg in messages:
        try:
            ts = msg.get("messageTimestamp") or 0
            msg_time = datetime.fromtimestamp(int(ts), tz=timezone.utc)
            if msg_time < cutoff:
                continue

            remote_jid = (msg.get("key") or {}).get("remoteJid", "")
            if remote_jid != settings.group_jid:
                continue

            if (msg.get("key") or {}).get("fromMe", False):
                continue

            # Wrap in the same payload format the webhook handler expects
            payload = {"event": "messages.upsert", "data": msg}
            await handle_incoming_message(payload, remote_jid=remote_jid)
            recovered += 1
        except Exception:
            logger.exception("Error processing recovery message")

    logger.info("Recovery complete — %d message(s) processed.", recovered)


async def _fetch_recent_messages() -> list[dict]:
    url = f"{settings.evolution_api_url}/chat/findMessages/{settings.evolution_instance_name}"
    headers = {"apikey": settings.evolution_api_key}
    body = {
        "where": {"key": {"remoteJid": settings.group_jid}},
        "limit": 200,
    }

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, json=body, headers=headers)
        response.raise_for_status()
        data = response.json()

    if isinstance(data, list):
        return data
    return data.get("messages", {}).get("records", []) or data.get("records", []) or []
