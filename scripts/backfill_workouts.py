"""
Insere treinos históricos para participantes que já treinaram antes do bot entrar.
Uso: python scripts/backfill_workouts.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta
from app.db.client import get_supabase

CHALLENGE_START = date(2026, 1, 1)
YESTERDAY = date.today() - timedelta(days=1)

WORKOUTS = {
    "Thiago":     2,
    "Alan":       55,
    "Pri Cordeiro": 90,
    "Bia":        91,
    "David":      56,
    "Carol":      97,
    "Marcela":    105,
    "Oberdan":    76,
    "Heloisa":    107,
    "Pedro":      91,
    "Gui Tadiello": 48,
    "Jheni":      81,
    "Fran":       24,
    "Du":         50,
    "Ste":        72,
    "Iago":       17,
    "Piazzi":     105,
    "Gui Pacheco": 83,
    "Valentina":  37,
    "Gabie":      35,
    "Julia":      26,
    "Natan":      17,
}


def find_participant(name: str, all_participants: list) -> dict | None:
    name_lower = name.lower()
    for p in all_participants:
        if p["name"].lower() == name_lower:
            return p
    return None


def count_existing_workouts(participant_id: str) -> int:
    result = (
        get_supabase()
        .table("workouts")
        .select("id", count="exact")
        .eq("participant_id", participant_id)
        .eq("is_valid", True)
        .is_("deleted_at", "null")
        .execute()
    )
    return result.count or 0


def generate_dates(n: int) -> list[date]:
    total_days = (YESTERDAY - CHALLENGE_START).days + 1
    if n >= total_days:
        return [CHALLENGE_START + timedelta(days=i) for i in range(n)]
    step = total_days / n
    return [CHALLENGE_START + timedelta(days=round(i * step)) for i in range(n)]


def insert_workouts(participant_id: str, dates: list[date], start_seq: int) -> int:
    supabase = get_supabase()
    inserted = 0
    for i, d in enumerate(dates):
        try:
            supabase.table("workouts").insert({
                "participant_id": participant_id,
                "workout_date": d.isoformat(),
                "submitted_at": f"{d.isoformat()}T09:00:00+00:00",
                "sequence_number": start_seq + i,
                "shift": "manha",
                "is_valid": True,
            }).execute()
            inserted += 1
        except Exception:
            pass
    return inserted


def main():
    print("\n=== Inserção de Treinos Históricos ===\n")

    supabase = get_supabase()
    all_participants = supabase.table("participants").select("id,name,phone").eq("is_active", True).execute().data or []

    preview = []
    not_found = []

    for name, target in WORKOUTS.items():
        p = find_participant(name, all_participants)
        if not p:
            not_found.append(name)
            continue
        existing = count_existing_workouts(p["id"])
        to_insert = max(target - existing, 0)
        preview.append({
            "name": p["name"],
            "id": p["id"],
            "target": target,
            "existing": existing,
            "to_insert": to_insert,
        })

    print(f"{'Nome':<20} {'Feitos':<8} {'Já no banco':<14} {'Vai inserir'}")
    print("-" * 55)
    for r in preview:
        print(f"{r['name']:<20} {r['target']:<8} {r['existing']:<14} {r['to_insert']}")

    if not_found:
        print(f"\nNão encontrados no banco: {', '.join(not_found)}")

    total = sum(r["to_insert"] for r in preview)
    print(f"\nTotal a inserir: {total} treinos")
    print()

    confirm = input("Confirma a inserção? (s/n): ").strip().lower()
    if confirm != "s":
        print("Cancelado.")
        return

    print()
    for r in preview:
        if r["to_insert"] == 0:
            print(f"  OK  {r['name']} — já tem {r['existing']} treinos, nada a inserir")
            continue
        dates = generate_dates(r["to_insert"])
        inserted = insert_workouts(r["id"], dates, start_seq=r["existing"] + 1)
        print(f"  OK  {r['name']} — {inserted} treinos inseridos")

    print("\nConcluido!\n")


if __name__ == "__main__":
    main()
