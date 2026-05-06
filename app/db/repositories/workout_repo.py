from datetime import date, datetime
from typing import Optional
from app.db.client import get_supabase


def insert(
    participant_id: str,
    workout_date: date,
    submitted_at: datetime,
    sequence_number: int,
    shift: str,
    photo_message_id: Optional[str],
    text_message_id: Optional[str],
    photo_url: Optional[str],
    modality: Optional[str] = None,
) -> Optional[dict]:
    row = {
        "participant_id": participant_id,
        "workout_date": workout_date.isoformat(),
        "submitted_at": submitted_at.isoformat(),
        "sequence_number": sequence_number,
        "shift": shift,
        "photo_message_id": photo_message_id,
        "text_message_id": text_message_id,
        "photo_url": photo_url,
        "modality": modality,
    }
    result = (
        get_supabase()
        .table("workouts")
        .upsert(row, on_conflict="participant_id,workout_date,shift")
        .execute()
    )
    return result.data[0] if result.data else None


def get_by_participant_and_date(participant_id: str, workout_date: date) -> list[dict]:
    result = (
        get_supabase()
        .table("workouts")
        .select("*")
        .eq("participant_id", participant_id)
        .eq("workout_date", workout_date.isoformat())
        .is_("deleted_at", "null")
        .execute()
    )
    return result.data or []


def soft_delete_by_message_id(message_id: str) -> bool:
    supabase = get_supabase()
    result = (
        supabase.table("workouts")
        .update({"deleted_at": datetime.utcnow().isoformat(), "is_valid": False})
        .or_(f"photo_message_id.eq.{message_id},text_message_id.eq.{message_id}")
        .is_("deleted_at", "null")
        .execute()
    )
    return bool(result.data)


def count_valid_by_participant(participant_id: str) -> int:
    result = (
        get_supabase()
        .table("workouts")
        .select("id", count="exact")
        .eq("participant_id", participant_id)
        .eq("is_valid", True)
        .is_("deleted_at", "null")
        .execute()
    )
    return result.count or 0


def get_count_and_max_seq(participant_id: str) -> tuple[int, int]:
    result = get_supabase().rpc("get_workout_counts").execute()
    for row in (result.data or []):
        if row["participant_id"] == participant_id:
            return row["count"], row.get("last_seq") or 0
    return 0, 0
