import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.webhooks import router as webhook_router
from app.core import constants
from app.db.repositories import participant_repo
from app import scheduler
from app.services import recovery_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_admin_phones()
    scheduler.start()
    logger.info("Fitness bot started. Admins loaded: %s", constants.ADMIN_PHONES)
    await recovery_service.recover_missed_messages()
    yield
    scheduler.stop()


def _load_admin_phones() -> None:
    admins = participant_repo.get_all_admins()
    for a in admins:
        constants.ADMIN_PHONES.add(a["phone"])
        if a.get("is_main_admin"):
            constants.MAIN_ADMIN_PHONE = a["phone"]


app = FastAPI(title="Fitness Bot 2026", lifespan=lifespan)
app.include_router(webhook_router)


@app.get("/health")
def health():
    return {"status": "ok"}
