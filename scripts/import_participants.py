"""
Importa participantes do grupo WhatsApp para o banco de dados.
Busca nome, telefone e LID de cada membro via Evolution API.

Uso: python scripts/import_participants.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from app.core.config import settings
from app.db.client import get_supabase


def fetch_group_participants() -> list[dict]:
    url = f"{settings.evolution_api_url}/group/participants/{settings.evolution_instance_name}"
    headers = {"apikey": settings.evolution_api_key}
    params = {"groupJid": settings.group_jid}

    response = httpx.get(url, params=params, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()

    if isinstance(data, list):
        return data
    return data.get("participants", [])


def clean_name(name: str) -> str:
    name = (name or "").strip()
    if name.startswith("~"):
        name = name[1:].strip()
    return name


def get_existing() -> dict:
    result = get_supabase().table("participants").select("id,phone,lid,name").execute()
    return {p["phone"]: p for p in (result.data or [])}


def main():
    print("\n=== Importação de Participantes do Grupo ===\n")
    print("Buscando membros via Evolution API...")

    try:
        raw = fetch_group_participants()
    except Exception as e:
        print(f"Erro ao buscar participantes: {e}")
        sys.exit(1)

    print(f"{len(raw)} membros encontrados.\n")
    existing = get_existing()

    to_insert = []
    to_update = []

    for p in raw:
        phone = (p.get("phoneNumber") or "").split("@")[0]
        raw_lid = (p.get("id") or "").split("@")[0]
        wa_name = clean_name(p.get("name") or p.get("pushName") or "")

        if not phone:
            continue

        if phone in existing:
            to_update.append({
                "db_id": existing[phone]["id"],
                "lid": raw_lid,
                "name": existing[phone]["name"],
                "phone": phone,
            })
        else:
            to_insert.append({"phone": phone, "lid": raw_lid, "wa_name": wa_name})

    print(f"{'Telefone':<20} {'Nome':<30} {'Situação'}")
    print("-" * 72)
    for p in to_update:
        print(f"{p['phone']:<20} {p['name']:<30} já cadastrado (LID será atualizado)")
    for p in to_insert:
        print(f"{p['phone']:<20} {p['wa_name'] or '(sem nome)':<30} NOVO")

    print()

    confirmed_new = []
    if to_insert:
        print("Para cada membro NOVO, confirme ou corrija o nome.")
        print("Pressione Enter para aceitar o nome do WhatsApp.\n")
        for p in to_insert:
            suggestion = p["wa_name"] or ""
            answer = input(f"  {p['phone']} — '{suggestion}': ").strip()
            final = answer or suggestion
            if not final:
                print(f"  Pulando {p['phone']} — sem nome definido.")
                continue
            confirmed_new.append({**p, "name": final})

    print()
    supabase = get_supabase()

    if confirmed_new:
        print(f"Inserindo {len(confirmed_new)} participante(s)...")
        for p in confirmed_new:
            try:
                supabase.table("participants").insert({
                    "name": p["name"],
                    "phone": p["phone"],
                    "lid": p["lid"] or None,
                    "joined_at": "2026-01-01",
                    "is_admin": False,
                    "is_main_admin": False,
                    "medical_leave_days": 0,
                    "is_active": True,
                }).execute()
                print(f"  OK  {p['name']} ({p['phone']})")
            except Exception as e:
                print(f"  ERRO  {p['name']}: {e}")

    if to_update:
        print(f"Atualizando LID de {len(to_update)} participante(s) já cadastrado(s)...")
        for p in to_update:
            try:
                supabase.table("participants").update(
                    {"lid": p["lid"] or None}
                ).eq("id", p["db_id"]).execute()
                print(f"  OK  {p['name']} ({p['phone']})")
            except Exception as e:
                print(f"  ERRO  {p['name']}: {e}")

    print("\nConcluido!\n")


if __name__ == "__main__":
    main()
