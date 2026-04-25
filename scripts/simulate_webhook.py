"""
Simula webhooks da Evolution API para testar o bot localmente.
Uso: python scripts/simulate_webhook.py --scenario <cenario>

Cenários disponíveis:
  photo_then_text   - foto chega primeiro, texto "N/200" chega depois
  text_then_photo   - texto chega primeiro, foto chega depois
  caption           - foto com legenda "N/200" na mesma mensagem
  unknown_sender    - número desconhecido (deve ser ignorado)
  from_me           - mensagem do próprio bot (deve ser ignorada)
"""

import argparse
import time
import httpx
from datetime import datetime

BASE_URL = "http://localhost:8000"
WEBHOOK_SECRET = "a_random_secret_you_generate"  # igual ao .env
GROUP_JID = "5511XXXXXXXXXXX@g.us"               # cole o JID real do grupo

# Número de um participante cadastrado no banco
PARTICIPANT_PHONE = "5511999990000"


def make_headers() -> dict:
    return {"x-evolution-secret": WEBHOOK_SECRET, "Content-Type": "application/json"}


def make_text_payload(phone: str, text: str, msg_id: str | None = None) -> dict:
    return {
        "event": "messages.upsert",
        "instance": "fitness2026",
        "data": {
            "key": {
                "remoteJid": GROUP_JID,
                "fromMe": False,
                "id": msg_id or f"TXT{int(time.time())}",
                "participant": f"{phone}@s.whatsapp.net",
            },
            "message": {"conversation": text},
            "messageTimestamp": int(datetime.now().timestamp()),
        },
    }


def make_photo_payload(phone: str, caption: str = "", msg_id: str | None = None) -> dict:
    return {
        "event": "messages.upsert",
        "instance": "fitness2026",
        "data": {
            "key": {
                "remoteJid": GROUP_JID,
                "fromMe": False,
                "id": msg_id or f"IMG{int(time.time())}",
                "participant": f"{phone}@s.whatsapp.net",
            },
            "message": {
                "imageMessage": {
                    "mimetype": "image/jpeg",
                    "caption": caption,
                    "url": "https://example.com/fake-image.jpg",
                }
            },
            "messageTimestamp": int(datetime.now().timestamp()),
        },
    }


def send(payload: dict) -> None:
    r = httpx.post(f"{BASE_URL}/webhook/evolution", json=payload, headers=make_headers())
    print(f"  → {r.status_code} {r.json()}")


def scenario_photo_then_text():
    print("Cenário: foto primeiro, texto depois")
    send(make_photo_payload(PARTICIPANT_PHONE, msg_id="IMG001"))
    time.sleep(1)
    send(make_text_payload(PARTICIPANT_PHONE, "47/200", msg_id="TXT001"))


def scenario_text_then_photo():
    print("Cenário: texto primeiro, foto depois")
    send(make_text_payload(PARTICIPANT_PHONE, "48/200", msg_id="TXT002"))
    time.sleep(1)
    send(make_photo_payload(PARTICIPANT_PHONE, msg_id="IMG002"))


def scenario_caption():
    print("Cenário: foto com legenda N/200 na mesma mensagem")
    send(make_photo_payload(PARTICIPANT_PHONE, caption="49/200 Treino de musculação!", msg_id="IMG003"))


def scenario_unknown_sender():
    print("Cenário: número desconhecido (deve ser ignorado silenciosamente)")
    payload = make_text_payload("5511000000000", "50/200")
    send(payload)


def scenario_from_me():
    print("Cenário: mensagem fromMe=True (deve ser ignorada)")
    payload = make_text_payload(PARTICIPANT_PHONE, "51/200")
    payload["data"]["key"]["fromMe"] = True
    send(payload)


SCENARIOS = {
    "photo_then_text": scenario_photo_then_text,
    "text_then_photo": scenario_text_then_photo,
    "caption": scenario_caption,
    "unknown_sender": scenario_unknown_sender,
    "from_me": scenario_from_me,
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=list(SCENARIOS.keys()), required=True)
    args = parser.parse_args()
    SCENARIOS[args.scenario]()
