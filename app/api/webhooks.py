import logging

from fastapi import APIRouter, Request, HTTPException

from app.core.config import settings
from app.handlers.workout_handler import handle_incoming_message
from app.db.repositories import workout_repo

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/webhook/evolution")
async def evolution_webhook(request: Request):
    secret = request.headers.get("x-evolution-secret") or request.headers.get("apikey")
    if secret != settings.evolution_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid secret")

    payload = await request.json()
    event = payload.get("event")

    if event == "messages.delete":
        _handle_message_delete(payload)
        return {"status": "ok"}

    if event == "messages.update":
        await _handle_message_update(payload)
        return {"status": "ok"}

    if event != "messages.upsert":
        return {"status": "ignored"}

    data = payload.get("data", {})
    remote_jid = data.get("key", {}).get("remoteJid", "")
    oberdan_jid = f"{settings.oberdan_phone}@s.whatsapp.net"

    is_group = remote_jid == settings.group_jid
    is_private_from_oberdan = remote_jid == oberdan_jid

    if not is_group and not is_private_from_oberdan:
        return {"status": "ignored"}

    if data.get("key", {}).get("fromMe", False):
        return {"status": "ignored"}

    # Fire and forget — return 200 immediately so Evolution API doesn't retry
    try:
        await handle_incoming_message(payload, remote_jid=remote_jid)
    except Exception:
        logger.exception("Unhandled error processing webhook")

    return {"status": "ok"}


async def _handle_message_update(payload: dict) -> None:
    data = payload.get("data", {})
    updates = data if isinstance(data, list) else [data]

    for item in updates:
        key = item.get("key", {})
        remote_jid = key.get("remoteJid", "")

        if remote_jid != settings.group_jid:
            continue
        if key.get("fromMe", False):
            continue

        # Extract the edited message content
        update = item.get("update", {})
        message = update.get("message") or {}

        # Edited messages are wrapped inside editedMessage
        edited = message.get("editedMessage", {}).get("message") or message

        if not edited:
            continue

        # Reconstruct payload in the same format as messages.upsert
        reconstructed = {
            "event": "messages.upsert",
            "data": {
                "key": key,
                "message": edited,
                "messageTimestamp": item.get("messageTimestamp", 0),
            },
        }

        logger.info("Processing edited message: id=%s", key.get("id"))
        try:
            await handle_incoming_message(reconstructed, remote_jid=remote_jid)
        except Exception:
            logger.exception("Error processing edited message: id=%s", key.get("id"))


def _handle_message_delete(payload: dict) -> None:
    # Evolution API sends either a single key or a list of keys
    data = payload.get("data", {})
    keys = data if isinstance(data, list) else [data]

    for item in keys:
        message_id = (item.get("key") or item).get("id")
        if not message_id:
            continue
        deleted = workout_repo.soft_delete_by_message_id(message_id)
        if deleted:
            logger.info("Workout soft-deleted due to message deletion: message_id=%s", message_id)
        else:
            logger.debug("Message deleted but no workout found: message_id=%s", message_id)
