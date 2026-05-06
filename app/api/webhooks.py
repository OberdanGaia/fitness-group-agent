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
