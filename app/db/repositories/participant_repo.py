from typing import Optional
from app.db.client import get_supabase


def get_by_phone(phone: str) -> Optional[dict]:
    result = (
        get_supabase()
        .table("participants")
        .select("*")
        .or_(f"phone.eq.{phone},lid.eq.{phone}")
        .eq("is_active", True)
        .execute()
    )
    return result.data[0] if result.data else None


def get_all_admins() -> list[dict]:
    result = (
        get_supabase()
        .table("participants")
        .select("phone, is_main_admin")
        .eq("is_admin", True)
        .eq("is_active", True)
        .execute()
    )
    return result.data or []
