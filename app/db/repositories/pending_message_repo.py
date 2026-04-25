from typing import Optional
from app.db.client import get_supabase


def insert_photo(
    participant_id: str,
    message_id: str,
    raw_payload: dict,
    photo_url: str,
) -> None:
    get_supabase().table("pending_messages").insert({
        "participant_id": participant_id,
        "message_id": message_id,
        "message_type": "photo",
        "raw_payload": raw_payload,
        "photo_url": photo_url,
    }).execute()


def insert_text(
    participant_id: str,
    message_id: str,
    raw_payload: dict,
    sequence_number: int,
    raw_text: str,
) -> None:
    get_supabase().table("pending_messages").insert({
        "participant_id": participant_id,
        "message_id": message_id,
        "message_type": "text",
        "raw_payload": raw_payload,
        "sequence_number": sequence_number,
        "raw_text": raw_text,
    }).execute()


def get_pending_counterpart(participant_id: str, counterpart_type: str) -> Optional[dict]:
    """Return the most recent pending message of the given type within the 3h window."""
    result = (
        get_supabase()
        .table("pending_messages")
        .select("*")
        .eq("participant_id", participant_id)
        .eq("message_type", counterpart_type)
        .gt("expires_at", "now()")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def delete(pending_id: str) -> None:
    get_supabase().table("pending_messages").delete().eq("id", pending_id).execute()


def delete_expired() -> None:
    get_supabase().table("pending_messages").delete().lt("expires_at", "now()").execute()
