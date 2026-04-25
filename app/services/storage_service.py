from datetime import date
import httpx
from app.core.config import settings
from app.db.client import get_supabase


async def download_image(url: str) -> bytes:
    """Download image from Evolution API media URL."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers={"apikey": settings.evolution_api_key})
        resp.raise_for_status()
        return resp.content


async def upload_photo(
    participant_phone: str,
    workout_date: date,
    message_id: str,
    image_bytes: bytes,
) -> str:
    path = f"{participant_phone}/{workout_date.isoformat()}/{message_id}.jpg"
    bucket = get_supabase().storage.from_(settings.supabase_storage_bucket)
    bucket.upload(path, image_bytes, {"content-type": "image/jpeg", "upsert": "true"})
    return bucket.get_public_url(path)
