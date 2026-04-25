import logging

from app.db.repositories import report_repo
from app.services import report_service, whatsapp_service

logger = logging.getLogger(__name__)


def is_admin_command(text: str) -> bool:
    return text.strip().lower().startswith("#")


async def handle_admin_command(text: str, participant: dict) -> None:
    cmd = text.strip().lower()
    if cmd.startswith("#relatorio"):
        await _handle_relatorio(participant)
    else:
        logger.debug("Unknown admin command from %s: %s", participant["phone"], text[:50])


async def _handle_relatorio(participant: dict) -> None:
    logger.info("Manual report requested by %s", participant["phone"])
    try:
        report_text, saved = await report_service.generate_report(
            trigger="manual",
            triggered_by_id=participant["id"],
        )
        await whatsapp_service.send_group_message(report_text)
        if saved:
            report_repo.mark_sent(saved["id"])
    except Exception:
        logger.exception("Failed to generate/send report for #relatorio command")
