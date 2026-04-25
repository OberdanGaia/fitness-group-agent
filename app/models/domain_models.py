from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional
from uuid import UUID


class Participant(BaseModel):
    id: UUID
    phone: str
    name: str
    is_admin: bool
    is_main_admin: bool
    joined_at: date
    medical_leave_days: int
    is_active: bool


class Workout(BaseModel):
    id: UUID
    participant_id: UUID
    workout_date: date
    submitted_at: datetime
    sequence_number: int
    shift: str
    modality: Optional[str]
    photo_url: Optional[str]
    photo_message_id: Optional[str]
    text_message_id: Optional[str]
    is_valid: bool


class PendingMessage(BaseModel):
    id: UUID
    participant_id: UUID
    message_id: str
    message_type: str  # 'photo' | 'text'
    raw_payload: dict
    photo_url: Optional[str]
    sequence_number: Optional[int]
    raw_text: Optional[str]
    expires_at: datetime
