import asyncio
import logging
from datetime import datetime

from app.handlers import admin_handler
from app.services import message_parser
from app.services.storage_service import download_image, upload_photo
from app.db.repositories import participant_repo, workout_repo, pending_message_repo

logger = logging.getLogger(__name__)

_background_tasks: set = set()


async def handle_incoming_message(payload: dict, remote_jid: str = None) -> None:
    from app.core.config import settings

    sender_phone = message_parser.extract_sender_phone(payload)
    if not sender_phone:
        return

    participant = participant_repo.get_by_phone(sender_phone)
    if not participant:
        return

    message_data = payload.get("data", {}).get("message") or {}

    is_private = remote_jid and remote_jid != settings.group_jid
    reply_phone = participant["phone"] if is_private else None

    # Handle pending #add-treino confirmation (s/n) before anything else
    if is_private and participant.get("is_admin") and admin_handler.has_pending_confirmation(sender_phone):
        for text in message_parser.extract_text_candidates(message_data):
            answer = text.strip().lower()
            if answer in ("s", "n"):
                await admin_handler.handle_confirmation(sender_phone, answer, reply_phone)
                return

    # Route admin commands before workout processing
    if participant.get("is_admin"):
        for text in message_parser.extract_text_candidates(message_data):
            if admin_handler.is_admin_command(text):
                await admin_handler.handle_admin_command(text, participant, reply_phone=reply_phone)
                return
    message_id = message_parser.extract_message_id(payload)
    submitted_at = message_parser.extract_timestamp(payload)

    is_photo = message_parser.has_image(message_data)
    sequence_number = None
    raw_text = ""

    for text in message_parser.extract_text_candidates(message_data):
        n = message_parser.extract_sequence_number(text)
        if n is not None:
            sequence_number = n
            raw_text = text
            break

    if is_photo and sequence_number is not None:
        # Best case: photo with caption containing N/200
        _, max_seq_before = workout_repo.get_count_and_max_seq(participant["id"])
        photo_url = await _store_photo(message_data, participant["phone"], message_id, submitted_at)
        _save_workout(participant, message_id, message_id, submitted_at, sequence_number, photo_url)
        _check_sequence_mismatch(participant, sequence_number, max_seq_before)

    elif is_photo:
        # Photo only — wait for the text
        photo_url = await _store_photo(message_data, participant["phone"], message_id, submitted_at)
        pending = pending_message_repo.get_pending_counterpart(participant["id"], "text")
        if pending:
            _, max_seq_before = workout_repo.get_count_and_max_seq(participant["id"])
            _save_workout(
                participant,
                message_id,
                pending["message_id"],
                submitted_at,
                pending["sequence_number"],
                photo_url,
            )
            pending_message_repo.delete(pending["id"])
            _check_sequence_mismatch(participant, pending["sequence_number"], max_seq_before)
        else:
            pending_message_repo.insert_photo(participant["id"], message_id, payload, photo_url)

    elif sequence_number is not None:
        # Text with N/200 — look for a pending photo
        pending = pending_message_repo.get_pending_counterpart(participant["id"], "photo")
        if pending:
            _, max_seq_before = workout_repo.get_count_and_max_seq(participant["id"])
            _save_workout(
                participant,
                pending["message_id"],
                message_id,
                submitted_at,
                sequence_number,
                pending["photo_url"],
            )
            pending_message_repo.delete(pending["id"])
            _check_sequence_mismatch(participant, sequence_number, max_seq_before)
        else:
            pending_message_repo.insert_text(
                participant["id"], message_id, payload, sequence_number, raw_text
            )


async def _store_photo(
    message_data: dict,
    phone: str,
    message_id: str,
    submitted_at: datetime,
) -> str | None:
    image_info = message_data.get("imageMessage", {})
    url = image_info.get("url")
    if not url:
        return None
    try:
        image_bytes = await download_image(url)
        return await upload_photo(phone, submitted_at.date(), message_id, image_bytes)
    except Exception:
        logger.exception("Failed to store photo for message %s", message_id)
        return None


def _check_sequence_mismatch(participant: dict, sequence_number: int, max_seq_before: int) -> None:
    if sequence_number != max_seq_before + 1:
        task = asyncio.create_task(_alert_mismatch_later(participant, sequence_number, max_seq_before))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)


async def _alert_mismatch_later(participant: dict, sent_seq: int, max_seq_at_send: int) -> None:
    from app.core.config import settings
    from app.services import whatsapp_service

    await asyncio.sleep(600)

    count, max_seq = workout_repo.get_count_and_max_seq(participant["id"])
    if count == max_seq:
        return

    missing = list(range(max_seq_at_send + 1, sent_seq))
    if len(missing) == 1:
        missing_str = f"o treino {missing[0]}/200"
    else:
        missing_str = f"os treinos {', '.join(str(m) for m in missing)}/200"

    last_ref = f"o último registrado era {max_seq_at_send}/200" if max_seq_at_send > 0 else "nenhum treino registrado antes"
    msg = (
        f"⚠️ {participant['name']} mandou {sent_seq}/200 mas {last_ref}. "
        f"Parece que perdemos {missing_str}."
    )
    logger.info("Sequence mismatch alert: %s sent=%d last_registered=%d", participant["name"], sent_seq, max_seq_at_send)
    await whatsapp_service.send_private_message(settings.oberdan_phone, msg)


def _save_workout(
    participant: dict,
    photo_message_id: str | None,
    text_message_id: str | None,
    submitted_at: datetime,
    sequence_number: int,
    photo_url: str | None,
) -> None:
    from app.core.config import settings
    import pytz
    shift = message_parser.get_shift(submitted_at, settings.timezone)
    workout_date = submitted_at.astimezone(pytz.timezone(settings.timezone)).date()

    try:
        workout_repo.insert(
            participant_id=participant["id"],
            workout_date=workout_date,
            submitted_at=submitted_at,
            sequence_number=sequence_number,
            shift=shift,
            photo_message_id=photo_message_id,
            text_message_id=text_message_id,
            photo_url=photo_url,
        )
        logger.info(
            "Workout registered: participant=%s seq=%s shift=%s date=%s",
            participant["phone"], sequence_number, shift, workout_date,
        )
    except Exception:
        logger.exception(
            "Failed to insert workout: participant=%s seq=%s", participant["phone"], sequence_number
        )
