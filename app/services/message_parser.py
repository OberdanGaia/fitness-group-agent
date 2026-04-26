import re
from datetime import datetime
from typing import Optional

import pytz

from app.core.constants import SHIFTS

WORKOUT_PATTERN = re.compile(r'\b(\d{1,3})[/:\-.]200\b', re.IGNORECASE)


def extract_sequence_number(text: str) -> Optional[int]:
    match = WORKOUT_PATTERN.search(text)
    if match:
        n = int(match.group(1))
        if 1 <= n <= 200:
            return n
    return None


def get_shift(dt: datetime, tz_name: str = "America/Sao_Paulo") -> str:
    tz = pytz.timezone(tz_name)
    local_dt = dt.astimezone(tz)
    t = local_dt.time()
    for shift_name, (start, end) in SHIFTS.items():
        if start <= t <= end:
            return shift_name
    return "noite"


def extract_sender_phone(payload: dict) -> Optional[str]:
    key = payload.get("data", {}).get("key", {})
    participant = key.get("participant")
    if participant:
        return participant.split("@")[0]
    remote = key.get("remoteJid", "")
    if "@s.whatsapp.net" in remote:
        return remote.split("@")[0]
    return None


def extract_message_id(payload: dict) -> Optional[str]:
    return payload.get("data", {}).get("key", {}).get("id")


def extract_timestamp(payload: dict) -> datetime:
    ts = payload.get("data", {}).get("messageTimestamp", 0)
    return datetime.fromtimestamp(int(ts), tz=pytz.UTC)


def extract_text_candidates(message: dict) -> list[str]:
    candidates = [
        message.get("conversation") or "",
        (message.get("extendedTextMessage") or {}).get("text") or "",
        (message.get("imageMessage") or {}).get("caption") or "",
    ]
    return [c for c in candidates if c]


def has_image(message: dict) -> bool:
    return "imageMessage" in message
