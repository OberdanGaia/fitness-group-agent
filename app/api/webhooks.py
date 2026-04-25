import logging

from fastapi import APIRouter, Request, HTTPException

from app.core.config import settings
from app.handlers.workout_handler import handle_incoming_message

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/webhook/evolution")
async def evolution_webhook(request: Request):
    secret = request.headers.get("x-evolution-secret") or request.headers.get("apikey")
    if secret != settings.evolution_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid secret")

    payload = await request.json()

    if payload.get("event") != "messages.upsert":
        return {"status": "ignored"}

    data = payload.get("data", {})
    remote_jid = data.get("key", {}).get("remoteJid", "")
    if remote_jid != settings.group_jid:
        return {"status": "ignored"}

    if data.get("key", {}).get("fromMe", False):
        return {"status": "ignored"}

    # Fire and forget — return 200 immediately so Evolution API doesn't retry
    try:
        await handle_incoming_message(payload)
    except Exception:
        logger.exception("Unhandled error processing webhook")

    return {"status": "ok"}
