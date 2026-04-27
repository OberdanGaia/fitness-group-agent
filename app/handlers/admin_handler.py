import logging

import httpx

from app.db.repositories import report_repo
from app.services import report_service, whatsapp_service
from app.services.report_service import ReportError

logger = logging.getLogger(__name__)


def is_admin_command(text: str) -> bool:
    return text.strip().lower().startswith("#")


async def handle_admin_command(text: str, participant: dict, reply_phone: str = None) -> None:
    cmd = text.strip().lower()
    if cmd.startswith("#relatorio"):
        await _handle_relatorio(participant, reply_phone=reply_phone)
    else:
        logger.debug("Unknown admin command from %s: %s", participant["phone"], text[:50])


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
