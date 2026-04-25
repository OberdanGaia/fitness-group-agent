from pydantic import BaseModel
from typing import Optional


class EvolutionImageMessage(BaseModel):
    mimetype: str = ""
    caption: Optional[str] = None
    url: Optional[str] = None


class EvolutionMessageContent(BaseModel):
    conversation: Optional[str] = None
    imageMessage: Optional[EvolutionImageMessage] = None
    extendedTextMessage: Optional[dict] = None


class EvolutionMessageKey(BaseModel):
    remoteJid: str
    fromMe: bool
    id: str
    participant: Optional[str] = None


class EvolutionWebhookData(BaseModel):
    key: EvolutionMessageKey
    message: Optional[EvolutionMessageContent] = None
    messageTimestamp: int


class EvolutionWebhookPayload(BaseModel):
    event: str
    instance: str
    data: EvolutionWebhookData
