"""
Atualiza telefone e LID de um participante que trocou de número.
Busca o novo LID diretamente do grupo via Evolution API.

Uso: python scripts/update_participant_phone.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from app.core.config import settings
from app.db.client import get_supabase

NAME = ""
NEW_PHONE = ""


def fetch_group_participants() -> list[dict]:
    url = f"{settings.evolution_api_url}/group/participants/{settings.evolution_instance_name}"
    headers = {"apikey": settings.evolution_api_key}
    params = {"groupJid": settings.group_jid}
    response = httpx.get(url, params=params, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, list) else data.get("participants", [])


def main():
    print(f"\n=== Atualização de número: {NAME} ===\n")

    supabase = get_supabase()

    # Busca o participante pelo nome
    result = supabase.table("participants").select("id,name,phone,lid").ilike("name", NAME).execute()
    participants = result.data or []

    if not participants:
        print(f"Participante '{NAME}' não encontrado no banco.")
        sys.exit(1)

    participant = participants[0]
    print(f"Encontrado no banco:")
    print(f"  Nome:     {participant['name']}")
    print(f"  Telefone: {participant['phone']}")
    print(f"  LID:      {participant['lid']}")
    print()

    # Busca o novo LID no grupo
    print("Buscando novo LID no grupo via Evolution API...")
    try:
        raw = fetch_group_participants()
    except Exception as e:
        print(f"Erro ao buscar participantes do grupo: {e}")
        sys.exit(1)

    new_lid = None
    for p in raw:
        phone = (p.get("phoneNumber") or "").split("@")[0]
        if phone == NEW_PHONE:
            new_lid = (p.get("id") or "").split("@")[0]
            break

    if not new_lid:
        print(f"Número {NEW_PHONE} não encontrado no grupo.")
        print("Verifique se o número já entrou no grupo do WhatsApp.")
        sys.exit(1)

    print(f"Novo LID encontrado: {new_lid}")
    print()
    print(f"Alterações que serão feitas:")
    print(f"  Telefone: {participant['phone']} → {NEW_PHONE}")
    print(f"  LID:      {participant['lid']} → {new_lid}")
    print()

    confirm = input("Confirma a atualização? (s/n): ").strip().lower()
    if confirm != "s":
        print("Cancelado.")
        return

    supabase.table("participants").update({
        "phone": NEW_PHONE,
        "lid": new_lid,
    }).eq("id", participant["id"]).execute()

    print(f"\n  OK  {NAME} atualizado com sucesso!")
    print(f"      Os treinos anteriores estão preservados.")
    print(f"      Novos treinos serão contabilizados automaticamente.\n")


if __name__ == "__main__":
    main()
