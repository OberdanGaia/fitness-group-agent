from datetime import date, datetime, timezone
from typing import Optional

from app.db.client import get_supabase


def get_last_report() -> Optional[dict]:
    result = (
        get_supabase()
        .table("reports")
        .select("*")
        .order("generated_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def insert(
    trigger: str,
    triggered_by_id: Optional[str],
    period_start: date,
    period_end: date,
    snapshot: list,
    report_text: str,
) -> Optional[dict]:
    row = {
        "trigger": trigger,
        "triggered_by": triggered_by_id,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "snapshot": snapshot,
        "report_text": report_text,
    }
    result = get_supabase().table("reports").insert(row).execute()
    return result.data[0] if result.data else None


def mark_sent(report_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    get_supabase().table("reports").update({"sent_at": now}).eq("id", report_id).execute()
