"""
Configura o webhook da Evolution API para incluir o evento messages.delete.
Uso: python scripts/configure_webhook.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from app.core.config import settings

url = f"{settings.evolution_api_url}/webhook/set/{settings.evolution_instance_name}"
headers = {"apikey": settings.evolution_api_key}

body = {
    "webhook": {
        "enabled": True,
        "url": f"https://fitness-group-agent-production.up.railway.app/webhook/evolution",
        "headers": {
            "x-evolution-secret": settings.evolution_webhook_secret,
        },
        "byEvents": False,
        "base64": False,
        "events": [
            "MESSAGES_UPSERT",
            "MESSAGES_DELETE",
        ],
    }
}

print("\n=== Configuração do Webhook Evolution API ===\n")
print(f"URL do webhook: {body['webhook']['url']}")
print(f"Eventos: {', '.join(body['webhook']['events'])}")
print()

try:
    response = httpx.post(url, json=body, headers=headers, timeout=15)
    response.raise_for_status()
    print("OK  Webhook configurado com sucesso!")
    print(f"    Resposta: {response.json()}")
except Exception as e:
    print(f"ERRO  {e}")
