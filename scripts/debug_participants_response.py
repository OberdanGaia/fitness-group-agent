"""
Mostra a resposta bruta da Evolution API para participants do grupo.
Uso: python scripts/debug_participants_response.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import httpx
from app.core.config import settings

url = f"{settings.evolution_api_url}/group/participants/{settings.evolution_instance_name}"
headers = {"apikey": settings.evolution_api_key}
params = {"groupJid": settings.group_jid}

response = httpx.get(url, params=params, headers=headers, timeout=15)
print(f"Status: {response.status_code}\n")
print(json.dumps(response.json(), indent=2, ensure_ascii=False))
