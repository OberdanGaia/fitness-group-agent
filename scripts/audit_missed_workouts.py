"""
Vasculha as mensagens das últimas 2 semanas no grupo e identifica treinos
que deveriam ter sido registrados mas não estão no banco.

Uso: python scripts/audit_missed_workouts.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytz

from app.core.config import settings
from app.db.client import get_supabase
from app.services.message_parser import extract_sequence_number, extract_text_candidates, get_shift

WINDOW_DAYS = 30
BR_TZ = pytz.timezone("America/Sao_Paulo")


def fetch_recent_messages(limit: int = 1000) -> list[dict]:
    url = f"{settings.evolution_api_url}/chat/findMessages/{settings.evolution_instance_name}"
    headers = {"apikey": settings.evolution_api_key}
    body = {
        "where": {"key": {"remoteJid": settings.group_jid}},
        "limit": limit,
    }
    response = httpx.post(url, json=body, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, list):
        return data
    return data.get("messages", {}).get("records", []) or data.get("records", []) or []


def load_participants() -> dict:
    result = get_supabase().table("participants").select("id,name,phone,lid").eq("is_active", True).execute()
    lookup = {}
    for p in (result.data or []):
        if p["phone"]:
            lookup[p["phone"]] = p
        if p["lid"]:
            lookup[p["lid"]] = p
    return lookup


def load_registered_message_ids() -> set:
    supabase = get_supabase()
    result = supabase.table("workouts").select("photo_message_id,text_message_id").is_("deleted_at", "null").execute()
    ids = set()
    for row in (result.data or []):
        if row["photo_message_id"]:
            ids.add(row["photo_message_id"])
        if row["text_message_id"]:
            ids.add(row["text_message_id"])
    return ids


def _resolve_message(message_data: dict) -> dict:
    """Retorna o conteúdo real da mensagem, desembrulhando edições se necessário."""
    edited = message_data.get("editedMessage", {}).get("message")
    if edited:
        return edited
    return message_data


def insert_workout(participant: dict, message_id: str, submitted_at: datetime, sequence_number: int, has_photo: bool) -> None:
    shift = get_shift(submitted_at, settings.timezone)
    workout_date = submitted_at.astimezone(BR_TZ).date()
    supabase = get_supabase()
    supabase.table("workouts").upsert({
        "participant_id": participant["id"],
        "workout_date": workout_date.isoformat(),
        "submitted_at": submitted_at.isoformat(),
        "sequence_number": sequence_number,
        "shift": shift,
        "photo_message_id": message_id if has_photo else None,
        "text_message_id": message_id if not has_photo else None,
        "is_valid": True,
    }, on_conflict="participant_id,workout_date,shift").execute()


def main():
    print("\n=== Auditoria de Treinos Perdidos (último mês) ===\n")

    print("Buscando mensagens do grupo via Evolution API...")
    try:
        messages = fetch_recent_messages()
    except Exception as e:
        print(f"Erro ao buscar mensagens: {e}")
        sys.exit(1)

    print(f"{len(messages)} mensagens encontradas.\n")

    cutoff = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    participants = load_participants()
    registered_ids = load_registered_message_ids()

    missed = []

    for msg in messages:
        ts = msg.get("messageTimestamp") or 0
        submitted_at = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        if submitted_at < cutoff:
            continue

        key = msg.get("key") or {}
        if key.get("fromMe"):
            continue

        message_id = key.get("id")
        if not message_id:
            continue

        # Já está registrado
        if message_id in registered_ids:
            continue

        # Identifica o remetente
        sender = (key.get("participant") or key.get("remoteJid") or "").split("@")[0]
        participant = participants.get(sender)
        if not participant:
            continue

        message_data = _resolve_message(msg.get("message") or {})
        texts = extract_text_candidates(message_data)
        has_photo = "imageMessage" in message_data

        sequence_number = None
        for text in texts:
            n = extract_sequence_number(text)
            if n is not None:
                sequence_number = n
                break

        # Só considera mensagens com foto + número (treino completo)
        if not has_photo or sequence_number is None:
            continue

        local_dt = submitted_at.astimezone(BR_TZ)
        missed.append({
            "participant": participant,
            "message_id": message_id,
            "submitted_at": submitted_at,
            "sequence_number": sequence_number,
            "has_photo": has_photo,
            "local_time": local_dt.strftime("%d/%m/%Y %H:%M"),
        })

    if not missed:
        print("Nenhum treino perdido encontrado no último mês.")
        return

    print(f"{'#':<4} {'Participante':<20} {'Seq':<6} {'Data/Hora':<20}")
    print("-" * 55)
    for i, m in enumerate(missed, 1):
        print(f"{i:<4} {m['participant']['name']:<20} {m['sequence_number']:<6} {m['local_time']}")

    print(f"\nTotal: {len(missed)} treino(s) perdido(s).")
    print()
    print("Digite os números dos treinos para inserir (ex: 1,3,5), 'todos' ou 'nenhum': ", end="")
    answer = input().strip().lower()

    if answer == "nenhum" or answer == "":
        print("Nenhum treino inserido.")
        return

    if answer == "todos":
        to_insert = missed
    else:
        try:
            indices = [int(x.strip()) - 1 for x in answer.split(",")]
            to_insert = [missed[i] for i in indices if 0 <= i < len(missed)]
        except ValueError:
            print("Entrada inválida. Nenhum treino inserido.")
            return

    print()
    for m in to_insert:
        try:
            insert_workout(m["participant"], m["message_id"], m["submitted_at"], m["sequence_number"], m["has_photo"])
            print(f"  OK  {m['participant']['name']} — {m['sequence_number']}/200 em {m['local_time']}")
        except Exception as e:
            print(f"  ERRO  {m['participant']['name']}: {e}")

    print(f"\nConcluído! {len(to_insert)} treino(s) inserido(s).\n")


if __name__ == "__main__":
    main()
