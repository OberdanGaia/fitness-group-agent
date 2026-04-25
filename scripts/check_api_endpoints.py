"""
Testa variações de endpoints da Evolution API para descobrir o correto.
Uso: python scripts/check_api_endpoints.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from app.core.config import settings

BASE = settings.evolution_api_url
INSTANCE = settings.evolution_instance_name
GROUP_JID = settings.group_jid
HEADERS = {"apikey": settings.evolution_api_key}

ENDPOINTS = [
    ("GET", f"/group/participants/{INSTANCE}", {"groupJid": GROUP_JID}),
    ("GET", f"/group/findParticipants/{INSTANCE}", {"groupJid": GROUP_JID}),
    ("GET", f"/group/fetchAllGroups/{INSTANCE}", {"getParticipants": "true"}),
    ("GET", f"/group/{INSTANCE}/participants", {"groupJid": GROUP_JID}),
    ("GET", f"/{INSTANCE}/group/participants", {"groupJid": GROUP_JID}),
    ("GET", "/", {}),
    ("GET", "/health", {}),
    ("GET", "/ping", {}),
]

print(f"\nTestando endpoints em: {BASE}\n")
print(f"{'Método':<8} {'Endpoint':<55} {'Status'}")
print("-" * 80)

with httpx.Client(headers=HEADERS, timeout=10) as client:
    for method, path, params in ENDPOINTS:
        url = BASE + path
        try:
            if method == "GET":
                r = client.get(url, params=params)
            else:
                r = client.post(url, json=params)
            status = str(r.status_code)
            if r.status_code not in (404, 401, 403):
                status += "  <-- FUNCIONA"
        except Exception as e:
            status = f"ERRO: {e}"
        print(f"{method:<8} {path:<55} {status}")

print()
