import logging
import re
from datetime import datetime, date
from typing import Optional

import httpx
import pytz

from app.db.repositories import report_repo
from app.services import report_service, whatsapp_service
from app.services.report_service import ReportError

logger = logging.getLogger(__name__)

# Stores pending #add-treino confirmations: phone -> workout data
_pending_add_treino: dict[str, dict] = {}

_ADD_TREINO_PATTERN = re.compile(
    r"#add-treino\s+(\d{1,3})/200\s+para\s+(.+?)\s+em\s+(\d{1,2}/\d{1,2})\s+(\d{1,2}:\d{2})\s*(AM|PM|A\.M\.?|P\.M\.?)?",
    re.IGNORECASE,
)

_ADD_TREINO_HELP = (
    "Para adicionar um treino manualmente, envie:\n\n"
    "*#add-treino 105/200 para Pri Cordeiro em 15/05 8:16 AM*\n\n"
    "Campos obrigatórios:\n"
    "• Número do treino/200\n"
    "• Nome do participante (como está no banco)\n"
    "• Data no formato DD/MM\n"
    "• Horário e turno (AM/PM)"
)

BRT = pytz.timezone("America/Sao_Paulo")


def is_admin_command(text: str) -> bool:
    return text.strip().lower().startswith("#")


def has_pending_confirmation(phone: str) -> bool:
    return phone in _pending_add_treino


async def handle_confirmation(phone: str, answer: str, reply_phone: str) -> None:
    pending = _pending_add_treino.pop(phone, None)
    if not pending:
        return

    if answer == "n":
        await whatsapp_service.send_private_message(reply_phone, "❌ Inserção cancelada.")
        return

    try:
        from app.db.repositories import workout_repo
        workout_repo.insert(
            participant_id=pending["participant"]["id"],
            workout_date=pending["workout_date"],
            submitted_at=pending["submitted_at"],
            sequence_number=pending["sequence_number"],
            shift=pending["shift"],
            photo_message_id=None,
            text_message_id=None,
            photo_url=None,
        )
        msg = (
            f"✅ Treino {pending['sequence_number']}/200 de *{pending['participant']['name']}* "
            f"registrado em {pending['workout_date'].strftime('%d/%m')} — turno *{pending['shift']}*."
        )
        logger.info(
            "Workout manually added: participant=%s seq=%d date=%s",
            pending["participant"]["name"], pending["sequence_number"], pending["workout_date"],
        )
    except Exception:
        logger.exception("Failed to insert workout via #add-treino")
        msg = "⚠️ Erro ao inserir treino. Verifique os logs no Railway."

    await whatsapp_service.send_private_message(reply_phone, msg)


async def handle_admin_command(text: str, participant: dict, reply_phone: str = None) -> None:
    cmd = text.strip().lower()
    if cmd.startswith("#relatorio"):
        await _handle_relatorio(participant, reply_phone=reply_phone)
    elif cmd.startswith("#add-treino"):
        await _handle_add_treino(text.strip(), participant, reply_phone=reply_phone)
    else:
        logger.debug("Unknown admin command from %s: %s", participant["phone"], text[:50])


async def _handle_add_treino(text: str, participant: dict, reply_phone: str = None) -> None:
    if not reply_phone:
        return

    # Help message when no arguments provided
    if text.strip().lower() == "#add-treino":
        await whatsapp_service.send_private_message(reply_phone, _ADD_TREINO_HELP)
        return

    match = _ADD_TREINO_PATTERN.search(text)
    if not match:
        await whatsapp_service.send_private_message(
            reply_phone,
            f"⚠️ Formato inválido.\n\n{_ADD_TREINO_HELP}",
        )
        return

    seq_str, name_raw, date_str, time_str, ampm = match.groups()
    sequence_number = int(seq_str)
    name_raw = name_raw.strip()

    # Parse date
    workout_date = _parse_date(date_str)
    if not workout_date:
        await whatsapp_service.send_private_message(
            reply_phone, f"⚠️ Data inválida: *{date_str}*. Use o formato DD/MM."
        )
        return

    # Parse time
    submitted_at = _parse_time(workout_date, time_str, ampm)
    if not submitted_at:
        await whatsapp_service.send_private_message(
            reply_phone, f"⚠️ Horário inválido: *{time_str} {ampm or ''}*. Use o formato H:MM AM/PM."
        )
        return

    # Derive shift
    from app.core.constants import SHIFTS
    local_time = submitted_at.astimezone(BRT).time()
    shift = next(
        (s for s, (start, end) in SHIFTS.items() if start <= local_time <= end),
        "noite",
    )

    # Lookup participant by name
    found = _find_participant(name_raw)
    if not found:
        await whatsapp_service.send_private_message(
            reply_phone,
            f"⚠️ Participante *{name_raw}* não encontrado. Verifique o nome no banco.",
        )
        return

    _pending_add_treino[participant["phone"]] = {
        "participant": found,
        "sequence_number": sequence_number,
        "workout_date": workout_date,
        "submitted_at": submitted_at,
        "shift": shift,
    }

    weekdays = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
    day_name = weekdays[workout_date.weekday()]
    time_display = submitted_at.astimezone(BRT).strftime("%H:%M")

    preview = (
        f"📋 *Confirmar inserção:*\n\n"
        f"• Participante: *{found['name']}*\n"
        f"• Treino: *{sequence_number}/200*\n"
        f"• Data: *{workout_date.strftime('%d/%m/%Y')}* ({day_name})\n"
        f"• Hora: *{time_display}* → turno *{shift}*\n\n"
        f"Responda *s* para confirmar ou *n* para cancelar."
    )
    await whatsapp_service.send_private_message(reply_phone, preview)


def _parse_date(date_str: str) -> Optional[date]:
    try:
        day, month = map(int, date_str.split("/"))
        return date(2026, month, day)
    except (ValueError, AttributeError):
        return None


def _parse_time(workout_date: date, time_str: str, ampm: Optional[str]) -> Optional[datetime]:
    try:
        hour, minute = map(int, time_str.split(":"))
        if ampm:
            normalized = ampm.upper().replace(".", "").replace(" ", "")
            if normalized == "PM" and hour != 12:
                hour += 12
            elif normalized == "AM" and hour == 12:
                hour = 0
        dt = datetime(workout_date.year, workout_date.month, workout_date.day, hour, minute)
        return BRT.localize(dt)
    except (ValueError, AttributeError):
        return None


def _find_participant(name: str) -> Optional[dict]:
    from app.db.client import get_supabase
    participants = (
        get_supabase()
        .table("participants")
        .select("id,name,phone")
        .eq("is_active", True)
        .execute()
        .data or []
    )
    name_lower = name.lower()
    # Exact match first
    for p in participants:
        if p["name"].lower() == name_lower:
            return p
    # Partial match fallback
    matches = [p for p in participants if name_lower in p["name"].lower()]
    return matches[0] if len(matches) == 1 else None


async def _handle_relatorio(participant: dict, reply_phone: str = None) -> None:
    logger.info("Manual report requested by %s", participant["phone"])
    try:
        report_text, saved = await report_service.generate_report(
            trigger="manual",
            triggered_by_id=participant["id"],
        )
        if reply_phone:
            await whatsapp_service.send_private_message(reply_phone, report_text)
        else:
            await whatsapp_service.send_group_message(report_text)
        if saved:
            report_repo.mark_sent(saved["id"])
    except ReportError as e:
        logger.error("Report error (service=%s): %s", e.service, e)
        error_msg = f"⚠️ Erro ao gerar relatório — serviço indisponível: *{e.service}*. Tente novamente em alguns minutos."
        if reply_phone:
            await whatsapp_service.send_private_message(reply_phone, error_msg)
    except httpx.HTTPError as e:
        logger.error("WhatsApp send error: %s", e)
        if reply_phone:
            await whatsapp_service.send_private_message(reply_phone, "⚠️ Erro ao enviar mensagem — serviço indisponível: *WhatsApp (Evolution API)*. Tente novamente em alguns minutos.")
    except Exception:
        logger.exception("Unexpected error for #relatorio command")
        if reply_phone:
            await whatsapp_service.send_private_message(reply_phone, "⚠️ Erro inesperado ao gerar relatório. Verifique os logs no Railway.")
